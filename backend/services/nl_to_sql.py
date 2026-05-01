"""
nl_to_sql.py — Local, deterministic NL-to-SQL engine for PulseBoard.

Replaces the previous Groq/LLM-based approach with a fully local
rule-based parser. Zero API calls. Sub-millisecond execution.

Public API (unchanged — no frontend modifications needed):
    nl_to_sql_with_retry(question, schema, executor) -> dict
"""

from nl_engine import parse_nl_query


def nl_to_sql_with_retry(question: str, schema: dict, executor) -> dict:
    """
    Parse a natural-language question into SQL and execute it.

    This function preserves the original return contract so the frontend
    and main.py require zero changes.

    Returns:
        {
            sql:      str   – Generated SQL query
            result:   dict  – Query result from executor (rows, columns, chart_type)
            attempts: int   – Always 1 (deterministic, no retry needed)
            success:  bool
            error:    str   – Present only on failure
            warning:  str   – Present on low-confidence parse
            fallback_message: str – Present when parse completely fails
            example_queries:  list – Schema-aware suggestions on failure
        }
    """
    # ── Step 1: Parse NL → SQL ────────────────────────────────────────────────
    parse_result = parse_nl_query(question, schema)

    # ── Step 2: Fallback path — parse failed ──────────────────────────────────
    if parse_result["fallback"] or not parse_result["sql"]:
        return {
            "sql": "",
            "result": None,
            "attempts": 1,
            "success": False,
            "error": parse_result.get("fallback_message") or "Could not generate SQL from your query.",
            "fallback_message": parse_result.get("fallback_message"),
            "example_queries": parse_result.get("example_queries", []),
            "warning": None,
        }

    sql = parse_result["sql"]

    # ── Step 3: Execute SQL ───────────────────────────────────────────────────
    try:
        result = executor(sql)
        return {
            "sql": sql,
            "result": result,
            "attempts": 1,
            "success": True,
            "warning": parse_result.get("warning"),
            "template_id": parse_result.get("template_id"),
            "confidence": parse_result.get("confidence"),
            "example_queries": parse_result.get("example_queries", []),
        }
    except Exception as e:
        error_msg = str(e)

        # ── Step 4: SQL execution failed — attempt a safe fallback query ──────
        fallback_sql = _build_safe_fallback(schema)
        if fallback_sql:
            try:
                result = executor(fallback_sql)
                return {
                    "sql": fallback_sql,
                    "result": result,
                    "attempts": 1,
                    "success": True,
                    "warning": (
                        f"Your original query couldn't execute ({error_msg}). "
                        f"Showing a basic overview instead."
                    ),
                    "example_queries": parse_result.get("example_queries", []),
                }
            except Exception:
                pass  # Even the fallback failed — return error below

        return {
            "sql": sql,
            "result": None,
            "attempts": 1,
            "success": False,
            "error": f"Query execution failed: {error_msg}",
            "example_queries": parse_result.get("example_queries", []),
            "warning": None,
        }


def _build_safe_fallback(schema: dict) -> str:
    """Build a guaranteed-safe SELECT * LIMIT 10 as last resort."""
    return "SELECT * FROM data LIMIT 10"
