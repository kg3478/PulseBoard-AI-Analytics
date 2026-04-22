"""
insights.py — LLM-powered weekly insight summary generation.
Uses gemini-2.0-flash with fallback to gemini-1.5-pro.
"""

import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

_MODELS = ["gemini-2.0-flash", "gemini-1.5-pro"]


def _get_model(model_name: str):
    return genai.GenerativeModel(model_name)


def _compute_metric_deltas(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    date_col = None
    for col in df.columns:
        try:
            pd.to_datetime(df[col].dropna().iloc[:5])
            date_col = col
            break
        except Exception:
            continue

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not date_col or not numeric_cols:
        return {
            col: {
                "this_week": round(float(df[col].tail(7).mean()), 2),
                "last_week": round(float(df[col].head(7).mean()), 2),
                "pct_change": None,
            }
            for col in numeric_cols[:8]
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.sort_values(date_col)
    last_date = df[date_col].max()

    this_week = df[df[date_col] > last_date - pd.Timedelta(days=7)]
    last_week = df[
        (df[date_col] > last_date - pd.Timedelta(days=14))
        & (df[date_col] <= last_date - pd.Timedelta(days=7))
    ]

    deltas = {}
    for col in numeric_cols[:8]:
        tw = this_week[col].sum() if len(this_week) > 0 else 0
        lw = last_week[col].sum() if len(last_week) > 0 else 0
        pct = ((tw - lw) / lw * 100) if lw != 0 else None
        deltas[col] = {
            "this_week": round(float(tw), 2),
            "last_week": round(float(lw), 2),
            "pct_change": round(float(pct), 1) if pct is not None else None,
        }
    return deltas


def generate_weekly_insights(csv_path: Path) -> dict:
    """Generate 3-5 weekly insight bullets using Gemini with model fallback."""
    deltas = _compute_metric_deltas(csv_path)

    delta_text = "Metric | This Week | Last Week | Change\n" + "-" * 55 + "\n"
    for col, vals in deltas.items():
        pct_str = f"{vals['pct_change']:+.1f}%" if vals["pct_change"] is not None else "N/A"
        delta_text += f"{col} | {vals['this_week']} | {vals['last_week']} | {pct_str}\n"

    prompt = f"""You are a growth analyst advising a non-technical startup founder.
Here is this week's metrics change summary:

{delta_text}

Write 3-5 bullet point insights in plain English. Rules:
1. Start with the most actionable finding.
2. Include specific numbers and percentages.
3. Flag any concerning trends clearly.
4. Use simple language — no jargon.
5. Each bullet must be a single sentence under 25 words.
6. Start each bullet with a relevant emoji.

Return ONLY the bullet points, nothing else."""

    last_error = None
    for model_name in _MODELS:
        try:
            model = _get_model(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.4, "max_output_tokens": 512},
                request_options={"timeout": 30},
            )
            raw = response.text.strip()
            bullets = [
                line.strip().lstrip("-•*").strip()
                for line in raw.split("\n")
                if line.strip()
            ]
            return {"bullets": bullets[:5], "deltas": deltas}
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if any(x in err_str for x in ["404", "not found", "deprecated", "quota", "unavailable"]):
                time.sleep(0.5)
                continue
            break

    return {
        "bullets": [f"⚠️ Could not generate insights: {str(last_error)}"],
        "deltas": deltas,
    }
