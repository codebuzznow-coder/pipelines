"""Observability configuration."""
from pathlib import Path

METRICS_CONFIG = {
    "db_path": Path(__file__).parent.parent.parent / "data" / "cache" / "metrics.db",
    "retention_days": 30,
    "flush_interval_seconds": 10,
}
