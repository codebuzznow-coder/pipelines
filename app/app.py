"""
CodeBuzz - Survey Q&A Application. Clean, minimal version with observability.

Usage:
    streamlit run app.py

Optional: add OPENAI_API_KEY=sk-... to app/.env. Do not commit .env; it is in .gitignore.
"""
import os
import sys
import time
from pathlib import Path

# Load .env from project root or app dir (so OPENAI_API_KEY is available without UI)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

import streamlit as st
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.cache import read_cache, get_cache_stats, cache_exists
from data_pipeline.run_pipeline import run_pipeline
from data_pipeline.validations import run_all_validations
from data_pipeline.evals import run_all_evals
from observability import get_metrics
from query_parsing import parse_query_with_openai, parse_query_keyword, test_openai_api

# Initialize metrics
metrics = get_metrics()

# Page config
st.set_page_config(
    page_title="CodeBuzz - Survey Q&A",
    page_icon="📊",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .main { padding: 1rem 2rem; }
    .metric-card { 
        background: #1e1e1e; 
        padding: 1rem; 
        border-radius: 8px; 
        margin: 0.5rem 0;
    }
    .stMetric { background: #262626; padding: 1rem; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load_data():
    """Load data from cache (TTL 60s so new pipeline data appears within a minute)."""
    df, year = read_cache()
    return df, year


def get_role_distribution(df: pd.DataFrame, country_filter: str = None, top_n: int = 10):
    """Get top roles from data."""
    data = df.copy()
    
    if country_filter:
        mask = data["Country"].astype(str).str.contains(country_filter, case=False, na=False)
        data = data[mask]
    
    if "DevType" not in data.columns:
        return []
    
    roles = []
    for value in data["DevType"].dropna():
        if ";" in str(value):
            roles.extend([r.strip() for r in str(value).split(";") if r.strip()])
        else:
            if str(value).strip() and str(value) != "nan":
                roles.append(str(value).strip())
    
    from collections import Counter
    return Counter(roles).most_common(top_n)


def render_sidebar():
    """Render sidebar with metrics and info."""
    with st.sidebar:
        st.title("📊 CodeBuzz – Survey Q&A")
        
        # Data info
        stats = get_cache_stats()
        if stats.get("exists"):
            st.success(f"Data loaded: {stats['rows']:,} rows")
            st.caption(f"Years: {stats.get('years', 'N/A')}")
            st.caption(f"Source: {stats.get('source', 'N/A')}")
        else:
            st.warning("No data cache found. Use the **Data Pipeline** tab below to upload and run, or run the GitHub workflow with your S3 path.")
        
        if st.button("🔄 Refresh data", key="sidebar_refresh_data"):
            load_data.clear()
            st.rerun()
        
        st.divider()
        
        # Metrics summary
        st.subheader("Observability")
        m = get_metrics()
        counters = m.get_all_counters()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Queries", counters.get("queries_total", 0))
        with col2:
            st.metric("Errors", counters.get("errors_total", 0))
        
        timing = m.get_timing_stats("query_duration_ms", hours=24)
        if timing["count"] > 0:
            st.caption(f"Avg query time: {timing['avg_ms']:.0f}ms (last 24h)")
        
        st.divider()
        
        # Navigation
        st.subheader("Navigation")
        return st.radio(
            "Section",
            ["Visualization", "Data Pipeline", "Validations & Evals", "Metrics Dashboard"],
            label_visibility="collapsed"
        )


def render_visualization():
    """Main visualization page."""
    st.header("Ask a Question")
    
    if not cache_exists():
        st.error("No data available. Load data first:")
        st.markdown("1. **If you ran the Run Data Pipeline GitHub Action:** click **🔄 Refresh data** in the sidebar — the cache is already on the server.")
        st.markdown("2. **Otherwise:** go to **Data Pipeline** in the sidebar and upload CSV/ZIP files, then Run Pipeline.")
        return
    
    df, _ = load_data()
    if df is None or df.empty:
        st.error("Failed to load data from cache.")
        return
    
    # Query settings: optional OpenAI
    with st.expander("⚙️ Query settings (optional OpenAI)"):
        use_openai = st.checkbox(
            "Use OpenAI to interpret questions",
            value=st.session_state.get("query_use_openai", False),
            key="query_use_openai",
            help="Convert your question to filters/parameters via OpenAI. Otherwise keyword parsing is used.",
        )
        # API key: from .env, Streamlit secrets, or UI (do not commit .env; it's in .gitignore)
        env_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        try:
            secret_key = (st.secrets.get("OPENAI_API_KEY") or "").strip()
        except Exception:
            secret_key = ""
        openai_key = st.text_input(
            "OpenAI API key",
            value=st.session_state.get("openai_api_key", ""),
            type="password",
            placeholder="sk-..." if not (env_key or secret_key) else "•••••••• (from app/.env)",
            key="openai_api_key_input",
            help="Optional. Or add OPENAI_API_KEY to app/.env.",
        )
        if openai_key:
            st.session_state["openai_api_key"] = openai_key.strip()
        else:
            st.session_state["openai_api_key"] = ""
        # Effective key: UI > .env > Streamlit secrets (never show secret in UI)
        effective_api_key = (st.session_state.get("openai_api_key") or env_key or secret_key).strip()
        if use_openai and not effective_api_key:
            st.caption("Enter an API key above, or add OPENAI_API_KEY to app/.env.")
        if effective_api_key:
            if st.button("Test API", key="test_openai_btn"):
                ok, msg = test_openai_api(effective_api_key)
                if ok:
                    st.success(msg)
                else:
                    st.error("API test failed: " + msg)
    
    # Query input
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Your question",
            placeholder="e.g., Top 5 roles in USA",
            label_visibility="collapsed"
        )
    with col2:
        default_top_n = st.selectbox("Top N", [5, 10, 15, 20], index=1)
    
    # How it works
    with st.expander("ℹ️ How queries work"):
        st.markdown("""
        - **With OpenAI (Query settings):** Your question is sent to the API and converted into **structured parameters** (country filter, top N). Then we aggregate from the cached survey data in memory.
        - **Without OpenAI:** **Keyword parsing** in Python (e.g. *USA* → United States filter). Data is from the **SQLite cache**; results are **aggregated in Python**. No SQL is generated.
        """)
    
    st.caption("Examples: Top 5 roles in USA | Top 10 programming languages | Show developer roles")
    
    if query:
        start_time = time.time()
        metrics.increment("queries_total")
        metrics.event("query", query)
        
        try:
            country_filter = None
            top_n = default_top_n
            interpretation = ""
            effective_key = (st.session_state.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
            try:
                effective_key = effective_key or (st.secrets.get("OPENAI_API_KEY") or "").strip()
            except Exception:
                pass
            use_openai_now = use_openai and effective_key

            if use_openai_now:
                country_filter, top_n, interpretation, err = parse_query_with_openai(
                    effective_key, query, default_top_n
                )
                if err:
                    st.warning(f"OpenAI parsing failed ({err}). Using keyword fallback.")
                    country_filter, top_n, interpretation = parse_query_keyword(query, default_top_n)
                    interpretation = "Keyword fallback: " + interpretation
                else:
                    interpretation = "OpenAI: " + (interpretation or "")
            else:
                country_filter, top_n, interpretation = parse_query_keyword(query, default_top_n)
                interpretation = "Keyword: " + interpretation

            st.info("**Query interpretation:** " + interpretation)
            
            # Get results
            results = get_role_distribution(df, country_filter=country_filter, top_n=top_n)
            
            if results:
                # Display results
                result_df = pd.DataFrame(results, columns=["Role", "Count"])
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader("Results")
                    st.dataframe(result_df, use_container_width=True, hide_index=True)
                
                with col2:
                    st.subheader("Chart")
                    st.bar_chart(result_df.set_index("Role")["Count"])
                
                # Record timing
                duration_ms = (time.time() - start_time) * 1000
                metrics.timing("query_duration_ms", duration_ms)
                st.caption(f"Query completed in {duration_ms:.0f}ms")
            else:
                st.info("No results found for your query.")
                
        except Exception as e:
            metrics.increment("errors_total")
            metrics.event("error", str(e))
            st.error(f"Error processing query: {e}")


def render_data_pipeline():
    """Data pipeline runner page."""
    st.header("Run Data Pipeline")
    
    st.info("Upload CSV files to process through the data pipeline: sample → validate → transform → enrich → cache")
    
    # File upload
    uploaded_files = st.file_uploader(
        "Upload Survey Data (CSV or ZIP)",
        type=["csv", "zip"],
        accept_multiple_files=True,
        help="Upload CSV files or ZIP archives containing survey CSVs"
    )
    
    if uploaded_files:
        st.success(f"{len(uploaded_files)} file(s) uploaded")
        
        # Pipeline options
        col1, col2 = st.columns(2)
        with col1:
            sample_pct = st.slider("Sample Percentage", 1, 100, 5, help="Percentage of data to sample (stratified by role)")
        with col2:
            seed = st.number_input("Random Seed", value=42, help="Seed for reproducible sampling")
        
        # Run button
        if st.button("🚀 Run Pipeline", type="primary", use_container_width=True):
            if not uploaded_files:
                st.error("Please upload at least one CSV file")
                return
            
            # Create temp directory for uploaded files
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / "uploaded_data"
                tmp_path.mkdir()
                
                # Save uploaded files
                for uploaded_file in uploaded_files:
                    file_path = tmp_path / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                # Show progress and live log
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_placeholder = st.empty()
                log_lines = []
                
                def _stage_progress(msg: str) -> int:
                    if "[1/6]" in msg:
                        return 16
                    if "[2/6]" in msg:
                        return 33
                    if "[3/6]" in msg:
                        return 50
                    if "[4/6]" in msg:
                        return 66
                    if "[5/6]" in msg:
                        return 83
                    if "[6/6]" in msg:
                        return 95
                    return None
                
                def log_callback(msg: str):
                    log_lines.append(msg)
                    pct = _stage_progress(msg)
                    if pct is not None:
                        progress_bar.progress(pct)
                    with log_placeholder.container():
                        st.code("\n".join(log_lines), language=None)
                
                try:
                    status_text.text("Starting pipeline...")
                    progress_bar.progress(5)
                    
                    # Run pipeline with live log
                    result = run_pipeline(
                        input_path=str(tmp_path),
                        sample_pct=sample_pct / 100.0,
                        seed=int(seed),
                        skip_cache=False,
                        log_callback=log_callback,
                    )
                    
                    progress_bar.progress(100)
                    status_text.empty()
                    
                    if result.get("ok"):
                        st.success("✅ Pipeline completed successfully!")
                        
                        # Show results
                        st.subheader("Pipeline Results")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Rows Loaded", f"{result['stages']['load']['rows']:,}")
                        with col2:
                            st.metric("Valid Rows", f"{result['stages']['validate']['rows_valid']:,}")
                        with col3:
                            st.metric("Final Sample", f"{result['stages']['sample']['rows_out']:,}")
                        
                        if result.get("cache", {}).get("ok"):
                            st.success(f"✅ Cache built: {result['cache']['rows']:,} rows")
                            # Bump cache key so Visualization will re-read from disk when user switches tabs
                            load_data.clear()
                        
                        # Show stage details
                        with st.expander("View Stage Details"):
                            st.json(result)
                        
                        st.info("🔄 Switch to **Visualization** in the sidebar to see the data.")
                        
                    else:
                        st.error(f"❌ Pipeline failed: {result.get('error', 'Unknown error')}")
                        if "stages" in result:
                            st.json(result)
                            
                except Exception as e:
                    st.error(f"❌ Error running pipeline: {e}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
    
    # Show current cache status
    st.divider()
    st.subheader("Current Cache Status")
    stats = get_cache_stats()
    if stats.get("exists"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rows", f"{stats['rows']:,}")
        with col2:
            st.metric("Size", f"{stats['size_mb']} MB")
        with col3:
            st.metric("Years", stats.get("years", "N/A"))
        
        if st.button("🗑️ Clear Cache", type="secondary"):
            cache_path = Path(stats["path"])
            if cache_path.exists():
                cache_path.unlink()
                st.success("Cache cleared! Upload new data to rebuild.")
                st.rerun()
    else:
        st.info("No cache found. Upload and process data to create a cache.")


def render_validations_evals():
    """Validations and evals report with graphs."""
    st.header("Validations & Evals")
    st.caption("Runs cache/data validations and query/data evals. Same logic as `python scripts/run_validations_evals.py`.")

    min_rows = st.number_input("Min rows (validations)", value=1, min_value=1, key="ve_min_rows")
    openai_key = (os.environ.get("OPENAI_API_KEY") or st.session_state.get("openai_api_key") or "").strip()
    if st.button("Run Validations & Evals", type="primary"):
        with st.spinner("Running validations and evals..."):
            v_results = run_all_validations(min_rows=int(min_rows))
            e_results = run_all_evals(openai_api_key=openai_key or None)

        v_passed = sum(1 for r in v_results if r.get("passed"))
        v_total = len(v_results)
        eval_scores = [r.get("score", 0) for r in e_results]
        avg_eval = (sum(eval_scores) / len(eval_scores) * 100) if eval_scores else 0

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Validations passed", f"{v_passed}/{v_total}")
        with col2:
            st.metric("Evals average", f"{avg_eval:.0f}%")
        with col3:
            st.metric("Status", "All passed" if v_passed == v_total else "Some failed")

        # Graph: Validations (pass/fail per check)
        st.subheader("Validations")
        v_df = pd.DataFrame([
            {"Validation": r["name"], "Passed": 1 if r.get("passed") else 0, "Status": "Pass" if r.get("passed") else "Fail"}
            for r in v_results
        ])
        st.bar_chart(v_df.set_index("Validation")[["Passed"]], color="#28a745")
        for r in v_results:
            icon = "✓" if r.get("passed") else "✗"
            st.caption(f"{icon} **{r['name']}**: {r['message']}")

        # Graph: Eval scores
        st.subheader("Eval scores")
        e_df = pd.DataFrame([
            {"Eval": r["name"], "Score %": round(r.get("score", 0) * 100)}
            for r in e_results
        ])
        st.bar_chart(e_df.set_index("Eval")[["Score %"]], color="#17a2b8")
        for r in e_results:
            pct = r.get("score", 0) * 100
            st.caption(f"**{r['name']}**: {r['message']} ({pct:.0f}%)")

        # JSON report download
        import json
        from datetime import datetime, timezone
        report = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "validations": {"passed": v_passed, "total": v_total, "all_passed": v_passed == v_total, "results": v_results},
            "evals": {"results": e_results, "average_score": sum(eval_scores) / len(eval_scores) if eval_scores else 0},
        }
        st.download_button(
            "Download report (JSON)",
            data=json.dumps(report, indent=2, default=str),
            file_name=f"validations_evals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="ve_download",
        )
        return

    # Where to run from CLI
    with st.expander("Where are validations and evals defined?"):
        st.markdown("""
        - **Validations:** `data_pipeline/validations.py` — cache exists, readable, required columns, min rows, metadata, key columns non-empty.
        - **Evals:** `data_pipeline/evals.py` — keyword query parsing, data coverage, role spread, optional OpenAI parsing.
        - **CLI:** From project root: `python scripts/run_validations_evals.py` or `python scripts/run_validations_evals.py --json report.json`
        """)


def render_metrics_dashboard():
    """Metrics and observability dashboard."""
    st.header("Observability Dashboard")
    
    m = get_metrics()
    
    # Counters
    st.subheader("Counters")
    counters = m.get_all_counters()
    if counters:
        cols = st.columns(min(len(counters), 4))
        for i, (name, value) in enumerate(counters.items()):
            with cols[i % len(cols)]:
                st.metric(name.replace("_", " ").title(), value)
    else:
        st.info("No counter data yet.")
    
    # Timing stats
    st.subheader("Query Performance (Last 24h)")
    timing = m.get_timing_stats("query_duration_ms", hours=24)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Queries", timing["count"])
    with col2:
        st.metric("Avg Duration", f"{timing['avg_ms']:.0f}ms")
    with col3:
        st.metric("Min Duration", f"{timing['min_ms']:.0f}ms")
    with col4:
        st.metric("Max Duration", f"{timing['max_ms']:.0f}ms")
    
    # Recent events
    st.subheader("Recent Events")
    events = m.get_recent_events(limit=20)
    if events:
        events_df = pd.DataFrame(events)
        st.dataframe(events_df, use_container_width=True, hide_index=True)
    else:
        st.info("No events recorded yet.")
    
    # Cleanup button
    st.divider()
    if st.button("Cleanup Old Data (30+ days)"):
        m.cleanup_old_data(days=30)
        st.success("Old metrics data cleaned up.")
        st.rerun()


def main():
    """Main application entry point."""
    # Record app start
    metrics.gauge("app_last_start", time.time())
    metrics.increment("app_starts_total")
    
    # Render sidebar and get navigation choice
    nav = render_sidebar()
    
    # Render selected page
    if nav == "Visualization":
        render_visualization()
    elif nav == "Data Pipeline":
        render_data_pipeline()
    elif nav == "Validations & Evals":
        render_validations_evals()
    elif nav == "Metrics Dashboard":
        render_metrics_dashboard()
    
    # Footer
    st.divider()
    st.caption("CodeBuzz – Survey Q&A | Metrics persist across restarts")


if __name__ == "__main__":
    main()
