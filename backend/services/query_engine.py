"""
query_engine.py — DuckDB-based CSV query execution and schema detection.
Handles: file storage, schema auto-detection, query execution, chart type suggestion.

v3.0: Enriched schema detection returns null_counts, unique_counts,
      value_range (numeric), sample_values (text) for LLM context.
      EDA starter questions added for universal dataset coverage.
"""

import os
import uuid
import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def save_csv(file_bytes: bytes, filename: str) -> str:
    """Save uploaded CSV to disk, return session_id."""
    session_id = str(uuid.uuid4())
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    file_path = session_dir / "data.csv"
    file_path.write_bytes(file_bytes)
    return session_id


def get_csv_path(session_id: str) -> Path:
    return UPLOAD_DIR / session_id / "data.csv"


def detect_schema(session_id: str) -> dict:
    """
    Auto-detect schema: column names, inferred types (date/numeric/text),
    row count, sample data, and enriched per-column metadata for LLM prompts.

    Returns per-column:
      - null_count, null_pct
      - unique_count
      - value_range {min, max} for numeric cols
      - sample_values (top 5 unique) for text cols
    """
    path = get_csv_path(session_id)
    df = pd.read_csv(path, nrows=500)
    n = len(df)

    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_count = int(df[col].isna().sum())

        if "int" in dtype or "float" in dtype:
            col_type = "numeric"
        elif "datetime" in dtype:
            col_type = "date"
        else:
            try:
                pd.to_datetime(df[col].dropna().iloc[:5], infer_datetime_format=True)
                col_type = "date"
            except Exception:
                col_type = "text"

        entry: dict = {
            "name":       col,
            "type":       col_type,
            "null_count": null_count,
            "null_pct":   round(null_count / n * 100, 1) if n > 0 else 0,
            "unique_count": int(df[col].nunique(dropna=True)),
        }

        if col_type == "numeric":
            series = df[col].dropna()
            entry["value_range"] = {
                "min": _safe_scalar(series.min()),
                "max": _safe_scalar(series.max()),
            }
        elif col_type == "text":
            top = df[col].dropna().value_counts().head(5).index.tolist()
            entry["sample_values"] = [str(v) for v in top]

        columns.append(entry)

    sample = df.head(5).fillna("").to_dict(orient="records")
    return {
        "columns":   columns,
        "row_count": len(df),
        "sample":    sample,
    }


def suggest_starter_questions(schema: dict) -> list[str]:
    """
    Generate 5 starter questions based on detected schema columns.
    Includes EDA-type questions for universal dataset coverage.
    """
    cols         = schema["columns"]
    numeric_cols = [c["name"] for c in cols if c["type"] == "numeric"]
    date_cols    = [c["name"] for c in cols if c["type"] == "date"]
    text_cols    = [c["name"] for c in cols if c["type"] == "text"]

    questions = []

    if numeric_cols and date_cols:
        questions.append(f"Show me {numeric_cols[0]} over time")
        questions.append(f"Total {numeric_cols[0]} by {text_cols[0] if text_cols else 'category'}")
    elif numeric_cols:
        questions.append(f"What is the sum of {numeric_cols[0]}?")
        if len(numeric_cols) > 1:
            questions.append(f"Compare {numeric_cols[0]} and {numeric_cols[1]}")

    if text_cols and numeric_cols:
        questions.append(f"Which {text_cols[0]} has the highest {numeric_cols[0]}?")
        questions.append(f"Top 10 {text_cols[0]} by {numeric_cols[0]}")

    if date_cols and numeric_cols:
        questions.append(f"Average {numeric_cols[0]} last month")

    # EDA / open-ended fallbacks
    eda_questions = [
        "Summarize this dataset",
        "What are the correlations?",
        "Show me outliers",
        "Show me the top 10 rows",
    ]
    while len(questions) < 5 and eda_questions:
        questions.append(eda_questions.pop(0))

    return questions[:5]


def infer_chart_type(columns: list[dict], rows: list[dict]) -> str:
    """Suggest the best chart type based on result shape."""
    if not rows or not columns:
        return "table"

    col_types = [c.get("type", "text") for c in columns]
    n_numeric = sum(1 for t in col_types if t == "numeric")
    n_text    = sum(1 for t in col_types if t == "text")
    n_date    = sum(1 for t in col_types if t == "date")

    if len(rows) == 1:
        return "table"
    if n_date >= 1 and n_numeric >= 1:
        return "line"
    if n_text >= 1 and n_numeric >= 1 and len(rows) <= 8:
        return "pie" if len(rows) <= 5 else "bar"
    if n_numeric >= 1:
        return "bar"
    return "table"


def execute_sql(session_id: str, sql: str) -> dict:
    """
    Execute SQL against the uploaded CSV using DuckDB.
    Returns: rows, columns with types, chart_type suggestion.
    """
    path = str(get_csv_path(session_id))
    con  = duckdb.connect(database=":memory:")
    con.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{path}')")

    sql_normalized = sql.strip().rstrip(";")
    result = con.execute(sql_normalized).fetchdf()
    con.close()

    columns = []
    for col in result.columns:
        dtype = str(result[col].dtype)
        if "int" in dtype or "float" in dtype:
            col_type = "numeric"
        elif "datetime" in dtype:
            col_type = "date"
        else:
            col_type = "text"
        columns.append({"name": col, "type": col_type})

    rows       = result.fillna("").to_dict(orient="records")
    chart_type = infer_chart_type(columns, rows)

    return {
        "columns":   columns,
        "rows":      rows,
        "chart_type": chart_type,
        "row_count": len(rows),
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_scalar(val) -> float:
    try:
        f = float(val)
        return round(f, 4) if not (np.isnan(f) or np.isinf(f)) else 0.0
    except Exception:
        return 0.0
