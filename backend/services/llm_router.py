"""
services/llm_router.py — Hybrid LLM routing layer for PulseBoard.

Responsibilities:
  1. Detect whether a query needs LLM (confidence-based + intent-based)
  2. Call Gemini 2.0 Flash with schema-anchored prompts
  3. Generate LLM insights from a statistical data summary (never raw data)
  4. Enforce a session-level call cap to minimize cost

Triggers LLM ONLY when:
  - Rule engine confidence == 0.0 (complete fallback)
  - Query contains explicit EDA/open-ended intent keywords
  - Schema is ambiguous (no numeric columns)

Cost safeguards:
  - Raw data is NEVER sent to Gemini (only schema + 5 sample rows)
  - 50-call cap per session stored in module-level dict
  - Uses gemini-2.0-flash (cheapest/fastest model)
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── EDA Intent Keywords ──────────────────────────────────────────────────────

_EDA_KEYWORDS = {
    "summarize", "summary", "overview", "describe", "profile",
    "what insights", "find patterns", "interesting patterns",
    "correlations", "correlation", "correlate",
    "distribution", "distributions", "histogram",
    "missing values", "missing data", "null values", "data quality",
    "outliers", "anomalies in data",
    "explore", "eda", "exploratory",
    "what can you tell me", "tell me about this data",
    "what is in this", "analyze this", "analyse this",
}

# ─── Session Call Counter ─────────────────────────────────────────────────────

_session_call_counts: dict[str, int] = {}
MAX_LLM_CALLS_PER_SESSION = 50


def _check_and_increment(session_id: str) -> bool:
    """Returns True if the call is allowed; False if cap exceeded."""
    count = _session_call_counts.get(session_id, 0)
    if count >= MAX_LLM_CALLS_PER_SESSION:
        return False
    _session_call_counts[session_id] = count + 1
    return True


# ─── Intent Detection ─────────────────────────────────────────────────────────

def detect_eda_intent(question: str) -> bool:
    """Return True if the question is EDA/open-ended and should bypass rule engine."""
    q = question.lower().strip()
    # Check exact keyword matches
    for kw in _EDA_KEYWORDS:
        if kw in q:
            return True
    # Regex patterns for open-ended phrasing
    open_ended = re.compile(
        r"\b(what('s| is)|tell me|show me|find|explain|why|how does|summarize|describe)\b"
        r".*\b(data|dataset|columns?|pattern|insight|trend|interesting)\b", re.I
    )
    return bool(open_ended.search(q))


def should_use_llm(parse_result: dict, question: str, schema: dict) -> bool:
    """
    Decide whether to invoke the LLM for a given query + parse result.

    Returns True when:
    - Parse completely failed (confidence == 0 / fallback == True)
    - Query is EDA/open-ended
    - Schema has no numeric columns (rule engine can't help)
    """
    if not os.getenv("GEMINI_API_KEY"):
        return False
    if parse_result.get("fallback") and detect_eda_intent(question):
        return True
    if parse_result.get("confidence", 1.0) == 0.0:
        return True
    numeric_cols = [c for c in schema.get("columns", []) if c["type"] == "numeric"]
    if not numeric_cols and parse_result.get("fallback"):
        return True
    return False


# ─── Gemini Client (lazy init) ───────────────────────────────────────────────

_gemini_client = None


def _get_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        _gemini_client = genai.Client(api_key=api_key)
        return _gemini_client
    except ImportError:
        logger.warning("google-genai not installed. LLM features disabled.")
        return None
    except Exception as e:
        logger.warning(f"Gemini init failed: {e}")
        return None


# ─── Schema Summarizer (for prompts) ─────────────────────────────────────────

def _build_schema_summary(schema: dict) -> str:
    """Build a compact schema string to include in LLM prompts."""
    cols = schema.get("columns", [])
    col_lines = []
    for c in cols:
        t = c["type"]
        extra = ""
        if t == "numeric":
            mn = c.get("value_range", {}).get("min", "")
            mx = c.get("value_range", {}).get("max", "")
            if mn != "" and mx != "":
                extra = f" [min={mn}, max={mx}]"
        elif t == "text":
            sample = c.get("sample_values", [])
            if sample:
                extra = f" [e.g. {', '.join(str(s) for s in sample[:3])}]"
        col_lines.append(f"  - {c['name']} ({t}){extra}")
    sample_rows = schema.get("sample", [])[:3]
    sample_str = ""
    if sample_rows:
        sample_str = "\nSample rows (first 3):\n"
        for row in sample_rows:
            sample_str += "  " + ", ".join(f"{k}={v}" for k, v in list(row.items())[:6]) + "\n"
    return f"Columns ({len(cols)} total):\n" + "\n".join(col_lines) + sample_str


# ─── SQL Generation via LLM ──────────────────────────────────────────────────

_SQL_SYSTEM_PROMPT = """You are a data analyst expert in DuckDB SQL.
Given a CSV schema and a user question, write a single DuckDB SQL query.

Rules:
- Table name is always 'data'
- Use only SELECT statements (no INSERT/UPDATE/DROP/CREATE)
- LIMIT results to 500 rows max
- Use double-quotes for column names with spaces or special characters
- Return ONLY the SQL query — no explanation, no markdown fences
- If the question is unanswerable with SQL, return: SELECT * FROM data LIMIT 10
"""


def call_llm_for_sql(
    question: str,
    schema: dict,
    session_id: str = "default",
) -> dict:
    """
    Call Gemini to generate a SQL query for the given question + schema.

    Returns:
        {
            sql: str,
            explanation: str,
            source: "llm",
            success: bool,
            error: str | None,
        }
    """
    client = _get_client()
    if not client:
        return {"sql": "", "explanation": "", "source": "llm", "success": False,
                "error": "LLM unavailable (no API key or package not installed)"}

    if not _check_and_increment(session_id):
        return {"sql": "", "explanation": "", "source": "llm", "success": False,
                "error": f"LLM call cap reached ({MAX_LLM_CALLS_PER_SESSION}/session). Rule engine only."}

    schema_summary = _build_schema_summary(schema)
    prompt = (
        f"{_SQL_SYSTEM_PROMPT}\n\n"
        f"Schema:\n{schema_summary}\n\n"
        f"Question: {question}\n\n"
        f"SQL:"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        # Strip markdown fences if present
        sql = re.sub(r"^```(?:sql)?\n?", "", raw, flags=re.I)
        sql = re.sub(r"\n?```$", "", sql).strip()
        if not sql.upper().startswith("SELECT"):
            sql = "SELECT * FROM data LIMIT 10"
        return {"sql": sql, "explanation": "", "source": "llm", "success": True, "error": None}
    except Exception as e:
        logger.error(f"LLM SQL generation failed: {e}")
        return {"sql": "", "explanation": "", "source": "llm", "success": False, "error": str(e)}


# ─── Insight Generation via LLM ──────────────────────────────────────────────

_INSIGHT_SYSTEM_PROMPT = """You are a senior data analyst.
Given a statistical summary of a dataset, generate 3-5 concise, actionable insight bullets.

Rules:
- Each bullet must be specific (mention column names, numbers where known)
- Use plain English — no jargon
- Focus on: trends, outliers, correlations, anomalies, opportunities
- Start each bullet with a relevant emoji
- Return ONLY the bullet list, one per line, no headers
"""


def call_llm_for_insights(
    data_summary: str,
    dataset_type: str,
    session_id: str = "default",
) -> list[str]:
    """
    Call Gemini to generate insight bullets from a statistical data summary.
    Raw data is NEVER sent — only aggregated summary stats.

    Returns list of insight strings, or [] on failure.
    """
    client = _get_client()
    if not client:
        return []

    if not _check_and_increment(session_id):
        return []

    prompt = (
        f"{_INSIGHT_SYSTEM_PROMPT}\n\n"
        f"Dataset type: {dataset_type}\n\n"
        f"Statistical summary:\n{data_summary}\n\n"
        f"Insights:"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip()
        bullets = [line.strip() for line in raw.split("\n") if line.strip()]
        return bullets[:5]
    except Exception as e:
        logger.error(f"LLM insight generation failed: {e}")
        return []


def call_llm_for_query_explanation(
    question: str,
    schema: dict,
    session_id: str = "default",
) -> str:
    """
    For open-ended / EDA queries that can't be answered with SQL,
    return a natural-language analysis of what the data shows.
    """
    client = _get_client()
    if not client:
        return ""

    if not _check_and_increment(session_id):
        return ""

    schema_summary = _build_schema_summary(schema)
    prompt = (
        "You are a data analyst. Based on this dataset schema, answer the user's question "
        "with a concise, structured analysis. Focus on what they can learn from the data.\n\n"
        f"Schema:\n{schema_summary}\n\n"
        f"Question: {question}\n\n"
        "Answer (3-5 sentences, plain English):"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"LLM explanation failed: {e}")
        return ""


def llm_available() -> bool:
    """Quick check if LLM is configured and ready."""
    return _get_client() is not None
