"""Stage 3: Enrich data (add derived fields, labels)."""
import pandas as pd
from typing import Dict, Any, Tuple

REGION_MAP = {
    "United States": "North America",
    "Canada": "North America",
    "Mexico": "North America",
    "United Kingdom": "Europe",
    "Germany": "Europe",
    "France": "Europe",
    "Netherlands": "Europe",
    "Spain": "Europe",
    "Italy": "Europe",
    "Poland": "Europe",
    "Sweden": "Europe",
    "India": "Asia",
    "China": "Asia",
    "Japan": "Asia",
    "Singapore": "Asia",
    "Australia": "Oceania",
    "New Zealand": "Oceania",
    "Brazil": "South America",
    "Argentina": "South America",
    "South Africa": "Africa",
    "Nigeria": "Africa",
}


def enrich_data(df: pd.DataFrame, source_label: str = "pipeline") -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Enrich survey data with derived fields.
    
    Adds:
        - year_label: Clean string year for display
        - region_group: Continent/region from country
        - _source: Pipeline source label
        - _enriched_at: Timestamp
    """
    stats = {
        "rows_in": len(df),
        "fields_added": []
    }
    
    out = df.copy()
    
    # Year label (clean string)
    if "survey_year" in out.columns:
        out["year_label"] = (
            out["survey_year"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )
        stats["fields_added"].append("year_label")
    
    # Region group from country
    if "Country" in out.columns:
        out["region_group"] = out["Country"].map(REGION_MAP).fillna("Other")
        stats["fields_added"].append("region_group")
    
    # Experience bucket
    if "WorkExp" in out.columns:
        out["experience_bucket"] = pd.cut(
            out["WorkExp"],
            bins=[-1, 2, 5, 10, 20, 100],
            labels=["0-2 years", "3-5 years", "6-10 years", "11-20 years", "20+ years"]
        )
        stats["fields_added"].append("experience_bucket")
    
    # Compensation tier
    if "ConvertedCompYearly" in out.columns:
        out["comp_tier"] = pd.cut(
            out["ConvertedCompYearly"],
            bins=[-1, 50000, 100000, 150000, 200000, float("inf")],
            labels=["<50k", "50-100k", "100-150k", "150-200k", "200k+"]
        )
        stats["fields_added"].append("comp_tier")
    
    # Pipeline metadata
    out["_source"] = source_label
    out["_enriched_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    stats["fields_added"].extend(["_source", "_enriched_at"])
    
    stats["rows_out"] = len(out)
    return out, stats
