"""
services/pm_analytics.py — PM Analytics Engine for PulseBoard.

Provides product-manager-focused analytics:
  - Dataset type detection (product / financial / marketing / ecommerce / hr / generic)
  - Smart query suggestions per dataset type (including EDA queries for generic)
  - DAU / WAU / MAU computation
  - Activation rate
  - Funnel analysis (sequential conversion)
  - Cohort / retention analysis

v3.0: Added ecommerce + hr dataset types. Generic type now suggests EDA queries.
Single file. No sub-packages. No external APIs. Pure pandas + regex.
"""

import re
import pandas as pd
import numpy as np
from typing import Optional

# ─── Column Hint Sets ────────────────────────────────────────────────────────

_USER_HINTS   = {"user_id","user","uid","customer_id","member_id","account_id","visitor_id","userid","user_key"}
_EVENT_HINTS  = {"event","event_name","event_type","action","activity","type","event_category","interaction"}
_TIME_HINTS   = {"timestamp","created_at","occurred_at","event_time","ts","time","datetime","event_date","date","created"}
_FINANCIAL    = {"revenue","mrr","arr","profit","sales","income","billing","amount","ltv","arpu","gmv"}
_MARKETING    = {"clicks","impressions","ctr","cpc","cpm","roas","spend","ad_spend","reach","conversions","leads","sessions"}
_ECOMMERCE    = {"order_id","order","product_id","sku","quantity","unit_price","cart","checkout","shipping","discount_code"}
_HR           = {"employee_id","employee","salary","hire_date","department","designation","headcount","attrition","tenure"}


# ─── 1. Dataset Type Detection ───────────────────────────────────────────────

def detect_dataset_type(schema: dict) -> str:
    """
    Inspect schema column names and return dataset category.
    Order matters: more specific types are checked first.
    """
    names = {c["name"].lower().replace(" ", "_") for c in schema.get("columns", [])}
    has_user  = bool(names & _USER_HINTS)
    has_event = bool(names & _EVENT_HINTS)
    has_time  = bool(names & _TIME_HINTS)
    if has_user and (has_event or has_time):
        return "product_analytics"
    if names & _HR:
        return "hr"
    if names & _ECOMMERCE:
        return "ecommerce"
    if names & _FINANCIAL:
        return "financial"
    if names & _MARKETING:
        return "marketing"
    return "generic"


def _find_col(df: pd.DataFrame, hints: set) -> Optional[str]:
    lower_map = {c.lower().replace(" ", "_"): c for c in df.columns}
    for h in hints:
        if h in lower_map:
            return lower_map[h]
    return None


# ─── 2. Smart Query Suggestions ──────────────────────────────────────────────

def suggest_pm_queries(dataset_type: str, schema: dict) -> list[str]:
    cols    = schema.get("columns", [])
    numeric = [c["name"] for c in cols if c["type"] == "numeric"]
    text_   = [c["name"] for c in cols if c["type"] == "text"]
    m = numeric[0] if numeric else "value"
    d = text_[0]   if text_   else "category"

    if dataset_type == "product_analytics":
        return [
            "Show me daily active users",
            "What is our activation rate?",
            "Funnel from signup to purchase",
            "Weekly retention cohort",
            "Which events have the highest drop-off?",
        ]
    if dataset_type == "financial":
        return [
            f"Show me {m} trend over time",
            f"Top 10 {d} by {m}",
            f"Week-over-week {m} change",
            f"Average {m} by {d}",
            f"Total {m} last month",
        ]
    if dataset_type == "marketing":
        return [
            "Show me CTR by channel",
            "Top 5 campaigns by conversions",
            "Impressions trend over time",
            "Cost per click by campaign",
            "ROAS by ad group",
        ]
    if dataset_type == "ecommerce":
        return [
            f"Top 10 products by revenue",
            f"Orders trend over time",
            f"Average order value by {d}",
            f"Total {m} last month",
            f"Which {d} has the most orders?",
        ]
    if dataset_type == "hr":
        return [
            f"Average salary by department",
            f"Headcount by department",
            f"Show me attrition trend over time",
            f"Top 10 departments by {m}",
            f"What is the average tenure?",
        ]
    # generic — mix of SQL and EDA queries
    return [
        f"Show me {m} by {d}",
        f"Top 10 {d} by {m}",
        "Summarize this dataset",
        "What are the correlations?",
        "Show me outliers",
    ]


# ─── 3. DAU / WAU / MAU ──────────────────────────────────────────────────────

def compute_dau_wau_mau(df: pd.DataFrame, date_col: str, user_col: str) -> dict:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, user_col])

    max_date = df[date_col].max()
    recent   = df[df[date_col] >= max_date - pd.Timedelta(days=30)]

    dau = (
        recent.groupby(recent[date_col].dt.date)[user_col]
        .nunique().reset_index()
        .rename(columns={date_col: "date", user_col: "dau"})
    )
    dau["date"] = dau["date"].astype(str)

    wau = df.groupby(df[date_col].dt.to_period("W"))[user_col].nunique()
    mau = df.groupby(df[date_col].dt.to_period("M"))[user_col].nunique()

    summary = {
        "current_dau":   int(dau["dau"].iloc[-1]) if len(dau) > 0 else 0,
        "avg_wau":       int(wau.mean())           if len(wau) > 0 else 0,
        "avg_mau":       int(mau.mean())           if len(mau) > 0 else 0,
        "dau_wau_ratio": round(
            float(dau["dau"].iloc[-1] / wau.iloc[-1])
            if len(wau) > 0 and wau.iloc[-1] > 0 else 0, 3
        ),
    }
    rows    = dau.to_dict(orient="records")
    columns = [{"name": "date", "type": "date"}, {"name": "dau", "type": "numeric"}]
    return {"rows": rows, "columns": columns, "chart_type": "line",
            "row_count": len(rows), "pm_data": {"type": "dau_wau_mau", "summary": summary}}


# ─── 4. Activation Rate ──────────────────────────────────────────────────────

def compute_activation_rate(df: pd.DataFrame, user_col: str,
                             event_col: str, activation_event: Optional[str] = None) -> dict:
    total = df[user_col].nunique()
    if total == 0:
        return _pm_error("No users found.")

    if activation_event is None:
        counts = df[event_col].value_counts()
        activation_event = counts.index[1] if len(counts) >= 2 else counts.index[0]

    activated = df[df[event_col].str.lower() == activation_event.lower()][user_col].nunique()
    rate      = round(activated / total * 100, 1)

    rows    = [{"segment": "Activated", "users": activated, "pct": rate},
               {"segment": "Not Activated", "users": total - activated, "pct": round(100 - rate, 1)}]
    columns = [{"name": "segment", "type": "text"},
               {"name": "users",   "type": "numeric"},
               {"name": "pct",     "type": "numeric"}]
    return {"rows": rows, "columns": columns, "chart_type": "pie", "row_count": 2,
            "pm_data": {"type": "activation_rate", "activation_event": activation_event,
                        "rate": rate, "total_users": total, "activated": activated}}


# ─── 5. Funnel Analysis ──────────────────────────────────────────────────────

def compute_funnel(df: pd.DataFrame, user_col: str, event_col: str, steps: list[str]) -> dict:
    if not steps:
        return _pm_error("No funnel steps provided.")
    if user_col not in df.columns or event_col not in df.columns:
        return _pm_error(f"Funnel requires '{user_col}' and '{event_col}' columns.")

    results    = []
    prev_users = None

    for i, step in enumerate(steps):
        step_users = set(
            df[df[event_col].str.lower().str.contains(step.lower(), na=False)][user_col]
        )
        if prev_users is not None:
            step_users = step_users & prev_users

        count      = len(step_users)
        first_cnt  = results[0]["users"] if results else count
        conv_rate  = round(count / first_cnt * 100, 1) if first_cnt > 0 else 0
        drop_off   = 0.0
        if i > 0 and results:
            pc = results[i - 1]["users"]
            drop_off = round((pc - count) / pc * 100, 1) if pc > 0 else 0

        results.append({"step": step, "users": count,
                         "conversion_rate": conv_rate, "drop_off": drop_off})
        prev_users = step_users

    columns = [{"name": "step",            "type": "text"},
               {"name": "users",           "type": "numeric"},
               {"name": "conversion_rate", "type": "numeric"},
               {"name": "drop_off",        "type": "numeric"}]
    pm_data = {"type": "funnel", "steps": steps,
               "user_counts":      [r["users"]           for r in results],
               "conversion_rates": [r["conversion_rate"] for r in results],
               "drop_offs":        [r["drop_off"]        for r in results],
               "overall_conversion": results[-1]["conversion_rate"] if results else 0}
    return {"rows": results, "columns": columns, "chart_type": "funnel",
            "row_count": len(results), "pm_data": pm_data}


# ─── 6. Cohort / Retention Analysis ─────────────────────────────────────────

def compute_cohort(df: pd.DataFrame, user_col: str,
                   date_col: str, period: str = "week") -> dict:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, user_col])

    if len(df) < 10:
        return _pm_error("Not enough data for cohort analysis (need ≥ 10 rows).")

    df["_period"] = (df[date_col].dt.to_period("W") if period == "week"
                     else df[date_col].dt.to_period("M"))

    user_cohort = (df.groupby(user_col)["_period"].min()
                   .reset_index().rename(columns={"_period": "cohort"}))
    df = df.merge(user_cohort, on=user_col)
    df["_age"] = (df["_period"] - df["cohort"]).apply(lambda x: x.n if hasattr(x, "n") else 0)

    max_age  = min(int(df["_age"].max()), 8)
    cohorts  = []

    for cohort_val, cdf in df.groupby("cohort"):
        cohort_users = set(cdf[user_col])
        size = len(cohort_users)
        if size < 3:
            continue
        row = {"cohort": str(cohort_val), "cohort_size": size}
        for age in range(max_age + 1):
            age_users = set(cdf[cdf["_age"] == age][user_col])
            row[f"week_{age}"] = round(len(age_users) / size * 100, 1)
        cohorts.append(row)

    if not cohorts:
        return _pm_error("Could not compute cohort data — check user_id and date columns.")

    cohorts  = cohorts[-8:]
    week_cols = [f"week_{i}" for i in range(max_age + 1)]
    columns  = ([{"name": "cohort", "type": "text"}, {"name": "cohort_size", "type": "numeric"}]
                + [{"name": c, "type": "numeric"} for c in week_cols])
    return {"rows": cohorts, "columns": columns, "chart_type": "cohort",
            "row_count": len(cohorts),
            "pm_data": {"type": "cohort", "period": period,
                        "num_cohorts": len(cohorts), "max_periods": max_age}}


# ─── 7. Main Query Router ────────────────────────────────────────────────────

def run_pm_query(question: str, df: pd.DataFrame, schema: dict, dataset_type: str) -> dict:
    q         = question.lower()
    user_col  = _find_col(df, _USER_HINTS)
    event_col = _find_col(df, _EVENT_HINTS)
    date_col  = _find_col(df, _TIME_HINTS)

    if dataset_type != "product_analytics" and not (user_col and date_col):
        examples = suggest_pm_queries(dataset_type, schema)
        return {"rows": [], "columns": [], "chart_type": "table", "row_count": 0,
                "pm_data": {"type": "error"}, "fallback": True,
                "fallback_message": (
                    f"This query needs user_id and event data. "
                    f"Your dataset looks like '{dataset_type}'. Try: '{examples[0]}'"
                ), "example_queries": examples}

    # DAU / WAU / MAU
    if re.search(r"\b(dau|wau|mau|daily active|weekly active|monthly active|active users)\b", q):
        if user_col and date_col:
            return compute_dau_wau_mau(df, date_col, user_col)
        return _pm_error("Need user_id and date columns for DAU/WAU/MAU.", schema)

    # Funnel
    if re.search(r"\b(funnel|conversion|drop.?off|journey|steps?|flow)\b", q):
        steps = extract_funnel_steps(question)
        if not steps and event_col:
            steps = df[event_col].value_counts().head(3).index.tolist()
        if steps and user_col and event_col:
            return compute_funnel(df, user_col, event_col, steps)
        return _pm_error("Need user_id and event columns for funnel analysis.", schema)

    # Cohort / Retention
    if re.search(r"\b(cohort|retention|retained|returning|churn)\b", q):
        period = "month" if "month" in q else "week"
        if user_col and date_col:
            return compute_cohort(df, user_col, date_col, period)
        return _pm_error("Need user_id and date columns for cohort analysis.", schema)

    # Activation
    if re.search(r"\b(activation|activated|onboard|onboarding|first action)\b", q):
        act_event = _extract_event_from_query(q, df, event_col)
        if user_col and event_col:
            return compute_activation_rate(df, user_col, event_col, act_event)
        return _pm_error("Need user_id and event columns for activation rate.", schema)

    examples = suggest_pm_queries(dataset_type, schema)
    return {"rows": [], "columns": [], "chart_type": "table", "row_count": 0,
            "pm_data": {"type": "error"}, "fallback": True,
            "fallback_message": "Couldn't determine the PM metric. Try one of these:",
            "example_queries": examples}


# ─── 8. Utilities ────────────────────────────────────────────────────────────

def extract_funnel_steps(question: str) -> list[str]:
    # Arrow style: signup → activate → purchase
    if re.search(r"→|->|=>", question):
        parts = re.split(r"→|->|=>", question)
        steps = [_clean_step(p) for p in parts if _clean_step(p)]
        if len(steps) >= 2:
            return steps
    # "from X to Y"
    m = re.search(r"from\s+([\w_]+)\s+to\s+([\w_]+)", question, re.I)
    if m:
        return [m.group(1).lower(), m.group(2).lower()]
    # "X then Y"
    parts = re.split(r"\s+then\s+", question, flags=re.I)
    if len(parts) >= 2:
        steps = [_clean_step(p) for p in parts if _clean_step(p)]
        if len(steps) >= 2:
            return steps
    # Common defaults
    if re.search(r"signup.*purchase|sign.?up.*buy", question, re.I):
        return ["signup", "activate", "purchase"]
    return []


def _clean_step(text: str) -> str:
    noise  = {"funnel","for","show","me","the","a","an","conversion","from","to"}
    tokens = re.findall(r"\w+", text.lower())
    clean  = [t for t in tokens if t not in noise and len(t) > 1]
    return "_".join(clean) if clean else ""


def _extract_event_from_query(question: str, df: pd.DataFrame,
                               event_col: Optional[str]) -> Optional[str]:
    if not event_col or event_col not in df.columns:
        return None
    for event in df[event_col].dropna().unique():
        if str(event).lower() in question.lower():
            return str(event)
    return None


def _pm_error(message: str, schema: Optional[dict] = None) -> dict:
    examples = suggest_pm_queries(detect_dataset_type(schema), schema) if schema else []
    return {"rows": [], "columns": [], "chart_type": "table", "row_count": 0,
            "pm_data": {"type": "error"}, "fallback": True,
            "fallback_message": message, "example_queries": examples}
