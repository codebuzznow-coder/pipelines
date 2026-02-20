"""
Persistent metrics collector using SQLite.

Metrics survive application and database restarts because they're stored
in a separate SQLite database file.

Usage:
    from observability import get_metrics
    
    metrics = get_metrics()
    metrics.increment("queries_total")
    metrics.gauge("active_users", 5)
    metrics.timing("query_duration_ms", 150)
    metrics.histogram("response_size_bytes", 1024)
"""
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from .config import METRICS_CONFIG


class MetricsCollector:
    """Thread-safe, persistent metrics collector backed by SQLite."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or METRICS_CONFIG["db_path"]
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize metrics tables."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER DEFAULT 0,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gauges (
                    name TEXT PRIMARY KEY,
                    value REAL,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS timings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_data TEXT,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timings_name ON timings(name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timings_recorded ON timings(recorded_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            conn.commit()
    
    @contextmanager
    def _get_conn(self):
        """Get a database connection with WAL mode for concurrent access."""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
        finally:
            conn.close()
    
    def increment(self, name: str, value: int = 1) -> int:
        """Increment a counter, return new value."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO counters (name, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET value = value + ?, updated_at = ?
                """, (name, value, now, value, now))
                conn.commit()
                cur = conn.execute("SELECT value FROM counters WHERE name = ?", (name,))
                return cur.fetchone()[0]
    
    def gauge(self, name: str, value: float):
        """Set a gauge value."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO gauges (name, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET value = ?, updated_at = ?
                """, (name, value, now, value, now))
                conn.commit()
    
    def timing(self, name: str, value_ms: float):
        """Record a timing measurement."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO timings (name, value, recorded_at) VALUES (?, ?, ?)",
                    (name, value_ms, now)
                )
                conn.commit()
    
    def event(self, event_type: str, data: Optional[str] = None):
        """Record an event."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO events (event_type, event_data, recorded_at) VALUES (?, ?, ?)",
                    (event_type, data, now)
                )
                conn.commit()
    
    def get_counter(self, name: str) -> int:
        """Get current counter value."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT value FROM counters WHERE name = ?", (name,))
            row = cur.fetchone()
            return row[0] if row else 0
    
    def get_gauge(self, name: str) -> Optional[float]:
        """Get current gauge value."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT value FROM gauges WHERE name = ?", (name,))
            row = cur.fetchone()
            return row[0] if row else None
    
    def get_timing_stats(self, name: str, hours: int = 24) -> Dict[str, Any]:
        """Get timing statistics for the last N hours."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute("""
                SELECT 
                    COUNT(*) as count,
                    AVG(value) as avg,
                    MIN(value) as min,
                    MAX(value) as max
                FROM timings 
                WHERE name = ? AND recorded_at > ?
            """, (name, cutoff))
            row = cur.fetchone()
            return {
                "count": row[0],
                "avg_ms": round(row[1], 2) if row[1] else 0,
                "min_ms": round(row[2], 2) if row[2] else 0,
                "max_ms": round(row[3], 2) if row[3] else 0,
            }
    
    def get_all_counters(self) -> Dict[str, int]:
        """Get all counter values."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT name, value FROM counters")
            return {row[0]: row[1] for row in cur.fetchall()}
    
    def get_all_gauges(self) -> Dict[str, float]:
        """Get all gauge values."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT name, value FROM gauges")
            return {row[0]: row[1] for row in cur.fetchall()}
    
    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get recent events."""
        with self._get_conn() as conn:
            if event_type:
                cur = conn.execute(
                    "SELECT event_type, event_data, recorded_at FROM events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                    (event_type, limit)
                )
            else:
                cur = conn.execute(
                    "SELECT event_type, event_data, recorded_at FROM events ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [
                {"type": row[0], "data": row[1], "recorded_at": row[2]}
                for row in cur.fetchall()
            ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            "counters": self.get_all_counters(),
            "gauges": self.get_all_gauges(),
            "timing_stats": {
                "query_duration_ms": self.get_timing_stats("query_duration_ms"),
            },
            "recent_events_count": len(self.get_recent_events(limit=1000)),
        }
    
    def cleanup_old_data(self, days: int = None):
        """Remove old timing and event data."""
        days = days or METRICS_CONFIG["retention_days"]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM timings WHERE recorded_at < ?", (cutoff,))
                conn.execute("DELETE FROM events WHERE recorded_at < ?", (cutoff,))
                conn.commit()


# Singleton instance
_metrics_instance: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_instance
    if _metrics_instance is None:
        with _metrics_lock:
            if _metrics_instance is None:
                _metrics_instance = MetricsCollector()
    return _metrics_instance
