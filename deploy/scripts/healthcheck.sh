#!/bin/bash
# Health check script for the application

set -e

APP_URL="${1:-http://localhost:8501}"

echo "Checking health: $APP_URL"

# Check Streamlit health endpoint
if curl -sf "$APP_URL/_stcore/health" > /dev/null; then
    echo "Health check: PASSED"
    exit 0
else
    echo "Health check: FAILED"
    exit 1
fi
