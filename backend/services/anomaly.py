"""
anomaly.py — Z-score based anomaly detection on numeric metric columns.
Uses pure numpy (no scipy dependency).
Monitors 30-day rolling windows; alerts when |z| > 2.0.
Severity: Critical (|z| > 3.0) | Warning (2.0 < |z| <= 3.0)
"""

import pandas as pd
import numpy as np
from pathlib import Path


def detect_anomalies(csv_path: Path) -> list[dict]:
    """
    Scan all numeric columns in the CSV for anomalies using Z-score.
    Uses the most recent value vs the 30-day rolling baseline.
    Returns list of anomaly alerts sorted by severity.
    """
    df = pd.read_csv(csv_path)

    # Find date column (first datetime-parseable column)
    date_col = None
    for col in df.columns:
        try:
            pd.to_datetime(df[col].dropna().iloc[:5])
            date_col = col
            break
        except Exception:
            continue

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.sort_values(date_col)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    alerts = []

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 7:
            continue  # Need at least 7 data points

        # Use last 30 data points as baseline, exclude the most recent
        window = series.iloc[-31:-1] if len(series) >= 31 else series.iloc[:-1]
        latest = float(series.iloc[-1])

        rolling_mean = float(window.mean())
        rolling_std = float(window.std())

        if rolling_std == 0:
            continue  # No variation — skip

        z_score = (latest - rolling_mean) / rolling_std
        abs_z = abs(z_score)

        if abs_z > 2.0:
            direction = "spike" if z_score > 0 else "drop"
            pct_change = ((latest - rolling_mean) / rolling_mean * 100) if rolling_mean != 0 else 0
            severity = "critical" if abs_z > 3.0 else "warning"

            alerts.append({
                "column": col,
                "current_value": round(latest, 2),
                "baseline_mean": round(rolling_mean, 2),
                "z_score": round(z_score, 2),
                "severity": severity,
                "direction": direction,
                "pct_change": round(pct_change, 1),
                "message": _format_alert_message(col, direction, pct_change, severity),
            })

    # Sort: Critical first, then by |z| descending
    alerts.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, -abs(x["z_score"])))
    return alerts


def _format_alert_message(col: str, direction: str, pct_change: float, severity: str) -> str:
    """Generate human-readable anomaly alert message."""
    verb = "jumped" if direction == "spike" else "dropped"
    emoji = "🚨" if severity == "critical" else "⚠️"
    pct_str = f"{abs(pct_change):.1f}%"
    return f"{emoji} Your {col} {verb} {pct_str} from the 30-day baseline — investigate immediately."
