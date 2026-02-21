"""
Validations for the survey cache and pipeline outputs.

Each validation returns a dict: {"name", "passed", "message", "details"}.
Run via scripts/run_validations_evals.py for a clear report.
"""
from pathlib import Path
from typing import Any, Dict, List

try:
    from config import get_cache_path, REQUIRED_COLUMNS, ROLE_COLUMN, YEAR_COLUMN
    from cache import read_cache, get_cache_stats, DATA_TABLE, META_TABLE
except ImportError:
    from .config import get_cache_path, REQUIRED_COLUMNS, ROLE_COLUMN, YEAR_COLUMN
    from .cache import read_cache, get_cache_stats, DATA_TABLE, META_TABLE


def validation_cache_exists() -> Dict[str, Any]:
    """Check that the SQLite cache file exists."""
    path = get_cache_path()
    exists = path.exists()
    return {
        "name": "cache_exists",
        "passed": exists,
        "message": "Cache file exists" if exists else "Cache file not found",
        "details": {"path": str(path)},
    }


def validation_cache_readable() -> Dict[str, Any]:
    """Check that the cache can be read and returns a non-empty dataframe."""
    df, _ = read_cache()
    passed = df is not None and not df.empty
    return {
        "name": "cache_readable",
        "passed": passed,
        "message": f"Cache readable, {len(df) if df is not None else 0} rows" if passed else "Cache unreadable or empty",
        "details": {"rows": len(df) if df is not None else 0},
    }


def validation_cache_required_columns() -> Dict[str, Any]:
    """Check that required columns (ResponseId, Country) and key columns (DevType) exist."""
    df, _ = read_cache()
    if df is None or df.empty:
        return {
            "name": "cache_required_columns",
            "passed": False,
            "message": "No data to validate",
            "details": {},
        }
    missing = [c for c in REQUIRED_COLUMNS + [ROLE_COLUMN] if c not in df.columns]
    passed = len(missing) == 0
    return {
        "name": "cache_required_columns",
        "passed": passed,
        "message": f"Required columns present" if passed else f"Missing columns: {missing}",
        "details": {"missing": missing, "columns": list(df.columns[:20])},
    }


def validation_cache_min_rows(min_rows: int = 1) -> Dict[str, Any]:
    """Check that the cache has at least min_rows rows."""
    df, _ = read_cache()
    if df is None:
        count = 0
    else:
        count = len(df)
    passed = count >= min_rows
    return {
        "name": "cache_min_rows",
        "passed": passed,
        "message": f"Row count {count} >= {min_rows}" if passed else f"Row count {count} < {min_rows}",
        "details": {"rows": count, "min_required": min_rows},
    }


def validation_cache_meta() -> Dict[str, Any]:
    """Check that cache metadata (built_at, source) exists."""
    import sqlite3
    path = get_cache_path()
    if not path.exists():
        return {"name": "cache_meta", "passed": False, "message": "Cache not found", "details": {}}
    try:
        conn = sqlite3.connect(str(path))
        cur = conn.execute(f"SELECT key, value FROM {META_TABLE}")
        meta = dict(cur.fetchall())
        conn.close()
        has_built_at = "built_at" in meta
        has_source = "source" in meta
        passed = has_built_at and has_source
        return {
            "name": "cache_meta",
            "passed": passed,
            "message": "Metadata present (built_at, source)" if passed else "Metadata missing",
            "details": {"built_at": meta.get("built_at"), "source": meta.get("source"), "years": meta.get("years")},
        }
    except Exception as e:
        return {"name": "cache_meta", "passed": False, "message": str(e), "details": {}}


def validation_key_columns_non_empty() -> Dict[str, Any]:
    """Check that key columns (DevType, Country) are not entirely null/empty."""
    df, _ = read_cache()
    if df is None or df.empty:
        return {"name": "key_columns_non_empty", "passed": False, "message": "No data", "details": {}}
    details = {}
    passed = True
    for col in [ROLE_COLUMN, "Country"]:
        if col not in df.columns:
            details[col] = "missing"
            passed = False
            continue
        non_null = df[col].astype(str).str.strip().replace("", None).notna().sum()
        total = len(df)
        pct = (non_null / total * 100) if total else 0
        details[col] = f"{non_null}/{total} ({pct:.1f}%) non-empty"
        if non_null == 0:
            passed = False
    return {
        "name": "key_columns_non_empty",
        "passed": passed,
        "message": "Key columns have data" if passed else "Some key columns are empty",
        "details": details,
    }


def run_all_validations(min_rows: int = 1) -> List[Dict[str, Any]]:
    """Run all validation checks. Returns list of result dicts."""
    validators = [
        validation_cache_exists,
        validation_cache_readable,
        validation_cache_required_columns,
        validation_cache_min_rows,
        validation_cache_meta,
        validation_key_columns_non_empty,
    ]
    results = []
    for v in validators:
        if v is validation_cache_min_rows:
            results.append(v(min_rows=min_rows))
        else:
            results.append(v())
    return results
