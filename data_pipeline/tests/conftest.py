"""Pytest configuration - adds data_pipeline to path."""
import sys
from pathlib import Path

data_pipeline_root = Path(__file__).parent.parent
sys.path.insert(0, str(data_pipeline_root))
