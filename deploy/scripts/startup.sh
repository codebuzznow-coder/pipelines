#!/bin/bash
# Container startup script

set -e

echo "=== Survey Q&A Startup ==="
echo "Time: $(date -Iseconds)"

# Sync data from S3 if configured
if [ -n "$S3_DATA_BUCKET" ]; then
    echo "Syncing data from S3..."
    aws s3 sync "s3://$S3_DATA_BUCKET/survey-data/" /app/survey_data/ || echo "S3 sync failed (continuing)"
    
    if [ -n "$S3_CACHE_PATH" ]; then
        echo "Copying cache from S3..."
        aws s3 cp "$S3_CACHE_PATH" /app/data/cache/survey_cache.db || echo "Cache copy failed (continuing)"
    fi
fi

# Run data pipeline if no cache exists and data is available
if [ ! -f /app/data/cache/survey_cache.db ] && [ -d /app/survey_data ] && [ "$(ls -A /app/survey_data 2>/dev/null)" ]; then
    echo "No cache found. Running data pipeline..."
    cd /app
    python -m data_pipeline.run_pipeline --input /app/survey_data --sample-pct 5 || echo "Pipeline failed (continuing)"
fi

# Check cache status
if [ -f /app/data/cache/survey_cache.db ]; then
    echo "Cache found: $(ls -lh /app/data/cache/survey_cache.db)"
else
    echo "WARNING: No data cache. App may not work correctly."
fi

# Start Streamlit
echo "Starting Streamlit..."
cd /app/app
exec streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
