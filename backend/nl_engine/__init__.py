"""
nl_engine — Local, deterministic NL-to-SQL engine for PulseBoard.
No external API calls. Zero latency beyond local regex + pandas.

Public API:
    parse_nl_query(question: str, schema: dict) -> dict
        Returns: { sql, pm_query, pm_intent, template_id, confidence,
                   slots, fallback_message, example_queries }
"""

from .parser import parse_nl_query

__all__ = ["parse_nl_query"]
