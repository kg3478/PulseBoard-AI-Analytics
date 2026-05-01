"""
nl_engine/templates.py — SQL + PM template library for PulseBoard.

12 templates total:
  SQL (8): metric_by_dim, top_n, bottom_n, trend_over_time, avg_metric,
           count_by_dim, total_metric, raw_top_n
  PM  (4): funnel_analysis, cohort_analysis, retention_query, activation_query
           (use sql_pattern='__PM_ENGINE__' — routed to pm_analytics.run_pm_query)
"""

from dataclasses import dataclass, field
from typing import Optional
import re


# ─── Template Dataclass ───────────────────────────────────────────────────────

@dataclass
class SQLTemplate:
    template_id: str
    description: str
    keywords: list[str]           # Trigger words for scoring
    boost_phrases: list[str]      # Multi-word phrases that get double score
    required_slots: list[str]     # Slots that MUST be filled
    optional_slots: list[str]     # Slots that improve the query if present
    sql_pattern: str              # Template string with {slot} placeholders

    def score(self, tokens: list[str], raw_query: str) -> float:
        """
        Score this template against a list of tokens (0.0 – 1.0).
        Higher = better match.
        """
        total_keywords = len(self.keywords) or 1
        matches = sum(1 for kw in self.keywords if kw in tokens)

        # Boost for exact phrase matches
        phrase_bonus = sum(
            0.3 for phrase in self.boost_phrases
            if phrase in raw_query.lower()
        )

        raw_score = (matches / total_keywords) + phrase_bonus
        return min(raw_score, 1.0)

    def render(self, slots: dict) -> str:
        """
        Render the SQL template with the given slot values.
        Missing optional slots are handled gracefully.
        """
        sql = self.sql_pattern
        for key, val in slots.items():
            sql = sql.replace(f"{{{key}}}", str(val) if val is not None else "")
        return sql.strip()


# ─── Template Library ─────────────────────────────────────────────────────────

TEMPLATES: list[SQLTemplate] = [

    # 1 — Revenue / metric by dimension
    SQLTemplate(
        template_id="metric_by_dim",
        description="Aggregate a metric grouped by a dimension",
        keywords=["by", "per", "breakdown", "split", "group", "each",
                  "distribution", "across", "among", "for each"],
        boost_phrases=[
            "by city", "by product", "by region", "by category",
            "by channel", "by status", "by location", "by department",
            "revenue by", "sales by", "orders by", "users by",
            "show me revenue", "show revenue", "show sales",
        ],
        required_slots=["metric", "dim"],
        optional_slots=["agg", "where", "limit"],
        sql_pattern=(
            "SELECT {dim}, {agg}({metric}) AS {agg}_{metric_alias} "
            "FROM data{where_clause} "
            "GROUP BY {dim} "
            "ORDER BY 2 DESC "
            "LIMIT {limit}"
        ),
    ),

    # 2 — Top N by metric
    SQLTemplate(
        template_id="top_n",
        description="Top N rows by a metric",
        keywords=["top", "best", "highest", "leading", "most", "ranking", "ranked", "first"],
        boost_phrases=["top 5", "top 10", "top 3", "best performing", "highest revenue"],
        required_slots=["metric", "dim", "n"],
        optional_slots=["where"],
        sql_pattern=(
            "SELECT {dim}, {agg}({metric}) AS {agg}_{metric_alias} "
            "FROM data{where_clause} "
            "GROUP BY {dim} "
            "ORDER BY 2 DESC "
            "LIMIT {n}"
        ),
    ),

    # 3 — Bottom N by metric
    SQLTemplate(
        template_id="bottom_n",
        description="Bottom N rows by a metric",
        keywords=["bottom", "worst", "lowest", "least", "lagging", "underperforming",
                  "by", "ranked", "performing", "poor"],
        boost_phrases=["bottom 5", "bottom 10", "bottom 3", "worst performing",
                       "lowest revenue", "least revenue", "worst cities", "worst products"],
        required_slots=["metric", "dim", "n"],
        optional_slots=["where"],
        sql_pattern=(
            "SELECT {dim}, {agg}({metric}) AS {agg}_{metric_alias} "
            "FROM data{where_clause} "
            "GROUP BY {dim} "
            "ORDER BY 2 ASC "
            "LIMIT {n}"
        ),
    ),

    # 4 — Trend over time
    SQLTemplate(
        template_id="trend_over_time",
        description="Metric aggregated over a date dimension",
        keywords=["over time", "trend", "timeline", "daily", "weekly", "monthly", "growth", "progression", "history"],
        boost_phrases=["over time", "over the months", "trend", "by day", "by week", "by month"],
        required_slots=["metric", "date"],
        optional_slots=["agg", "where"],
        sql_pattern=(
            "SELECT {date}, {agg}({metric}) AS {agg}_{metric_alias} "
            "FROM data{where_clause} "
            "GROUP BY {date} "
            "ORDER BY 1 "
            "LIMIT 500"
        ),
    ),

    # 5 — Average metric
    SQLTemplate(
        template_id="avg_metric",
        description="Average of a metric, optionally by dimension",
        keywords=["average", "avg", "mean", "typical", "median"],
        boost_phrases=["average order", "average revenue", "avg value", "mean value"],
        required_slots=["metric"],
        optional_slots=["dim", "where"],
        sql_pattern=(
            "SELECT {dim_select}AVG({metric}) AS avg_{metric_alias} "
            "FROM data{where_clause}{group_by} "
            "ORDER BY 1 "
            "LIMIT 500"
        ),
    ),

    # 6 — Count by dimension
    SQLTemplate(
        template_id="count_by_dim",
        description="Count of rows grouped by a dimension",
        keywords=["count", "how many", "number of", "frequency", "occurrences", "times"],
        boost_phrases=["count by", "how many orders", "number of customers", "number of transactions"],
        required_slots=["dim"],
        optional_slots=["where"],
        sql_pattern=(
            "SELECT {dim}, COUNT(*) AS count "
            "FROM data{where_clause} "
            "GROUP BY {dim} "
            "ORDER BY 2 DESC "
            "LIMIT 500"
        ),
    ),

    # 7 — Total / sum of a metric
    SQLTemplate(
        template_id="total_metric",
        description="Total sum of a numeric metric",
        keywords=["total", "sum", "overall", "aggregate", "cumulative", "all"],
        boost_phrases=["total revenue", "total sales", "sum of", "overall total"],
        required_slots=["metric"],
        optional_slots=["where"],
        sql_pattern=(
            "SELECT SUM({metric}) AS total_{metric_alias} "
            "FROM data{where_clause}"
        ),
    ),

    # 8 — Raw top N rows (catch-all / fallback) — intentionally low keyword overlap
    SQLTemplate(
        template_id="raw_top_n",
        description="Show raw top N rows from the data",
        keywords=["show", "display", "list", "rows", "records", "table", "entries", "sample", "preview"],
        boost_phrases=["top rows", "first rows", "sample data", "show the data", "show all", "show data"],
        required_slots=[],
        optional_slots=["n"],
        sql_pattern="SELECT * FROM data LIMIT {n}",
    ),

    # ── PM Analytics Templates (route to pm_analytics engine, not SQL) ────────

    # 9 — Funnel Analysis
    SQLTemplate(
        template_id="funnel_analysis",
        description="User conversion funnel between ordered event steps",
        keywords=["funnel", "conversion", "dropoff", "drop", "steps", "flow", "journey"],
        boost_phrases=["signup to purchase", "conversion funnel", "drop-off",
                       "user journey", "funnel for", "from signup", "step by step"],
        required_slots=[],
        optional_slots=[],
        sql_pattern="__PM_ENGINE__",
    ),

    # 10 — Cohort Analysis
    SQLTemplate(
        template_id="cohort_analysis",
        description="Group users by first activity date and track over time",
        keywords=["cohort", "cohorts", "group by signup", "signup date"],
        boost_phrases=["cohort analysis", "retention cohort", "by signup date",
                       "weekly cohort", "monthly cohort"],
        required_slots=[],
        optional_slots=[],
        sql_pattern="__PM_ENGINE__",
    ),

    # 11 — Retention Query
    SQLTemplate(
        template_id="retention_query",
        description="User retention rate over time",
        keywords=["retention", "retained", "returning", "churn", "comeback", "stickiness"],
        boost_phrases=["weekly retention", "monthly retention", "day 7 retention",
                       "retention rate", "user retention", "how many users returned"],
        required_slots=[],
        optional_slots=[],
        sql_pattern="__PM_ENGINE__",
    ),

    # 12 — Activation Query
    SQLTemplate(
        template_id="activation_query",
        description="Activation rate — users who completed the key first action",
        keywords=["activation", "activated", "onboard", "onboarding", "first action", "setup"],
        boost_phrases=["activation rate", "how many activated", "completed onboarding",
                       "users who activated", "first key action"],
        required_slots=[],
        optional_slots=[],
        sql_pattern="__PM_ENGINE__",
    ),

    # 13 — DAU / WAU / MAU Query
    SQLTemplate(
        template_id="dau_query",
        description="Daily/Weekly/Monthly active user metrics",
        keywords=["dau", "wau", "mau", "daily", "active", "users", "weekly", "monthly", "stickiness"],
        boost_phrases=["daily active users", "weekly active", "monthly active",
                       "active users", "dau trend", "user activity", "dau wau mau"],
        required_slots=[],
        optional_slots=[],
        sql_pattern="__PM_ENGINE__",
    ),
]


# ─── Template Selector ────────────────────────────────────────────────────────

def select_template(tokens: list[str], raw_query: str) -> tuple[SQLTemplate, float]:
    """
    Score all templates and return the best match.
    PM templates (__PM_ENGINE__) take priority when their keywords dominate.
    raw_top_n is suppressed when any specific template also scores.
    """
    scored = [(tpl, tpl.score(tokens, raw_query)) for tpl in TEMPLATES]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_template, best_score = scored[0]

    # Suppress raw_top_n when a more specific template scores
    if best_template.template_id == "raw_top_n" and len(scored) > 1:
        runner_up, runner_score = scored[1]
        if runner_score >= 0.25:
            best_template, best_score = runner_up, runner_score

    # Tiebreaker: prefer templates with more keywords (more specific)
    top_candidates = [(t, s) for t, s in scored if s == best_score]
    if len(top_candidates) > 1:
        best_template = max(top_candidates, key=lambda x: len(x[0].keywords))[0]

    return best_template, best_score


def quote_col(col_name: str) -> str:
    """Wrap column name in double-quotes if it contains spaces or special chars."""
    if re.search(r"[\s\-/]", col_name):
        return f'"{col_name}"'
    return col_name
