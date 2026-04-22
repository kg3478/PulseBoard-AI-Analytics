"""
nl_to_sql.py — Natural Language to SQL translation using Gemini API.
Uses gemini-2.0-flash with fallback to gemini-1.5-pro.
"""

import os
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

# Model cascade: newest first, fallback on 404/unavailable
_MODELS = ["gemini-2.0-flash", "gemini-1.5-flash-8b"]


def _get_model(model_name: str):
    return genai.GenerativeModel(model_name)


def _build_system_prompt(schema: dict) -> str:
    col_descriptions = "\n".join(
        f"  - {c['name']} ({c['type']})" for c in schema["columns"]
    )
    return f"""You are a SQL expert. The user has uploaded a CSV file loaded as a DuckDB table named 'data'.

Table schema:
{col_descriptions}

Examples:
  Q: "Show me revenue by city"
  A: SELECT city, SUM(revenue) AS total_revenue FROM data GROUP BY city ORDER BY total_revenue DESC

  Q: "What is the total MRR?"
  A: SELECT SUM(mrr) AS total_mrr FROM data

  Q: "Top 5 rows by sales"
  A: SELECT * FROM data ORDER BY sales DESC LIMIT 5

Rules:
1. Always use table name 'data'.
2. Return ONLY the SQL query — no markdown, no code fences, no explanation.
3. Use DuckDB-compatible SQL syntax.
4. If column name has spaces, wrap in double quotes.
5. LIMIT to 500 rows maximum.
"""


def _extract_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).replace("```", "")
    return text.strip()


def nl_to_sql(question: str, schema: dict, previous_error: str = None) -> str:
    """Convert NL question to SQL with model fallback."""
    system_prompt = _build_system_prompt(schema)
    if previous_error:
        user_message = f"""The previous SQL query failed with:\nError: {previous_error}\n\nFix it. Original question: {question}"""
    else:
        user_message = f"Convert to SQL: {question}"

    full_prompt = f"{system_prompt}\n\nUser: {user_message}"

    last_error = None
    for model_name in _MODELS:
        try:
            model = _get_model(model_name)
            response = model.generate_content(
                full_prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 512},
                request_options={"timeout": 30},
            )
            return _extract_sql(response.text)
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Only try fallback on model-not-found / quota errors
            if any(x in err_str for x in ["404", "not found", "deprecated", "quota", "unavailable"]):
                time.sleep(0.5)
                continue
            # Other errors (network, auth) — raise immediately
            raise

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def nl_to_sql_with_retry(question: str, schema: dict, executor) -> dict:
    """
    Run NL-to-SQL with up to 2 self-correction retries.
    executor: callable(sql) -> dict
    """
    sql = ""
    for attempt in range(1, 3):
        try:
            error_ctx = None if attempt == 1 else last_sql_error
            sql = nl_to_sql(question, schema, previous_error=error_ctx)
            result = executor(sql)
            return {
                "sql": sql,
                "result": result,
                "attempts": attempt,
                "success": True,
            }
        except Exception as e:
            last_sql_error = str(e)
            if attempt == 2:
                return {
                    "sql": sql,
                    "result": None,
                    "attempts": attempt,
                    "success": False,
                    "error": f"Query failed: {last_sql_error}",
                }

    return {"sql": sql, "result": None, "attempts": 2, "success": False, "error": "Query failed."}
