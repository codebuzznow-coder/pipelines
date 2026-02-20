"""
Survey Q&A Application - Clean, minimal version with observability.

Usage:
    streamlit run app.py
"""
import os
import sys
import time
from pathlib import Path

import streamlit as st
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_pipeline.cache import read_cache, get_cache_stats, cache_exists
from observability import get_metrics

# Initialize metrics
metrics = get_metrics()

# Page config
st.set_page_config(
    page_title="Survey Q&A",
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


@st.cache_data(ttl=300)
def load_data():
    """Load data from cache."""
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
        st.title("📊 Survey Q&A")
        
        # Data info
        stats = get_cache_stats()
        if stats.get("exists"):
            st.success(f"Data loaded: {stats['rows']:,} rows")
            st.caption(f"Years: {stats.get('years', 'N/A')}")
            st.caption(f"Source: {stats.get('source', 'N/A')}")
        else:
            st.warning("No data cache found. Run the data pipeline first.")
        
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
            ["Visualization", "Metrics Dashboard"],
            label_visibility="collapsed"
        )


def render_visualization():
    """Main visualization page."""
    st.header("Ask a Question")
    
    if not cache_exists():
        st.error("No data available. Please run the data pipeline first.")
        st.code("cd data_pipeline && python run_pipeline.py --input /path/to/survey_data")
        return
    
    df, _ = load_data()
    if df is None or df.empty:
        st.error("Failed to load data from cache.")
        return
    
    # Query input
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input(
            "Your question",
            placeholder="e.g., Top 5 roles in USA",
            label_visibility="collapsed"
        )
    with col2:
        top_n = st.selectbox("Top N", [5, 10, 15, 20], index=1)
    
    # Quick examples
    st.caption("Examples: Top 5 roles in USA | Top 10 programming languages | Show developer roles")
    
    if query:
        start_time = time.time()
        metrics.increment("queries_total")
        metrics.event("query", query)
        
        try:
            # Simple query parsing
            query_lower = query.lower()
            country_filter = None
            if "usa" in query_lower or "united states" in query_lower:
                country_filter = "United States"
            
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
    elif nav == "Metrics Dashboard":
        render_metrics_dashboard()
    
    # Footer
    st.divider()
    st.caption("Survey Q&A | Metrics persist across restarts")


if __name__ == "__main__":
    main()
