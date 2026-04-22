"""
main.py — PulseBoard FastAPI backend.
All routes: /upload, /query, /anomalies, /insights, /root-cause
Session-based: each upload gets a session_id; subsequent requests use it.
"""

import os
import json
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from services.query_engine import (
    save_csv,
    get_csv_path,
    detect_schema,
    suggest_starter_questions,
    execute_sql,
)
from services.nl_to_sql import nl_to_sql_with_retry
from services.anomaly import detect_anomalies
from services.insights import generate_weekly_insights

load_dotenv()

app = FastAPI(
    title="PulseBoard API",
    description="NL-powered analytics backend for non-technical startup founders",
    version="1.0.0",
)

# CORS — allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory schema cache (session_id → schema dict)
_schema_cache: dict[str, dict] = {}


# ─── Request/Response Models ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    session_id: str
    question: str


class RootCauseRequest(BaseModel):
    session_id: str
    column: str
    chart_context: str = ""


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {"status": "ok", "service": "PulseBoard API", "version": "1.0.0"}


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file. Returns:
    - session_id (use this for all subsequent requests)
    - schema (columns with types)
    - starter_questions (5 AI-suggested questions)
    - row_count
    - sample (first 5 rows)
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 50MB.")

    try:
        session_id = save_csv(contents, file.filename)
        schema = detect_schema(session_id)
        questions = suggest_starter_questions(schema)

        # Cache schema for this session
        _schema_cache[session_id] = schema

        return {
            "session_id": session_id,
            "filename": file.filename,
            "schema": schema,
            "starter_questions": questions,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/query")
async def run_nl_query(req: QueryRequest):
    """
    Convert a natural language question to SQL and execute it.
    Returns:
    - sql (generated SQL query — shown in UI for transparency)
    - result (rows + columns + chart_type)
    - attempts (1 or 2 — shows if retry was needed)
    - success (bool)
    """
    schema = _schema_cache.get(req.session_id)
    if not schema:
        # Reload schema from disk if not in cache
        csv_path = get_csv_path(req.session_id)
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="Session not found. Please re-upload your CSV.")
        schema = detect_schema(req.session_id)
        _schema_cache[req.session_id] = schema

    def executor(sql: str):
        return execute_sql(req.session_id, sql)

    result = nl_to_sql_with_retry(req.question, schema, executor)

    if not result["success"]:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": result.get("error", "Query failed"),
                "sql": result.get("sql", ""),
                "attempts": result.get("attempts", 2),
            },
        )

    return {
        "success": True,
        "question": req.question,
        "sql": result["sql"],
        "result": result["result"],
        "attempts": result["attempts"],
    }


@app.get("/anomalies/{session_id}")
async def get_anomalies(session_id: str):
    """
    Run Z-score anomaly detection on all numeric columns.
    Returns ranked list of anomaly alerts (Critical first).
    """
    csv_path = get_csv_path(session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        alerts = detect_anomalies(csv_path)
        return {"alerts": alerts, "total": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")


@app.get("/insights/{session_id}")
async def get_insights(session_id: str):
    """
    Generate LLM weekly insight summary.
    Returns 3-5 plain-English bullet points + metric deltas table.
    """
    csv_path = get_csv_path(session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    if not os.getenv("GEMINI_API_KEY"):
        return {
            "bullets": [
                "📈 Set your GEMINI_API_KEY in backend/.env to enable AI insight generation.",
                "💡 Once configured, PulseBoard will generate 3-5 actionable insights every week.",
                "🎯 Insights are based on week-over-week metric changes in your uploaded data.",
            ],
            "deltas": {},
        }

    try:
        result = generate_weekly_insights(csv_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {str(e)}")


@app.post("/root-cause")
async def root_cause_analysis(req: RootCauseRequest):
    """
    'Why did this happen?' — LLM correlation analysis for a specific metric.
    """
    import google.generativeai as genai

    csv_path = get_csv_path(req.session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    if not os.getenv("GEMINI_API_KEY"):
        return {
            "analysis": "Set GEMINI_API_KEY in backend/.env to enable root cause analysis."
        }

    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        schema = _schema_cache.get(req.session_id) or detect_schema(req.session_id)

        col_summary = "\n".join(
            f"  - {c['name']}: {df[c['name']].describe().to_dict() if c['name'] in df.columns else 'N/A'}"
            for c in schema["columns"][:10]
        )

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""You are a data analyst. A startup founder is asking "Why did {req.column} change?"

Dataset summary (column statistics):
{col_summary}

Chart context: {req.chart_context}

Provide 2-3 possible reasons for the change in {req.column}, based on correlations with other columns.
Be specific and actionable. Use simple language. Start each reason with a number (1., 2., 3.)."""

        response = model.generate_content(prompt)
        return {"analysis": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Root cause analysis failed: {str(e)}")
