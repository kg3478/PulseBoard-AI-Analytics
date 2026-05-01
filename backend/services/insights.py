"""
services/insights.py — Hybrid insight generation for PulseBoard.

v3.0: Hybrid mode added.
  - Deterministic insights run first (always fast, always available)
  - LLM insights appended when GEMINI_API_KEY is set
  - Raw data is NEVER sent to LLM — only statistical summary

Public API (unchanged):
    generate_insights(csv_path, session_id?) -> dict
        Returns: { "bullets": list[str], "deltas": dict, "llm_bullets": list[str] }
    generate_pm_insights(pm_result, dataset_type) -> list[str]
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional


# ─── Bullet Templates ─────────────────────────────────────────────────────────

def _bullet_increase(col, pct, tw, lw):
    return f"📈 **{col}** increased by **{pct:+.1f}%** this week ({_fmt(tw)} vs {_fmt(lw)} last week)"

def _bullet_decrease(col, pct, tw, lw):
    return f"📉 **{col}** dropped by **{abs(pct):.1f}%** this week ({_fmt(tw)} vs {_fmt(lw)} last week) — worth monitoring"

def _bullet_spike(col, pct):
    return f"⚠️ **{col}** spiked **{pct:+.1f}%** — unusually high activity detected"

def _bullet_drop(col, pct):
    return f"🚨 **{col}** crashed **{abs(pct):.1f}%** — immediate investigation recommended"

def _bullet_stable(col, val):
    return f"✅ **{col}** is stable at {_fmt(val)} — no significant week-over-week change"

def _bullet_highest(col, val):
    return f"🏆 **{col}** reached its highest value in the dataset: {_fmt(val)}"

def _bullet_trend_up(col):
    return f"📊 **{col}** has been consistently rising over the past 3 periods"

def _bullet_trend_down(col):
    return f"📊 **{col}** has been declining steadily over the past 3 periods"

def _bullet_all_stable():
    return "✅ All metrics are stable this week — no significant changes detected across your data"


def _fmt(val: float) -> str:
    """Format a number compactly: 1234567 → 12.3L, 12345 → 12.3K."""
    if abs(val) >= 10_000_000: return f"{val / 10_000_000:.1f}Cr"
    if abs(val) >= 100_000:    return f"{val / 100_000:.1f}L"
    if abs(val) >= 1_000:      return f"{val / 1_000:.1f}K"
    if val == int(val):        return str(int(val))
    return f"{val:.2f}"


# ─── Metric Delta Computation ─────────────────────────────────────────────────

def _compute_metric_deltas(csv_path: Path) -> dict:
    """Compute week-over-week deltas for all numeric columns."""
    df = pd.read_csv(csv_path)

    date_col = None
    for col in df.columns:
        try:
            pd.to_datetime(df[col].dropna().iloc[:5], errors="raise")
            date_col = col
            break
        except Exception:
            continue

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return {}

    if not date_col:
        mid = len(df) // 2
        deltas = {}
        for col in numeric_cols[:8]:
            tw = float(df.iloc[mid:][col].sum())
            lw = float(df.iloc[:mid][col].sum())
            pct = ((tw - lw) / lw * 100) if lw != 0 else None
            deltas[col] = {"this_week": round(tw, 2), "last_week": round(lw, 2),
                           "pct_change": round(float(pct), 1) if pct is not None else None}
        return deltas

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.sort_values(date_col)
    last_date = df[date_col].max()
    this_week = df[df[date_col] > last_date - pd.Timedelta(days=7)]
    last_week = df[(df[date_col] > last_date - pd.Timedelta(days=14)) &
                   (df[date_col] <= last_date - pd.Timedelta(days=7))]

    deltas = {}
    for col in numeric_cols[:8]:
        tw = float(this_week[col].sum()) if len(this_week) > 0 else 0
        lw = float(last_week[col].sum()) if len(last_week) > 0 else 0
        pct = ((tw - lw) / lw * 100) if lw != 0 else None
        deltas[col] = {"this_week": round(tw, 2), "last_week": round(lw, 2),
                       "pct_change": round(float(pct), 1) if pct is not None else None}
    return deltas


def _detect_trend(csv_path: Path, col: str, date_col: Optional[str]) -> Optional[str]:
    try:
        df = pd.read_csv(csv_path)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.sort_values(date_col)
        series = df[col].dropna()
        if len(series) < 6:
            return None
        chunk = len(series) // 3
        p1 = float(series.iloc[-chunk * 3: -chunk * 2].sum())
        p2 = float(series.iloc[-chunk * 2: -chunk].sum())
        p3 = float(series.iloc[-chunk:].sum())
        if p1 < p2 < p3: return "up"
        if p1 > p2 > p3: return "down"
    except Exception:
        pass
    return None


def _find_overall_max(csv_path: Path, col: str) -> Optional[float]:
    try:
        return float(pd.read_csv(csv_path)[col].max())
    except Exception:
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_insights(csv_path: Path, session_id: str = "default") -> dict:
    """
    Generate hybrid insight summary:
      1. Deterministic WoW bullet points (always run, always fast)
      2. LLM insight bullets appended (only when GEMINI_API_KEY is set)

    Returns: { "bullets": list[str], "deltas": dict, "llm_bullets": list[str] }
    Raw data is NEVER sent to LLM — only a compact statistical summary.
    """
    deltas = _compute_metric_deltas(csv_path)
    if not deltas:
        return {"bullets": ["ℹ️ No numeric columns found in your data to generate insights."],
                "deltas": {}, "llm_bullets": []}

    try:
        df_head = pd.read_csv(csv_path, nrows=10)
        date_col = None
        for c in df_head.columns:
            try:
                pd.to_datetime(df_head[c].dropna().iloc[:3], errors="raise")
                date_col = c
                break
            except Exception:
                continue
    except Exception:
        date_col = None

    ranked    = sorted([(col, v) for col, v in deltas.items() if v["pct_change"] is not None],
                       key=lambda x: abs(x[1]["pct_change"]), reverse=True)
    no_change = [(col, v) for col, v in deltas.items() if v["pct_change"] is None]
    bullets   = []

    for col, vals in ranked[:4]:
        pct, tw, lw = vals["pct_change"], vals["this_week"], vals["last_week"]
        if   abs(pct) >= 40: bullet = _bullet_spike(col, pct) if pct > 0 else _bullet_drop(col, pct)
        elif pct > 5:        bullet = _bullet_increase(col, pct, tw, lw)
        elif pct < -5:       bullet = _bullet_decrease(col, pct, tw, lw)
        else:                bullet = _bullet_stable(col, tw)
        bullets.append(bullet)
        if col == ranked[0][0]:
            trend = _detect_trend(csv_path, col, date_col)
            if trend == "up"   and pct > 0: bullets.append(_bullet_trend_up(col))
            elif trend == "down" and pct < 0: bullets.append(_bullet_trend_down(col))

    if ranked and all(abs(v["pct_change"]) <= 5 for _, v in ranked if v["pct_change"] is not None) and bullets:
        bullets = [_bullet_all_stable()]

    if ranked and len(bullets) < 5:
        max_val = _find_overall_max(csv_path, ranked[0][0])
        if max_val is not None:
            bullets.append(_bullet_highest(ranked[0][0], max_val))

    if not bullets:
        for col, vals in no_change[:3]:
            bullets.append(_bullet_stable(col, vals["this_week"]))

    if not bullets:
        bullets = ["ℹ️ Upload data with more rows to generate meaningful week-over-week insights."]

    # ── LLM enrichment (non-blocking, graceful fallback) ─────────────────────
    llm_bullets: list[str] = []
    try:
        from services.llm_router import call_llm_for_insights, llm_available
        from services.eda import build_data_summary_for_llm
        from services.pm_analytics import detect_dataset_type
        if llm_available():
            schema_stub = {"columns": [{"name": c, "type": "numeric"}
                                       for c in list(deltas.keys())[:8]]}
            dataset_type = detect_dataset_type(schema_stub)
            summary      = build_data_summary_for_llm(csv_path, schema_stub)
            llm_bullets  = call_llm_for_insights(summary, dataset_type, session_id=session_id)
    except Exception:
        llm_bullets = []

    return {"bullets": bullets[:5], "deltas": deltas, "llm_bullets": llm_bullets}


# Preserved alias
generate_weekly_insights = generate_insights


# ─── PM Analytics Insight Generator ─────────────────────────────────────────

def generate_pm_insights(pm_result: dict, dataset_type: str = "product_analytics") -> list[str]:
    """Generate PM-focused insight bullets from a pm_analytics result dict."""
    pm_data = pm_result.get("pm_data", {})
    rows    = pm_result.get("rows", [])
    pm_type = pm_data.get("type", "")
    bullets = []

    if pm_type == "funnel":
        steps, counts, drop_offs = pm_data.get("steps",[]), pm_data.get("user_counts",[]), pm_data.get("drop_offs",[])
        overall = pm_data.get("overall_conversion", 0)
        bullets.append(f"🎯 Overall funnel conversion: **{overall:.1f}%** of users completed all steps")
        if len(drop_offs) > 1:
            idx = max(range(1, len(drop_offs)), key=lambda i: drop_offs[i])
            step_name = steps[idx] if idx < len(steps) else f"step {idx}"
            bullets.append(f"🔻 Biggest drop-off at **{step_name}** ({drop_offs[idx]:.1f}% lost) — highest priority optimization")
        if counts:
            bullets.append(f"👥 {counts[0]:,} users entered the funnel; {counts[-1]:,} completed it")

    elif pm_type == "activation_rate":
        rate, event = pm_data.get("rate", 0), pm_data.get("activation_event", "the key action")
        total, activated = pm_data.get("total_users", 0), pm_data.get("activated", 0)
        emoji = "✅" if rate >= 60 else "⚠️" if rate >= 30 else "🚨"
        bullets.append(f"{emoji} Activation rate: **{rate}%** — {activated:,} of {total:,} users reached '{event}'")
        if rate < 60:
            bullets.append(f"💡 {100 - rate:.1f}% of users never activated — improve onboarding or reduce time-to-value")

    elif pm_type == "cohort":
        period = pm_data.get("period", "week")
        if rows:
            w1_vals = [r.get("week_1", 0) for r in rows if "week_1" in r]
            w4_vals = [r.get("week_4", 0) for r in rows if "week_4" in r]
            avg_w1 = round(sum(w1_vals) / len(w1_vals), 1) if w1_vals else None
            avg_w4 = round(sum(w4_vals) / len(w4_vals), 1) if w4_vals else None
            if avg_w1 is not None:
                bullets.append(f"{'✅' if avg_w1 >= 40 else '⚠️'} {period.title()}-1 retention: **{avg_w1}%**")
            if avg_w4 is not None:
                bullets.append(f"📊 {period.title()}-4 retention: **{avg_w4}%** — "
                               f"{'healthy long-term engagement' if avg_w4 >= 20 else 'churn risk detected'}")

    elif pm_type == "dau_wau_mau":
        s = pm_data.get("summary", {})
        bullets.append(f"📱 DAU: **{s.get('current_dau',0):,}** | WAU: **{s.get('avg_wau',0):,}** | MAU: **{s.get('avg_mau',0):,}**")
        ratio = s.get("dau_wau_ratio", 0)
        if ratio > 0:
            stickiness = "excellent" if ratio > 0.5 else "moderate" if ratio > 0.2 else "low"
            bullets.append(f"🔁 DAU/WAU ratio: **{ratio:.2f}** — {stickiness} user stickiness")

    if not bullets:
        bullets.append("ℹ️ PM analytics computed — see the chart for detailed breakdown")

    return bullets[:5]
