"""Stage 2: Transform data (type coercion, cleaning, normalization)."""
import pandas as pd
import re
from typing import Dict, Any, Tuple


def transform_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Transform and clean survey data.
    
    - Coerce types (numeric columns, strings)
    - Normalize text fields
    - Clean compensation data
    - Standardize year format
    """
    stats = {
        "rows_in": len(df),
        "transforms_applied": []
    }
    
    out = df.copy()
    
    # Normalize survey_year: "2024.0" -> "2024"
    if "survey_year" in out.columns:
        out["survey_year"] = (
            out["survey_year"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )
        stats["transforms_applied"].append("normalized survey_year")
    
    # Clean compensation columns
    comp_cols = ["CompTotal", "ConvertedCompYearly"]
    for col in comp_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
            # Remove outliers: negative or > 10M
            mask = (out[col] < 0) | (out[col] > 10_000_000)
            out.loc[mask, col] = None
            stats["transforms_applied"].append(f"cleaned {col}")
    
    # Normalize country names
    if "Country" in out.columns:
        country_map = {
            "USA": "United States",
            "United States of America": "United States",
            "UK": "United Kingdom",
            "Great Britain": "United Kingdom",
        }
        out["Country"] = out["Country"].replace(country_map)
        stats["transforms_applied"].append("normalized Country")
    
    # Strip whitespace from string columns
    str_cols = out.select_dtypes(include=["object"]).columns
    for col in str_cols:
        out[col] = out[col].astype(str).str.strip().replace({"nan": "", "None": ""})
    stats["transforms_applied"].append(f"stripped whitespace ({len(str_cols)} columns)")
    
    # Normalize WorkExp to numeric
    if "WorkExp" in out.columns:
        out["WorkExp"] = pd.to_numeric(out["WorkExp"], errors="coerce")
        stats["transforms_applied"].append("converted WorkExp to numeric")
    
    stats["rows_out"] = len(out)
    return out, stats
