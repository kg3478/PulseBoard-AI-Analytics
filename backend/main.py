"""
main.py — PulseBoard FastAPI backend.
All routes: /upload, /query, /anomalies, /insights, /root-cause

v2.1: PM Analytics Layer added.
  - /upload returns dataset_type + pm_queries
  - /query auto-routes PM intents to pm_analytics engine
  - All existing routes unchanged
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

load_dotenv()

app = FastAPI(
    title="PulseBoard API",
    description="Local NL-powered analytics backend — no external API dependencies",
    version="2.1.0",
)

# CORS — wildcard with credentials=False is valid and simplest
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


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "PulseBoard API",
        "version": "2.1.0",
        "mode": "fully-local",
        "features": ["nl-to-sql", "pm-analytics", "anomaly-detection", "insights"],
    }


@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file. Returns session_id, schema, starter_questions,
    dataset_type (product_analytics/financial/marketing/generic),
    and pm_queries (5 smart PM-context-aware query suggestions).
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

        return {
            "session_id":      session_id,
            "filename":        file.filename,
            "schema":          schema,
            "starter_questions": questions,
            "dataset_type":    dataset_type,
            "pm_queries":      pm_queries,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/query")
async def run_nl_query(req: QueryRequest):
    """
    Convert a natural language question to SQL (or PM analytics) and execute it.
    PM queries (funnel, cohort, retention, activation, DAU) are auto-routed to
    the pm_analytics engine without SQL generation.
    """
    schema = _schema_cache.get(req.session_id)
    if not schema:
        csv_path = get_csv_path(req.session_id)
        if not csv_path.exists():
            raise HTTPException(status_code=404, detail="Session not found. Please re-upload your CSV.")
        schema = detect_schema(req.session_id)
        _schema_cache[req.session_id] = schema

    dataset_type = _dataset_type_cache.get(req.session_id) or detect_dataset_type(schema)

    # Parse NL — detects SQL vs PM intent
    from nl_engine import parse_nl_query
    parse_result = parse_nl_query(req.question, schema)

    # ── PM Analytics routing ────────────────────────────────────────────────
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
                "error": pm_res.get("fallback_message", "PM query failed"),
                "sql": "",
                "attempts": 1,
                "pm_query": True,
                "example_queries": pm_res.get("example_queries", []),
            })

        return {
            "success":        True,
            "question":       req.question,
            "sql":            f"-- PM Analytics: {parse_result['pm_intent']}",
            "result":         pm_res,
            "attempts":       1,
            "pm_query":       True,
            "pm_intent":      parse_result["pm_intent"],
            "dataset_type":   dataset_type,
            "example_queries": parse_result.get("example_queries", []),
        }

    # ── Standard SQL routing ──────────────────────────────────────────────────
    def executor(sql: str):
        return execute_sql(req.session_id, sql)

    result = nl_to_sql_with_retry(req.question, schema, executor)

    if not result["success"]:
        return JSONResponse(status_code=422, content={
            "success":         False,
            "error":           result.get("error", "Query failed"),
            "sql":             result.get("sql", ""),
            "attempts":        result.get("attempts", 1),
            "fallback_message": result.get("fallback_message"),
            "example_queries": result.get("example_queries", []),
        })

    return {
        "success":       True,
        "question":      req.question,
        "sql":           result["sql"],
        "result":        result["result"],
        "attempts":      result["attempts"],
        "warning":       result.get("warning"),
        "pm_query":      False,
        "dataset_type":  dataset_type,
        "example_queries": result.get("example_queries", []),
    }


@app.get("/anomalies/{session_id}")
async def get_anomalies(session_id: str):
    """
    Run Z-score anomaly detection on all numeric columns.
    Returns ranked list of anomaly alerts (Critical first).
    Fully local — no external dependencies.
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
    Generate deterministic weekly insight summary.
    Returns 3-5 plain-English bullet points + metric deltas table.
    Fully local — no external API calls.
    """
    csv_path = get_csv_path(session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        result = generate_weekly_insights(csv_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Insight generation failed: {str(e)}")


@app.post("/root-cause")
async def root_cause_analysis(req: RootCauseRequest):
    """
    'Why did this happen?' — Local statistical correlation analysis.

    Replaces the previous LLM-based approach with Pearson correlation:
    Identifies which other numeric columns in the dataset correlate most
    strongly with the target metric and surfaces them as numbered findings.

    Returns:
    - analysis: str — 2-3 numbered correlation-based insights
    - correlations: list — ranked correlation data for transparency
    """
    csv_path = get_csv_path(req.session_id)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        df = pd.read_csv(csv_path)
        schema = _schema_cache.get(req.session_id) or detect_schema(req.session_id)

        # Validate target column exists
        if req.column not in df.columns:
            # Try case-insensitive match
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

        # Compute Pearson correlation with all other numeric columns
        correlations = []
        target_series = df[target_col].dropna()

        for col in numeric_cols:
            if col == target_col:
                continue
            try:
                other = df[col].dropna()
                # Align indices
                aligned = pd.concat([target_series, other], axis=1).dropna()
                if len(aligned) < 5:
                    continue
                r = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
                if not np.isnan(r):
                    correlations.append({
                        "column": col,
                        "r": round(r, 3),
                        "abs_r": round(abs(r), 3),
                        "direction": "positive" if r > 0 else "negative",
                        "strength": _correlation_strength(abs(r)),
                    })
            except Exception:
                continue

        # Sort by absolute correlation (strongest first)
        correlations.sort(key=lambda x: x["abs_r"], reverse=True)
        top = correlations[:3]

        # Generate numbered analysis text
        analysis_lines = _format_correlation_analysis(target_col, top, req.chart_context)

        return {
            "analysis": "\n\n".join(analysis_lines),
            "correlations": correlations[:5],  # Return top 5 for transparency
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Root cause analysis failed: {str(e)}",
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _correlation_strength(abs_r: float) -> str:
    """Classify Pearson r into human-readable strength labels."""
    if abs_r >= 0.8:
        return "very strong"
    if abs_r >= 0.6:
        return "strong"
    if abs_r >= 0.4:
        return "moderate"
    if abs_r >= 0.2:
        return "weak"
    return "very weak"


def _format_correlation_analysis(target: str, top_corr: list, context: str) -> list[str]:
    """Format top correlations as numbered plain-English sentences."""
    if not top_corr:
        return [
            f"No significant correlations found for '{target}' with other numeric columns. "
            "Consider uploading more data or checking if related metrics exist in your dataset."
        ]

    lines = []
    for i, corr in enumerate(top_corr, 1):
        col    = corr["column"]
        r      = corr["r"]
        strength = corr["strength"]
        direction = corr["direction"]

        if direction == "positive":
            relation = f"moves together with **{col}** (r={r:.2f})"
            implication = f"when {col} rises, {target} tends to rise too"
        else:
            relation = f"moves inversely with **{col}** (r={r:.2f})"
            implication = f"when {col} increases, {target} tends to decrease"

        lines.append(
            f"{i}. **{target}** has a {strength} {direction} correlation and {relation} — "
            f"{implication}."
        )

    # Add context note if provided
    if context:
        lines.append(
            f"\n📊 *Query context: {context}*"
        )

    # Add a "no strong correlations" note if all are weak
    if all(c["abs_r"] < 0.3 for c in top_corr):
        lines.append(
            "\nℹ️ All correlations are weak — changes in this metric may be driven by "
            "external factors not captured in the current dataset."
        )

    return lines
