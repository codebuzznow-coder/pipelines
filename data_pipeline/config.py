"""Data pipeline configuration."""
import os
from pathlib import Path

PIPELINE_ROOT = Path(__file__).parent.parent
DATA_DIR = PIPELINE_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
STAGE_DIR = DATA_DIR / "stages"

CACHE_DB_NAME = "survey_cache.db"
METRICS_DB_NAME = "metrics.db"

SAMPLE_PCT = 0.05
MIN_SAMPLES_PER_STRATUM = 1
RANDOM_SEED = 42

ROLE_COLUMN = "DevType"
YEAR_COLUMN = "survey_year"

REQUIRED_COLUMNS = ["ResponseId", "Country"]
KEY_COLUMNS = ["ResponseId", ROLE_COLUMN, YEAR_COLUMN]

STAGE_NAMES = ["01_sample", "02_validate", "03_transform", "04_enrich"]


def ensure_dirs():
    """Create necessary directories."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    for stage in STAGE_NAMES:
        (STAGE_DIR / stage).mkdir(parents=True, exist_ok=True)


def get_cache_path() -> Path:
    ensure_dirs()
    return CACHE_DIR / CACHE_DB_NAME


def get_metrics_path() -> Path:
    ensure_dirs()
    return CACHE_DIR / METRICS_DB_NAME
