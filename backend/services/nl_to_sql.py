"""
nl_to_sql.py — Natural Language to SQL translation using Gemini API.
Includes: schema-aware prompt, self-correction retry loop (max 2 attempts).
"""

import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
_model = genai.GenerativeModel("gemini-1.5-flash")


def _build_system_prompt(schema: dict) -> str:
    """Build a schema-aware system prompt for NL-to-SQL."""
    col_descriptions = "\n".join(
        f"  - {c['name']} ({c['type']})" for c in schema["columns"]
    )
    sample_pairs = """
Examples of valid NL → SQL conversions:
  Q: "Show me revenue by city last month"
  A: SELECT city, SUM(revenue) AS total_revenue FROM data WHERE date >= date_trunc('month', current_date - INTERVAL '1 month') GROUP BY city ORDER BY total_revenue DESC

  Q: "What is the total MRR this week?"
  A: SELECT SUM(mrr) AS total_mrr FROM data WHERE date >= current_date - INTERVAL '7 days'

  Q: "Top 5 products by sales"
  A: SELECT product, SUM(sales) AS total_sales FROM data GROUP BY product ORDER BY total_sales DESC LIMIT 5

  Q: "Show me DAU over the last 30 days"
  A: SELECT date, SUM(dau) AS daily_active_users FROM data WHERE date >= current_date - INTERVAL '30 days' GROUP BY date ORDER BY date

  Q: "What is the average churn rate by cohort?"
  A: SELECT cohort, AVG(churn_rate) AS avg_churn FROM data GROUP BY cohort ORDER BY avg_churn DESC
"""
    return f"""You are a SQL expert. The user has uploaded a CSV file loaded as a DuckDB table named 'data'.

Table schema:
{col_descriptions}

{sample_pairs}

Rules:
1. Always use table name 'data' (never anything else).
2. Return ONLY the SQL query — no explanation, no markdown, no code fences.
3. Use DuckDB-compatible SQL syntax.
4. For date filtering, use DuckDB date functions.
5. If a column name has spaces, wrap it in double quotes.
6. Always add ORDER BY for time-series queries.
7. LIMIT results to 500 rows maximum.
"""


def _extract_sql(text: str) -> str:
    """Strip any markdown fences from LLM output."""
    # Remove ```sql ... ``` or ``` ... ```
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).replace("```", "")
    return text.strip()


def nl_to_sql(question: str, schema: dict, previous_error: str = None) -> str:
    """
    Convert a natural language question to SQL.
    If previous_error is provided, include it in the prompt for self-correction.
    Returns the SQL string.
    """
    system_prompt = _build_system_prompt(schema)

    if previous_error:
        user_message = f"""The previous SQL query failed with this error:
Error: {previous_error}

Please fix the query and return ONLY the corrected SQL.
Original question: {question}"""
    else:
        user_message = f"Convert this question to SQL: {question}"

    full_prompt = f"{system_prompt}\n\nUser: {user_message}"

    response = _model.generate_content(full_prompt)
    sql = _extract_sql(response.text)
    return sql


def nl_to_sql_with_retry(question: str, schema: dict, executor) -> dict:
    """
    Run NL-to-SQL with up to 2 self-correction retries.
    executor: callable(sql) -> dict (the query engine)
    Returns: {"sql": str, "result": dict, "attempts": int, "success": bool}
    """
    sql = nl_to_sql(question, schema)
    
    for attempt in range(1, 3):  # Max 2 attempts
        try:
            result = executor(sql)
            return {
                "sql": sql,
                "result": result,
                "attempts": attempt,
                "success": True,
            }
        except Exception as e:
            error_msg = str(e)
            if attempt < 2:
                # Retry with error context
                sql = nl_to_sql(question, schema, previous_error=error_msg)
            else:
                return {
                    "sql": sql,
                    "result": None,
                    "attempts": attempt,
                    "success": False,
                    "error": "I couldn't understand that query — try rephrasing it.",
                }

    return {
        "sql": sql,
        "result": None,
        "attempts": 2,
        "success": False,
        "error": "Query failed after 2 attempts.",
    }
