"""Stage 1: Validate data (schema, nulls, duplicates)."""
import pandas as pd
from typing import Dict, Any, Tuple, List

try:
    from config import REQUIRED_COLUMNS, KEY_COLUMNS
except ImportError:
    from ..config import REQUIRED_COLUMNS, KEY_COLUMNS


def validate_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Validate survey data.
    
    Returns:
        - valid_df: Rows that passed validation
        - quarantine_df: Rows that failed validation
        - stats: Validation statistics
    """
    stats = {
        "rows_in": len(df),
        "rows_valid": 0,
        "rows_quarantined": 0,
        "issues": []
    }
    
    # Check required columns exist
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        stats["issues"].append(f"Missing columns: {missing_cols}")
    
    # Remove exact duplicates
    df_dedup = df.drop_duplicates()
    dupe_count = len(df) - len(df_dedup)
    if dupe_count > 0:
        stats["issues"].append(f"Removed {dupe_count} duplicate rows")
    
    # Check for ResponseId duplicates (keep first)
    if "ResponseId" in df_dedup.columns:
        before = len(df_dedup)
        df_dedup = df_dedup.drop_duplicates(subset=["ResponseId"], keep="first")
        id_dupes = before - len(df_dedup)
        if id_dupes > 0:
            stats["issues"].append(f"Removed {id_dupes} duplicate ResponseIds")
    
    # Quarantine rows with >50% nulls in key columns
    key_cols = [c for c in KEY_COLUMNS if c in df_dedup.columns]
    if key_cols:
        null_pct = df_dedup[key_cols].isnull().sum(axis=1) / len(key_cols)
        quarantine_mask = null_pct > 0.5
        quarantine_df = df_dedup[quarantine_mask].copy()
        valid_df = df_dedup[~quarantine_mask].copy()
    else:
        quarantine_df = pd.DataFrame()
        valid_df = df_dedup.copy()
    
    stats["rows_valid"] = len(valid_df)
    stats["rows_quarantined"] = len(quarantine_df)
    stats["columns"] = list(valid_df.columns)
    
    return valid_df, quarantine_df, stats
