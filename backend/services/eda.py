"""
services/eda.py — Local Exploratory Data Analysis engine for PulseBoard.

Provides schema-agnostic EDA on any uploaded CSV:
  - Column profiling (type, null%, unique count, min/max/mean/std)
  - Pearson correlation matrix for all numeric pairs
  - Distribution summary (histogram buckets per numeric col)
  - Missing value map (per column)
  - Outlier detection (values > 3σ from mean)

Zero external API calls. Pure pandas + numpy. Fast even on 50MB files.

Public API:
    run_eda(csv_path: Path) -> dict
"""

import numpy as np
import pandas as pd
from pathlib import Path


# ─── Public API ───────────────────────────────────────────────────────────────

def run_eda(csv_path: Path) -> dict:
    """
    Run full EDA on a CSV file.

    Returns:
    {
        "profile":        list[dict]   — per-column statistics
        "correlations":   list[dict]   — pairwise Pearson correlations (top 20)
        "distributions":  list[dict]   — histogram buckets per numeric column
        "missing":        list[dict]   — columns with null counts
        "outliers":       list[dict]   — columns with outlier counts + examples
        "summary":        dict         — dataset-level summary (rows, cols, numeric_cols, etc.)
    }
    """
    df = pd.read_csv(csv_path)
    df_sample = df.head(10000)  # Cap at 10k rows for performance

    profile      = _profile_columns(df_sample)
    correlations = _compute_correlations(df_sample)
    distributions = _compute_distributions(df_sample)
    missing      = _compute_missing(df_sample)
    outliers     = _detect_outliers(df_sample)
    summary      = _dataset_summary(df, profile)

    return {
        "profile":       profile,
        "correlations":  correlations,
        "distributions": distributions,
        "missing":       missing,
        "outliers":      outliers,
        "summary":       summary,
    }


# ─── Column Profiler ──────────────────────────────────────────────────────────

def _profile_columns(df: pd.DataFrame) -> list[dict]:
    """Per-column statistics."""
    n = len(df)
    profiles = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        null_pct   = round(null_count / n * 100, 1) if n > 0 else 0
        unique     = int(series.nunique(dropna=True))
        dtype_str  = str(series.dtype)

        # Detect type
        if "int" in dtype_str or "float" in dtype_str:
            col_type = "numeric"
        elif "datetime" in dtype_str:
            col_type = "date"
        else:
            # Try date parse
            try:
                pd.to_datetime(series.dropna().iloc[:5], errors="raise")
                col_type = "date"
            except Exception:
                col_type = "text"

        entry: dict = {
            "name":       col,
            "type":       col_type,
            "null_count": null_count,
            "null_pct":   null_pct,
            "unique":     unique,
        }

        if col_type == "numeric":
            non_null = series.dropna()
            entry["min"]  = _safe_float(non_null.min())
            entry["max"]  = _safe_float(non_null.max())
            entry["mean"] = _safe_float(non_null.mean())
            entry["std"]  = _safe_float(non_null.std())
            entry["median"] = _safe_float(non_null.median())
        elif col_type == "text":
            top = series.dropna().value_counts().head(5)
            entry["top_values"] = [{"value": str(v), "count": int(c)}
                                   for v, c in top.items()]
        elif col_type == "date":
            parsed = pd.to_datetime(series, errors="coerce").dropna()
            if len(parsed) > 0:
                entry["min_date"] = str(parsed.min().date())
                entry["max_date"] = str(parsed.max().date())

        profiles.append(entry)

    return profiles


# ─── Correlation Matrix ───────────────────────────────────────────────────────

def _compute_correlations(df: pd.DataFrame) -> list[dict]:
    """Compute Pearson correlation for all numeric column pairs. Return top 20."""
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return []

    corr_matrix = numeric.corr(method="pearson")
    pairs = []

    cols = corr_matrix.columns.tolist()
    for i, c1 in enumerate(cols):
        for c2 in cols[i + 1:]:
            r = corr_matrix.loc[c1, c2]
            if pd.isna(r):
                continue
            pairs.append({
                "col_a":     c1,
                "col_b":     c2,
                "r":         round(float(r), 3),
                "abs_r":     round(abs(float(r)), 3),
                "strength":  _corr_strength(abs(float(r))),
                "direction": "positive" if r > 0 else "negative",
            })

    pairs.sort(key=lambda x: x["abs_r"], reverse=True)
    return pairs[:20]


def _corr_strength(abs_r: float) -> str:
    if abs_r >= 0.8: return "very strong"
    if abs_r >= 0.6: return "strong"
    if abs_r >= 0.4: return "moderate"
    if abs_r >= 0.2: return "weak"
    return "negligible"


# ─── Distribution Summaries ───────────────────────────────────────────────────

def _compute_distributions(df: pd.DataFrame, bins: int = 10) -> list[dict]:
    """
    Compute histogram bucket data for each numeric column.
    Returns at most 8 columns to keep response size manageable.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()[:8]
    result = []

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 5:
            continue
        try:
            counts, edges = np.histogram(series, bins=min(bins, len(series) // 2 or 1))
            buckets = []
            for i in range(len(counts)):
                buckets.append({
                    "label": f"{edges[i]:.2g}–{edges[i+1]:.2g}",
                    "count": int(counts[i]),
                    "from":  _safe_float(edges[i]),
                    "to":    _safe_float(edges[i + 1]),
                })
            result.append({"column": col, "buckets": buckets})
        except Exception:
            continue

    return result


# ─── Missing Values ───────────────────────────────────────────────────────────

def _compute_missing(df: pd.DataFrame) -> list[dict]:
    """Per-column missing value counts. Only returns columns with at least 1 null."""
    n = len(df)
    missing = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            missing.append({
                "column":     col,
                "null_count": null_count,
                "null_pct":   round(null_count / n * 100, 1) if n > 0 else 0,
            })
    missing.sort(key=lambda x: x["null_pct"], reverse=True)
    return missing


# ─── Outlier Detection ────────────────────────────────────────────────────────

def _detect_outliers(df: pd.DataFrame) -> list[dict]:
    """
    Detect outliers in numeric columns using 3-sigma rule.
    Returns per-column outlier count + a sample of extreme values.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    outliers = []

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue
        mean  = float(series.mean())
        std   = float(series.std())
        if std == 0:
            continue
        mask   = (series - mean).abs() > 3 * std
        count  = int(mask.sum())
        if count == 0:
            continue
        extreme = series[mask].sort_values(key=abs, ascending=False).head(3).tolist()
        outliers.append({
            "column":        col,
            "outlier_count": count,
            "outlier_pct":   round(count / len(series) * 100, 1),
            "mean":          round(mean, 3),
            "std":           round(std, 3),
            "examples":      [_safe_float(v) for v in extreme],
        })

    outliers.sort(key=lambda x: x["outlier_pct"], reverse=True)
    return outliers


# ─── Dataset Summary ─────────────────────────────────────────────────────────

def _dataset_summary(df: pd.DataFrame, profile: list[dict]) -> dict:
    """High-level summary of the dataset."""
    total_nulls = int(df.isna().sum().sum())
    numeric_cols = [p["name"] for p in profile if p["type"] == "numeric"]
    text_cols    = [p["name"] for p in profile if p["type"] == "text"]
    date_cols    = [p["name"] for p in profile if p["type"] == "date"]
    completeness = round((1 - total_nulls / max(df.size, 1)) * 100, 1)

    return {
        "total_rows":      len(df),
        "total_cols":      len(df.columns),
        "numeric_cols":    len(numeric_cols),
        "text_cols":       len(text_cols),
        "date_cols":       len(date_cols),
        "total_nulls":     total_nulls,
        "completeness_pct": completeness,
        "numeric_col_names": numeric_cols[:10],
        "text_col_names":    text_cols[:10],
    }


# ─── Build LLM Data Summary (for insight prompts) ────────────────────────────

def build_data_summary_for_llm(csv_path: Path, schema: dict) -> str:
    """
    Build a compact statistical summary string suitable for LLM insight prompts.
    NEVER includes raw data — only aggregated statistics.
    """
    try:
        df = pd.read_csv(csv_path, nrows=5000)
        lines = [f"Dataset: {len(df)} rows × {len(df.columns)} columns"]

        numeric = df.select_dtypes(include=[np.number])
        if not numeric.empty:
            lines.append("\nNumeric column stats:")
            for col in numeric.columns[:8]:
                s = numeric[col].dropna()
                if len(s) > 0:
                    lines.append(
                        f"  {col}: min={s.min():.2g}, max={s.max():.2g}, "
                        f"mean={s.mean():.2g}, std={s.std():.2g}"
                    )

        text_cols = df.select_dtypes(include=["object"]).columns[:4]
        if len(text_cols) > 0:
            lines.append("\nText column top values:")
            for col in text_cols:
                top = df[col].value_counts().head(3).index.tolist()
                lines.append(f"  {col}: {', '.join(str(v) for v in top)}")

        return "\n".join(lines)
    except Exception:
        return "Dataset summary unavailable."


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _safe_float(val) -> float:
    """Convert numpy scalar to plain Python float safely."""
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return round(f, 4)
    except Exception:
        return 0.0
