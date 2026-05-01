"""
nl_engine/parser.py — NL-to-SQL orchestrator for PulseBoard.

Consolidates (formerly separate files, now deleted):
  • nl_engine/schema_mapper.py  — column matching + alias table
  • utils/date_parser.py        — time expression → SQL WHERE clause

Pipeline:
  1. Tokenize query
  2. Score all 13 templates (SQL + PM)
  3. If PM template → return pm_query flag (routed in main.py)
  4. Fill slots via schema mapper + date parsing
  5. Render final SQL
  6. Return structured result with confidence + fallback on failure

No external API calls. Fully deterministic. Sub-millisecond on all inputs.
"""

import re
from typing import Optional

from .templates import select_template, quote_col, TEMPLATES


# ─── Confidence Thresholds ────────────────────────────────────────────────────
CONFIDENCE_HIGH = 0.5   # Generate SQL confidently
CONFIDENCE_LOW  = 0.15  # Generate SQL with warning; below this → fallback


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION A — SCHEMA MAPPER (merged from schema_mapper.py)
# ═══════════════════════════════════════════════════════════════════════════════

METRIC_ALIASES: dict[str, list[str]] = {
    "revenue":  ["sales", "income", "amount", "total", "earnings", "gmv", "turnover", "billing", "billed"],
    "profit":   ["margin", "net", "gain", "surplus"],
    "orders":   ["transactions", "purchases", "bookings", "deals", "conversions", "sales"],
    "users":    ["customers", "clients", "members", "signups", "visitors", "accounts", "people"],
    "sessions": ["visits", "views", "pageviews", "hits"],
    "cost":     ["expense", "spend", "expenditure", "cogs", "opex"],
    "quantity": ["qty", "units", "count", "volume", "number"],
    "price":    ["rate", "fee", "charge", "unit_price", "value", "fare"],
    "rating":   ["score", "stars", "review", "feedback"],
    "refunds":  ["returns", "chargebacks", "cancellations", "reversed"],
    "discount": ["coupon", "promo", "offer", "deal", "rebate"],
    "clicks":   ["taps", "interactions", "engagements"],
    "leads":    ["prospects", "inquiries", "contacts", "submissions"],
}

DIMENSION_ALIASES: dict[str, list[str]] = {
    "city":       ["location", "region", "area", "place", "town", "district", "zone"],
    "country":    ["nation", "territory", "geography"],
    "state":      ["province", "prefecture"],
    "product":    ["item", "sku", "good", "category", "merchandise", "offering", "name"],
    "category":   ["segment", "type", "class", "group", "tier"],
    "channel":    ["source", "medium", "platform", "origin", "referrer"],
    "department": ["team", "division", "unit", "vertical"],
    "status":     ["stage", "phase", "state", "condition"],
    "brand":      ["label", "manufacturer", "maker", "vendor", "supplier"],
    "gender":     ["sex"],
    "age":        ["age_group", "cohort"],
    "segment":    ["cluster", "persona", "tier"],
}

_ALL_ALIASES: dict[str, str] = {}
for _c, _syns in {**METRIC_ALIASES, **DIMENSION_ALIASES}.items():
    for _s in _syns:
        _ALL_ALIASES[_s] = _c
    _ALL_ALIASES[_c] = _c


def _score_col(user_word: str, col_name: str) -> int:
    """Score how well user_word matches a column name. Higher = better."""
    if user_word == col_name:          return 100
    canonical = _ALL_ALIASES.get(user_word)
    if canonical and (canonical == col_name or canonical in col_name): return 60
    if user_word in col_name:          return 70
    if col_name in user_word:          return 65
    u_tok = set(user_word.replace("_", " ").split())
    c_tok = set(col_name.replace("_", " ").split())
    overlap = u_tok & c_tok
    if overlap:                        return 40 + len(overlap) * 5
    return 0


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_]*", text.lower())
    stop   = {"show","me","give","get","what","is","are","the","a","an","of","by","in",
               "for","and","or","how","many","much","do","did","does","was","were","my",
               "our","all","each","per","with","without","where","when","which","who",
               "that","this","from","to","vs","versus","between","compare","list"}
    return [t for t in tokens if t not in stop and len(t) > 1]


def find_metric_column(query: str, schema: dict) -> Optional[dict]:
    tokens      = _tokenize(query)
    numeric_cols = [c for c in schema.get("columns", []) if c["type"] == "numeric"]
    if not numeric_cols:
        return None
    best, best_score = None, 0
    for token in tokens:
        for col in numeric_cols:
            s = _score_col(token, col["name"].lower())
            if s > best_score:
                best_score, best = s, {"name": col["name"], "type": col["type"], "score": s}
    if not best or best_score < 30:
        c = numeric_cols[0]
        return {"name": c["name"], "type": c["type"], "score": 10}
    return best


def find_dimension_column(query: str, schema: dict) -> Optional[dict]:
    tokens    = _tokenize(query)
    text_cols = [c for c in schema.get("columns", []) if c["type"] == "text"]
    if not text_cols:
        return None
    best, best_score = None, 0
    for token in tokens:
        for col in text_cols:
            s = _score_col(token, col["name"].lower())
            if s > best_score:
                best_score, best = s, {"name": col["name"], "type": col["type"], "score": s}
    if not best or best_score < 30:
        c = text_cols[0]
        return {"name": c["name"], "type": c["type"], "score": 10}
    return best


def find_date_column(schema: dict) -> Optional[dict]:
    for col in schema.get("columns", []):
        if col["type"] == "date":
            return {"name": col["name"], "type": "date", "score": 100}
    return None


def get_all_columns_of_type(schema: dict, col_type: str) -> list[dict]:
    return [c for c in schema.get("columns", []) if c["type"] == col_type]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION B — DATE / NUMERIC PARSER (merged from utils/date_parser.py)
# ═══════════════════════════════════════════════════════════════════════════════

_DATE_PATTERNS = [
    (re.compile(r"\blast\s+(\d+)\s+(day|days|week|weeks|month|months|year|years)\b", re.I), "last_n"),
    (re.compile(r"\blast\s+(week|month|year)\b", re.I),  "last_unit"),
    (re.compile(r"\bthis\s+(week|month|year)\b", re.I),  "this_unit"),
    (re.compile(r"\b(today|yesterday)\b", re.I),         "rel_day"),
    (re.compile(r"\b(last|this)\s+quarter\b", re.I),     "quarter"),
    (re.compile(r"\b(year[\s-]to[\s-]date|ytd)\b", re.I),"ytd"),
    (re.compile(r"\bpast\s+(\d+)\s+(day|days|week|weeks|month|months)\b", re.I), "last_n"),
]
_UNIT_MAP = {"day":"DAY","days":"DAY","week":"WEEK","weeks":"WEEK",
             "month":"MONTH","months":"MONTH","year":"YEAR","years":"YEAR"}


def parse_time_expression(text: str, date_col: str = "{date_col}") -> Optional[dict]:
    """Return DuckDB WHERE fragment for a time phrase, or None."""
    col = f'"{date_col}"' if " " in date_col else date_col
    for pat, kind in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        if kind == "last_n":
            n, unit = m.group(1), m.group(2)
            sql_unit = _UNIT_MAP.get(unit.lower(), "DAY")
            return {"where_clause": f"{col} >= CURRENT_DATE - INTERVAL {n} {sql_unit}",
                    "label": f"last {n} {unit}"}
        if kind == "last_unit":
            unit = m.group(1).lower()
            clauses = {"week": (f"{col} >= DATE_TRUNC('week', CURRENT_DATE - INTERVAL 7 DAY) "
                                f"AND {col} < DATE_TRUNC('week', CURRENT_DATE)", "last week"),
                       "month":(f"{col} >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL 1 MONTH) "
                                f"AND {col} < DATE_TRUNC('month', CURRENT_DATE)", "last month"),
                       "year": (f"{col} >= DATE_TRUNC('year', CURRENT_DATE - INTERVAL 1 YEAR) "
                                f"AND {col} < DATE_TRUNC('year', CURRENT_DATE)", "last year")}
            w, lbl = clauses.get(unit, (f"{col} >= CURRENT_DATE - INTERVAL 30 DAY", "last 30 days"))
            return {"where_clause": w, "label": lbl}
        if kind == "this_unit":
            unit = m.group(1).lower()
            clauses = {"week":  (f"{col} >= DATE_TRUNC('week', CURRENT_DATE)",  "this week"),
                       "month": (f"{col} >= DATE_TRUNC('month', CURRENT_DATE)", "this month"),
                       "year":  (f"{col} >= DATE_TRUNC('year', CURRENT_DATE)",  "this year")}
            w, lbl = clauses.get(unit, (f"{col} >= CURRENT_DATE - INTERVAL 30 DAY", "recent"))
            return {"where_clause": w, "label": lbl}
        if kind == "rel_day":
            day = m.group(1).lower()
            return {"where_clause": f"{col} = CURRENT_DATE" if day == "today"
                    else f"{col} = CURRENT_DATE - INTERVAL 1 DAY", "label": day}
        if kind == "quarter":
            q = m.group(1).lower()
            if q == "last":
                return {"where_clause": f"{col} >= DATE_TRUNC('quarter', CURRENT_DATE - INTERVAL 3 MONTH) "
                                        f"AND {col} < DATE_TRUNC('quarter', CURRENT_DATE)", "label": "last quarter"}
            return {"where_clause": f"{col} >= DATE_TRUNC('quarter', CURRENT_DATE)", "label": "this quarter"}
        if kind == "ytd":
            return {"where_clause": f"{col} >= DATE_TRUNC('year', CURRENT_DATE)", "label": "year to date"}
    return None


def extract_top_n(text: str) -> Optional[int]:
    m = re.search(r"\b(?:top|first|best|worst|bottom)\s+(\d+)\b", text, re.I)
    return min(int(m.group(1)), 100) if m else None


def extract_numeric_filter(text: str) -> Optional[dict]:
    pats = [
        (re.compile(r"\b(?:greater than|more than|above|over|exceeds?)\s+([\d,]+)\b", re.I), ">"),
        (re.compile(r"\b(?:less than|below|under|fewer than)\s+([\d,]+)\b", re.I), "<"),
        (re.compile(r"\b(?:at least|minimum|min)\s+([\d,]+)\b", re.I), ">="),
        (re.compile(r"\b(?:at most|maximum|max|up to)\s+([\d,]+)\b", re.I), "<="),
        (re.compile(r"\b(?:equals?|equal to|is exactly)\s+([\d,]+)\b", re.I), "="),
    ]
    for pat, op in pats:
        m = pat.search(text)
        if m:
            try:
                return {"op": op, "value": float(m.group(1).replace(",", ""))}
            except ValueError:
                continue
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION C — PARSER (core orchestrator)
# ═══════════════════════════════════════════════════════════════════════════════

# Heuristic column name tokens that suggest a date column
_DATE_HINT_NAMES = {"date","day","week","month","year","period","time","timestamp",
                    "datetime","created","updated","created_at","order_date","sale_date",
                    "report_date","transaction_date"}


def _heuristic_date_col(schema: dict) -> Optional[dict]:
    for col in schema.get("columns", []):
        name_lower = col["name"].lower().replace(" ", "_")
        if name_lower in _DATE_HINT_NAMES:
            return {"name": col["name"], "type": col["type"], "score": 80}
        for hint in _DATE_HINT_NAMES:
            if hint in name_lower:
                return {"name": col["name"], "type": col["type"], "score": 60}
    return None


def _detect_aggregation(raw_lower: str) -> str:
    if re.search(r"\b(average|avg|mean)\b", raw_lower):   return "AVG"
    if re.search(r"\b(count|number of|how many)\b", raw_lower): return "COUNT"
    if re.search(r"\b(min|minimum|lowest|least|smallest)\b", raw_lower): return "MIN"
    if re.search(r"\b(max|maximum|highest|largest)\b", raw_lower):       return "MAX"
    return "SUM"


def _safe_alias(col_name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", col_name).lower().strip("_")


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_nl_query(question: str, schema: dict) -> dict:
    """
    Convert a natural-language question into a SQL query or PM analytics request.

    Returns dict with keys:
        sql, pm_query, pm_intent, template_id, confidence,
        slots, warning, fallback, fallback_message, example_queries
    """
    question  = question.strip()
    raw_lower = question.lower()
    tokens    = _tokenize(question)

    template, confidence = select_template(tokens, raw_lower)
    examples = _generate_examples(schema)

    if confidence < CONFIDENCE_LOW:
        return _fallback("I couldn't understand your query. Try: 'Revenue by city last month'", examples)

    # PM template detected — signal main.py to use pm_analytics engine
    if template.sql_pattern == "__PM_ENGINE__":
        return {"sql": "", "pm_query": True, "pm_intent": template.template_id,
                "template_id": template.template_id, "confidence": round(confidence, 3),
                "slots": {}, "warning": None, "fallback": False,
                "fallback_message": None, "example_queries": examples}

    slots   = _fill_slots(template, question, raw_lower, tokens, schema)
    missing = [s for s in template.required_slots if not slots.get(s)]
    if missing:
        slots = _auto_fill_missing(slots, missing, schema)
        if [s for s in template.required_slots if not slots.get(s)]:
            return _fallback(f"I understood '{template.description}' but couldn't find the right "
                             f"column(s). Try one of these:", examples)

    try:
        sql = _render_sql(template, slots, schema)
    except Exception as e:
        return _fallback(f"Query construction failed: {e}. Try rephrasing.", examples)

    warning = (f"Low confidence ({confidence:.0%}). If results look wrong, try rephrasing."
               if confidence < CONFIDENCE_HIGH else None)

    return {"sql": sql, "pm_query": False, "pm_intent": None,
            "template_id": template.template_id, "confidence": round(confidence, 3),
            "slots": {k: str(v) for k, v in slots.items() if v is not None},
            "warning": warning, "fallback": False,
            "fallback_message": None, "example_queries": examples}


# ─── Slot Filling ─────────────────────────────────────────────────────────────

def _fill_slots(template, question, raw_lower, tokens, schema) -> dict:
    slots = {}
    slots["n"]   = extract_top_n(question) or 10
    slots["agg"] = _detect_aggregation(raw_lower)

    metric_col = find_metric_column(question, schema)
    if metric_col:
        slots["metric"]       = quote_col(metric_col["name"])
        slots["metric_alias"] = _safe_alias(metric_col["name"])
        slots["metric_type"]  = metric_col["type"]
    else:
        slots["metric"] = None

    dim_col = find_dimension_column(question, schema)
    if dim_col:
        slots["dim"]       = quote_col(dim_col["name"])
        slots["dim_alias"] = _safe_alias(dim_col["name"])
    else:
        slots["dim"] = None

    date_col = find_date_column(schema) or _heuristic_date_col(schema)
    if date_col:
        slots["date"]         = quote_col(date_col["name"])
        slots["date_col_raw"] = date_col["name"]
    else:
        slots["date"] = slots["date_col_raw"] = None

    date_raw = slots.get("date_col_raw") or "date"
    slots["time_filter"]    = parse_time_expression(question, date_raw)
    slots["numeric_filter"] = extract_numeric_filter(question)
    return slots


def _auto_fill_missing(slots: dict, missing: list[str], schema: dict) -> dict:
    numeric_cols = get_all_columns_of_type(schema, "numeric")
    text_cols    = get_all_columns_of_type(schema, "text")
    for slot in missing:
        if slot == "metric" and numeric_cols:
            c = numeric_cols[0]
            slots["metric"]       = quote_col(c["name"])
            slots["metric_alias"] = _safe_alias(c["name"])
        elif slot == "dim" and text_cols:
            c = text_cols[0]
            slots["dim"]       = quote_col(c["name"])
            slots["dim_alias"] = _safe_alias(c["name"])
        elif slot == "date":
            h = _heuristic_date_col(schema)
            if h:
                slots["date"] = quote_col(h["name"]); slots["date_col_raw"] = h["name"]
        elif slot == "n":
            slots["n"] = 10
    return slots


# ─── SQL Rendering ────────────────────────────────────────────────────────────

def _render_sql(template, slots: dict, schema: dict) -> str:
    tid    = template.template_id
    metric = slots.get("metric", "*");  metric_alias = slots.get("metric_alias", "value")
    agg    = slots.get("agg", "SUM");   dim  = slots.get("dim")
    date   = slots.get("date");         n    = slots.get("n", 10)

    where_parts = []
    if slots.get("time_filter") and slots.get("date"):
        where_parts.append(slots["time_filter"]["where_clause"])
    if slots.get("numeric_filter") and metric:
        nf = slots["numeric_filter"]
        where_parts.append(f"{metric} {nf['op']} {nf['value']}")
    wc = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    if tid == "metric_by_dim":
        if not dim:
            return f"SELECT {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc}"
        return f"SELECT {dim}, {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc} GROUP BY {dim} ORDER BY 2 DESC LIMIT 500"

    if tid in ("top_n", "bottom_n"):
        order = "DESC" if tid == "top_n" else "ASC"
        if dim:
            return f"SELECT {dim}, {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc} GROUP BY {dim} ORDER BY 2 {order} LIMIT {n}"
        return f"SELECT * FROM data{wc} ORDER BY {metric} {order} LIMIT {n}"

    if tid == "trend_over_time":
        if not date:
            if dim:
                return f"SELECT {dim}, {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc} GROUP BY {dim} ORDER BY 2 DESC LIMIT 500"
            return f"SELECT {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc}"
        return f"SELECT {date}, {agg}({metric}) AS {agg.lower()}_{metric_alias} FROM data{wc} GROUP BY {date} ORDER BY 1 LIMIT 500"

    if tid == "avg_metric":
        if dim:
            return f"SELECT {dim}, AVG({metric}) AS avg_{metric_alias} FROM data{wc} GROUP BY {dim} ORDER BY 2 DESC LIMIT 500"
        return f"SELECT AVG({metric}) AS avg_{metric_alias} FROM data{wc}"

    if tid == "count_by_dim":
        if dim:
            return f"SELECT {dim}, COUNT(*) AS count FROM data{wc} GROUP BY {dim} ORDER BY 2 DESC LIMIT 500"
        return f"SELECT COUNT(*) AS total_count FROM data{wc}"

    if tid == "total_metric":
        return f"SELECT SUM({metric}) AS total_{metric_alias} FROM data{wc}"

    if tid == "raw_top_n":
        return f"SELECT * FROM data{wc} LIMIT {n}"

    return f"SELECT * FROM data LIMIT {n}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fallback(message: str, examples: list[str]) -> dict:
    return {"sql": "", "pm_query": False, "pm_intent": None, "template_id": None,
            "confidence": 0.0, "slots": {}, "warning": None, "fallback": True,
            "fallback_message": message, "example_queries": examples}


def _generate_examples(schema: dict) -> list[str]:
    cols     = schema.get("columns", [])
    numeric  = [c["name"] for c in cols if c["type"] == "numeric"]
    text_    = [c["name"] for c in cols if c["type"] == "text"]
    date_    = [c["name"] for c in cols if c["type"] == "date"]
    examples = []
    if numeric and text_:
        examples += [f"Show me {numeric[0]} by {text_[0]}", f"Top 5 {text_[0]} by {numeric[0]}"]
    if numeric and date_:
        examples.append(f"{numeric[0]} trend over time")
    elif numeric:
        examples.append(f"Total {numeric[0]}")
    if len(examples) < 3:
        examples.append("Show me the top 10 rows")
    return examples[:3]
