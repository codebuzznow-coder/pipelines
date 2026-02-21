"""SQLite cache for survey data."""
import sqlite3
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import pandas as pd

try:
    from config import get_cache_path
except ImportError:
    from .config import get_cache_path

DATA_TABLE = "survey_data"
META_TABLE = "cache_meta"
CHUNK_SIZE = 5000


def build_cache(df: pd.DataFrame, source: str = "pipeline") -> Dict[str, Any]:
    """
    Write DataFrame to SQLite cache.
    
    Returns:
        {"ok": True, "rows": n, "path": str} or {"ok": False, "message": str}
    """
    path = get_cache_path()
    try:
        out = df.copy()
        for col in out.columns:
            # Convert to string first so Categorical columns don't raise on fillna("")
            out[col] = out[col].astype(str).fillna("").replace("nan", "")
        
        conn = sqlite3.connect(str(path))
        out.to_sql(DATA_TABLE, conn, if_exists="replace", index=False, chunksize=CHUNK_SIZE)
        
        # Store metadata
        years_val = ""
        if "survey_year" in out.columns:
            yrs = out["survey_year"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
            years_val = ", ".join(sorted(set(yrs.unique()) - {"", "nan", "None"}))
        
        conn.execute(f"CREATE TABLE IF NOT EXISTS {META_TABLE} (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(f"DELETE FROM {META_TABLE}")
        conn.execute(
            f"INSERT INTO {META_TABLE} (key, value) VALUES (?, ?), (?, ?), (?, ?)",
            ("built_at", datetime.now(timezone.utc).isoformat(), "source", source, "years", years_val),
        )
        conn.commit()
        conn.close()
        
        return {"ok": True, "rows": len(out), "path": str(path), "years": years_val}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def read_cache(year: Optional[str] = None) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Read survey data from SQLite cache.
    
    Returns:
        (df, year) or (None, None) if cache missing
    """
    path = get_cache_path()
    if not path.exists():
        return None, None
    
    try:
        conn = sqlite3.connect(str(path))
        if year:
            df = pd.read_sql_query(
                f"SELECT * FROM {DATA_TABLE} WHERE survey_year = ?",
                conn,
                params=(str(year),),
            )
            conn.close()
            return df, str(year)
        
        df = pd.read_sql_query(f"SELECT * FROM {DATA_TABLE}", conn)
        conn.close()
        return df, None
    except Exception:
        return None, None


def get_cache_stats() -> Dict[str, Any]:
    """Return cache statistics."""
    path = get_cache_path()
    if not path.exists():
        return {"exists": False}
    
    try:
        size_bytes = os.path.getsize(path)
        conn = sqlite3.connect(str(path))
        
        cur = conn.execute(f"SELECT COUNT(*) FROM {DATA_TABLE}")
        rows = cur.fetchone()[0]
        
        meta = {}
        try:
            cur = conn.execute(f"SELECT key, value FROM {META_TABLE}")
            for k, v in cur.fetchall():
                meta[k] = v
        except Exception:
            pass
        
        conn.close()
        
        return {
            "exists": True,
            "path": str(path),
            "rows": rows,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "built_at": meta.get("built_at", ""),
            "source": meta.get("source", ""),
            "years": meta.get("years", ""),
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}


def cache_exists() -> bool:
    """Check if cache exists."""
    return get_cache_path().exists()
