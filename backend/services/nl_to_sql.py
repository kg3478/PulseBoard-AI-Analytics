"""
nl_to_sql.py — Natural Language to SQL using Groq (llama-3.3-70b-versatile).
"""

import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
_MODEL = "llama-3.3-70b-versatile"


def _build_system_prompt(schema: dict) -> str:
    col_descriptions = "\n".join(
        f"  - {c['name']} ({c['type']})" for c in schema["columns"]
    )
    return f"""You are a SQL expert. The user uploaded a CSV file loaded as a DuckDB table named 'data'.

Table schema:
{col_descriptions}

Rules:
1. Always use table name 'data' (never anything else).
2. Return ONLY the raw SQL query — no explanation, no markdown, no code fences, no backticks.
3. Use DuckDB-compatible SQL syntax.
4. If a column name has spaces, wrap it in double quotes.
5. Always add ORDER BY for time-series queries.
6. LIMIT results to 500 rows maximum."""


def _extract_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE).replace("```", "")
    return text.strip()


def nl_to_sql(question: str, schema: dict, previous_error: str = None) -> str:
    system_prompt = _build_system_prompt(schema)

    if previous_error:
        user_message = (
            f"The previous SQL query failed with error:\n{previous_error}\n\n"
            f"Fix it and return ONLY the corrected SQL.\nOriginal question: {question}"
        )
    else:
        user_message = f"Convert this question to SQL: {question}"

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_completion_tokens=512,
            top_p=1,
            stream=False,
        )
        return _extract_sql(response.choices[0].message.content)
    except Exception as e:
        raise Exception(f"Groq NL-to-SQL failed: {e}")


def nl_to_sql_with_retry(question: str, schema: dict, executor) -> dict:
    """Run NL-to-SQL with one self-correction retry."""
    sql = ""
    last_error = None

    for attempt in range(1, 3):
        try:
            sql = nl_to_sql(question, schema, previous_error=last_error)
            result = executor(sql)
            return {
                "sql": sql,
                "result": result,
                "attempts": attempt,
                "success": True,
            }
        except Exception as e:
            last_error = str(e)
            if attempt == 2:
                return {
                    "sql": sql,
                    "result": None,
                    "attempts": attempt,
                    "success": False,
                    "error": f"Query failed after {attempt} attempts: {last_error}",
                }

    return {
        "sql": sql,
        "result": None,
        "attempts": 2,
        "success": False,
        "error": "AI provider temporarily unavailable",
    }
