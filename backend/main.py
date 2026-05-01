"""
main.py — PulseBoard FastAPI backend.

v3.0: Universal AI Data Analysis Platform (Hybrid Intelligence)
  - /upload  → returns dataset_type, pm_queries, eda_summary
  - /query   → hybrid routing: rules → LLM → EDA, returns `source` field
  - /eda     → full Exploratory Data Analysis (local, no LLM)
  - /insights → hybrid: deterministic + LLM bullets
  - /llm-insights → on-demand LLM insight generation
  - /anomalies → Z-score anomaly detection (unchanged)
  - /root-cause → Pearson correlation analysis (unchanged)
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from services.query_engine import (
    save_csv, get_csv_path, detect_schema, suggest_starter_questions, execute_sql,
)
from services.nl_to_sql import nl_to_sql_with_retry
from services.anomaly import detect_anomalies
from services.insights import generate_insights as generate_weekly_insights
from services.pm_analytics import (
    detect_dataset_type, suggest_pm_queries, run_pm_query,
)
from services.eda import run_eda
from services.llm_router import detect_eda_intent, llm_available

load_dotenv()

app = FastAPI(
    title="PulseBoard API",
    description="Universal AI Data Analysis Platform — hybrid rule engine + Gemini LLM",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory caches (session_id → schema/dataset_type)
_schema_cache:       dict[str, dict] = {}
_dataset_type_cache: dict[str, str]  = {}


# ─── Request/Response Models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    session_id: str
    question: str

class RootCauseRequest(BaseModel):
    session_id: str
    column: str
    chart_context: str = ""

class LLMInsightsRequest(BaseModel):
    session_id: str


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status":   "ok",
        "service":  "PulseBoard API",
        "version":  "3.0.0",
        "mode":     "hybrid (rules + Gemini LLM)",
        "llm_ready": llm_available(),
        "features": [
            "nl-to-sql", "llm-fallback", "eda", "pm-analytics",
            "anomaly-detection", "hybrid-insights",
        ],
    }


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file. Returns session_id, schema, starter_questions,
    dataset_type, pm_queries, and lightweight eda_summary.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 50MB.")

    try:
        session_id   = save_csv(contents, file.filename)
        schema       = detect_schema(session_id)
        questions    = suggest_starter_questions(schema)
        dataset_type = detect_dataset_type(schema)
        pm_queries   = suggest_pm_queries(dataset_type, schema)

        _schema_cache[session_id]       = schema
        _dataset_type_cache[session_id] = dataset_type

        # Lightweight EDA summary for the upload response
        eda_summary = {
            "total_rows":       schema["row_count"],
            "total_cols":       len(schema["columns"]),
            "numeric_cols":     sum(1 for c in schema["columns"] if c["type"] == "numeric"),
            "text_cols":        sum(1 for c in schema["columns"] if c["type"] == "text"),
            "date_cols":        sum(1 for c in schema["columns"] if c["type"] == "date"),
            "cols_with_nulls":  sum(1 for c in schema["columns"] if c.get("null_count", 0) > 0),
            "dataset_type":     dataset_type,
        }

        return {
            "session_id":        session_id,
            "filename":          file.filename,
            "schema":            schema,
            "starter_questions": questions,
            "dataset_type":      dataset_type,
            "pm_queries":        pm_queries,
            "eda_summary":       eda_summary,
            "llm_available":     llm_available(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/query")
async def run_nl_query(req: QueryRequest):
    """
    Convert a natural language question to SQL (or PM analytics / EDA) and execute.

    Routing order:
      1. EDA intent detected → run_eda() (local, instant)
      2. PM intent detected  → pm_analytics engine
      3. Rule engine (deterministic NL-to-SQL)
      4. LLM fallback (Gemini) when rule engine confidence == 0
    """
    schema = _schema_cache.get(req.session_id)
    if not schema:
        csv_path = get_csv_path(req.session_id)
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="Session not found. Please re-upload your CSV.")
        schema = detect_schema(req.session_id)
        _schema_cache[req.session_id] = schema

    dataset_type = _dataset_type_cache.get(req.session_id) or detect_dataset_type(schema)

    # ── 1. EDA intent — bypass rule engine entirely ───────────────────────────
    if detect_eda_intent(req.question):
        csv_path = get_csv_path(req.session_id)
        try:
            eda_result = run_eda(csv_path)
            return {
                "success":      True,
                "question":     req.question,
                "sql":          "-- EDA (no SQL)",
                "result":       _eda_to_query_result(eda_result),
                "eda_full":     eda_result,
                "attempts":     1,
                "source":       "eda",
                "pm_query":     False,
                "dataset_type": dataset_type,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"EDA failed: {str(e)}")

    # ── 2. PM analytics routing ───────────────────────────────────────────────
    from nl_engine import parse_nl_query
    parse_result = parse_nl_query(req.question, schema)

    if parse_result.get("pm_query"):
        csv_path = get_csv_path(req.session_id)
        try:
            df     = pd.read_csv(csv_path)
            pm_res = run_pm_query(req.question, df, schema, dataset_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PM analytics failed: {str(e)}")

        if pm_res.get("fallback"):
            return JSONResponse(status_code=422, content={
                "success": False,
                "error":   pm_res.get("fallback_message", "PM query failed"),
                "sql":     "",
                "attempts": 1,
                "source":   "rules",
                "pm_query": True,
                "example_queries": pm_res.get("example_queries", []),
            })

        return {
            "success":       True,
            "question":      req.question,
            "sql":           f"-- PM Analytics: {parse_result['pm_intent']}",
            "result":        pm_res,
            "attempts":      1,
            "source":        "rules",
            "pm_query":      True,
            "pm_intent":     parse_result["pm_intent"],
            "dataset_type":  dataset_type,
            "example_queries": parse_result.get("example_queries", []),
        }

    # ── 3 & 4. Standard SQL routing (rule engine → LLM fallback) ─────────────
    def executor(sql: str):
        return execute_sql(req.session_id, sql)

    result = nl_to_sql_with_retry(
        req.question, schema, executor, session_id=req.session_id
    )

    if not result["success"]:
        return JSONResponse(status_code=422, content={
            "success":          False,
            "error":            result.get("error", "Query failed"),
            "sql":              result.get("sql", ""),
            "attempts":         result.get("attempts", 1),
            "source":           result.get("source", "rules"),
            "fallback_message": result.get("fallback_message"),
            "llm_explanation":  result.get("llm_explanation"),
            "example_queries":  result.get("example_queries", []),
        })

    return {
        "success":         True,
        "question":        req.question,
        "sql":             result["sql"],
        "result":          result["result"],
        "attempts":        result["attempts"],
        "source":          result.get("source", "rules"),
        "warning":         result.get("warning"),
        "pm_query":        False,
        "dataset_type":    dataset_type,
        "llm_explanation": result.get("llm_explanation"),
        "example_queries": result.get("example_queries", []),
    }


@app.get("/eda/{session_id}")
async def get_eda(session_id: str):
    """
    Full Exploratory Data Analysis — column profiles, correlations,
    distributions, missing values, outliers. Fully local, no LLM.
    """
    csv_path = get_csv_path(session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        result = run_eda(csv_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"EDA failed: {str(e)}")


@app.post("/llm-insights")
async def get_llm_insights(req: LLMInsightsRequest):
    """
    On-demand LLM-generated insight bullets from a compact data summary.
    Falls back to empty list if LLM is unavailable.
    Raw data is NEVER sent to the LLM.
    """
    csv_path = get_csv_path(req.session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    schema = _schema_cache.get(req.session_id) or detect_schema(req.session_id)
    dataset_type = _dataset_type_cache.get(req.session_id) or detect_dataset_type(schema)

    try:
        from services.llm_router import call_llm_for_insights
        from services.eda import build_data_summary_for_llm
        summary = build_data_summary_for_llm(csv_path, schema)
        bullets = call_llm_for_insights(summary, dataset_type, session_id=req.session_id)
        return {
            "bullets":      bullets,
            "llm_ready":    llm_available(),
            "dataset_type": dataset_type,
        }
    except Exception as e:
        return {"bullets": [], "llm_ready": False, "error": str(e)}


@app.get("/anomalies/{session_id}")
async def get_anomalies(session_id: str):
    """Z-score anomaly detection on all numeric columns."""
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
    Hybrid insight summary: deterministic WoW bullets + LLM bullets.
    Returns: { bullets, deltas, llm_bullets }
    """
    csv_path = get_csv_path(session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        result = generate_weekly_insights(csv_path, session_id=session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {str(e)}")


@app.post("/root-cause")
async def root_cause_analysis(req: RootCauseRequest):
    """
    'Why did this happen?' — Local Pearson correlation analysis.
    Identifies which numeric columns correlate most strongly with the target metric.
    """
    csv_path = get_csv_path(req.session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        df     = pd.read_csv(csv_path)
        schema = _schema_cache.get(req.session_id) or detect_schema(req.session_id)

        if req.column not in df.columns:
            col_match = next(
                (c for c in df.columns if c.lower() == req.column.lower()), None
            )
            if not col_match:
                return {
                    "analysis": (
                        f"Column '{req.column}' not found in the dataset. "
                        f"Available columns: {', '.join(df.columns.tolist()[:10])}"
                    ),
                    "correlations": [],
                }
            target_col = col_match
        else:
            target_col = req.column

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if target_col not in numeric_cols:
            return {
                "analysis": (
                    f"'{target_col}' is not a numeric column — "
                    "correlation analysis only works on numeric metrics."
                ),
                "correlations": [],
            }

        correlations   = []
        target_series  = df[target_col].dropna()

        for col in numeric_cols:
            if col == target_col:
                continue
            try:
                other   = df[col].dropna()
                aligned = pd.concat([target_series, other], axis=1).dropna()
                if len(aligned) < 5:
                    continue
                r = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
                if not np.isnan(r):
                    correlations.append({
                        "column":    col,
                        "r":         round(r, 3),
                        "abs_r":     round(abs(r), 3),
                        "direction": "positive" if r > 0 else "negative",
                        "strength":  _correlation_strength(abs(r)),
                    })
            except Exception:
                continue

        correlations.sort(key=lambda x: x["abs_r"], reverse=True)
        top      = correlations[:3]
        analysis = _format_correlation_analysis(target_col, top, req.chart_context)

        return {
            "analysis":     "\n\n".join(analysis),
            "correlations": correlations[:5],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Root cause analysis failed: {str(e)}",
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _eda_to_query_result(eda: dict) -> dict:
    """Convert EDA output into the standard query result shape for frontend rendering."""
    profile = eda.get("profile", [])
    rows = []
    for p in profile:
        row: dict = {
            "Column": p["name"],
            "Type":   p["type"],
            "Nulls":  f"{p['null_pct']}%",
            "Unique": p.get("unique", "—"),
        }
        if p["type"] == "numeric":
            row["Min"]  = p.get("min", "")
            row["Max"]  = p.get("max", "")
            row["Mean"] = p.get("mean", "")
        rows.append(row)

    columns = [
        {"name": "Column", "type": "text"},
        {"name": "Type",   "type": "text"},
        {"name": "Nulls",  "type": "text"},
        {"name": "Unique", "type": "numeric"},
        {"name": "Min",    "type": "numeric"},
        {"name": "Max",    "type": "numeric"},
        {"name": "Mean",   "type": "numeric"},
    ]
    return {"columns": columns, "rows": rows, "chart_type": "table", "row_count": len(rows)}


def _correlation_strength(abs_r: float) -> str:
    if abs_r >= 0.8: return "very strong"
    if abs_r >= 0.6: return "strong"
    if abs_r >= 0.4: return "moderate"
    if abs_r >= 0.2: return "weak"
    return "very weak"


def _format_correlation_analysis(target: str, top_corr: list, context: str) -> list[str]:
    if not top_corr:
        return [
            f"No significant correlations found for '{target}' with other numeric columns. "
            "Consider uploading more data or checking if related metrics exist in your dataset."
        ]
    lines = []
    for i, corr in enumerate(top_corr, 1):
        col, r = corr["column"], corr["r"]
        strength, direction = corr["strength"], corr["direction"]
        if direction == "positive":
            relation    = f"moves together with **{col}** (r={r:.2f})"
            implication = f"when {col} rises, {target} tends to rise too"
        else:
            relation    = f"moves inversely with **{col}** (r={r:.2f})"
            implication = f"when {col} increases, {target} tends to decrease"
        lines.append(
            f"{i}. **{target}** has a {strength} {direction} correlation and {relation} — "
            f"{implication}."
        )
    if context:
        lines.append(f"\n📊 *Query context: {context}*")
    if all(c["abs_r"] < 0.3 for c in top_corr):
        lines.append(
            "\nℹ️ All correlations are weak — changes in this metric may be driven by "
            "external factors not captured in the current dataset."
        )
    return lines
