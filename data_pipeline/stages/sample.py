"""Stratified sampling (5% by role). Runs first in pipeline to reduce volume before validate/transform/enrich."""
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

try:
    from config import ROLE_COLUMN, SAMPLE_PCT, MIN_SAMPLES_PER_STRATUM, RANDOM_SEED
except ImportError:
    from ..config import ROLE_COLUMN, SAMPLE_PCT, MIN_SAMPLES_PER_STRATUM, RANDOM_SEED


def _get_primary_role(devtype_val) -> str:
    """Extract first role from semicolon-separated DevType."""
    if pd.isna(devtype_val) or str(devtype_val).strip() in ("", "nan", "None"):
        return "Unknown"
    parts = str(devtype_val).split(";")
    first = parts[0].strip() if parts else ""
    return first or "Unknown"


def stratified_sample(
    df: pd.DataFrame,
    sample_pct: float = SAMPLE_PCT,
    min_per_stratum: int = MIN_SAMPLES_PER_STRATUM,
    seed: Optional[int] = RANDOM_SEED
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Create a stratified sample by role (DevType).
    
    Each row is assigned to one stratum based on its primary role.
    We sample sample_pct (e.g. 5%) of each stratum, with at least
    min_per_stratum rows per role.
    
    Returns:
        - sampled_df: The stratified sample
        - stats: Sampling statistics
    """
    stats = {
        "rows_in": len(df),
        "sample_pct": sample_pct * 100,
        "strata_counts": {},
        "rows_out": 0
    }
    
    if ROLE_COLUMN not in df.columns:
        raise ValueError(f"DataFrame must have column '{ROLE_COLUMN}' for stratified sampling.")
    
    out = df.copy()
    out["_primary_role"] = out[ROLE_COLUMN].map(_get_primary_role)
    
    rng = np.random.default_rng(seed)
    sampled_parts = []
    
    for role, group in out.groupby("_primary_role", sort=False):
        n = len(group)
        k = max(min_per_stratum, min(n, round(n * sample_pct)))
        
        if k >= n:
            chosen_idx = group.index.tolist()
        else:
            chosen_idx = rng.choice(group.index, size=k, replace=False).tolist()
        
        sampled_parts.append(out.loc[chosen_idx].drop(columns=["_primary_role"]))
        stats["strata_counts"][str(role)] = {"original": n, "sampled": len(chosen_idx)}
    
    sampled_df = pd.concat(sampled_parts, axis=0, ignore_index=True)
    stats["rows_out"] = len(sampled_df)
    stats["reduction_pct"] = round((1 - len(sampled_df) / len(df)) * 100, 1)
    
    return sampled_df, stats
