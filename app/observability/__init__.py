"""Observability module: persistent metrics that survive restarts."""
from .metrics import MetricsCollector, get_metrics
from .config import METRICS_CONFIG

__all__ = ["MetricsCollector", "get_metrics", "METRICS_CONFIG"]
