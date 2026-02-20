#!/bin/bash
# Run all pipelines in sequence
# Usage: ./scripts/run_all.sh [survey_data_path]

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SURVEY_DATA="${1:-$ROOT/survey_data}"

echo "============================================================"
echo "Survey Q&A - Full Pipeline Run"
echo "============================================================"
echo "Survey data: $SURVEY_DATA"
echo ""

# Check for survey data
if [ ! -d "$SURVEY_DATA" ] || [ -z "$(ls -A "$SURVEY_DATA" 2>/dev/null)" ]; then
    echo "ERROR: No survey data found in $SURVEY_DATA"
    echo "Add survey CSV files and try again."
    exit 1
fi

# 1. Data Pipeline
echo ""
echo "============================================================"
echo "[1/3] Data Pipeline"
echo "============================================================"
cd "$ROOT/data_pipeline"
python3 run_pipeline.py --input "$SURVEY_DATA" --sample-pct 5

# 2. Verify cache
echo ""
echo "============================================================"
echo "[2/3] Verify Cache"
echo "============================================================"
python3 -c "
from cache import get_cache_stats
stats = get_cache_stats()
if stats.get('exists'):
    print(f'Cache OK: {stats[\"rows\"]} rows, {stats[\"size_mb\"]} MB')
    print(f'Years: {stats.get(\"years\", \"N/A\")}')
else:
    print('ERROR: Cache not created')
    exit(1)
"

# 3. Test app
echo ""
echo "============================================================"
echo "[3/3] Test Application"
echo "============================================================"
cd "$ROOT/app"
python3 -c "
import sys
sys.path.insert(0, '..')
from data_pipeline.cache import read_cache
from observability import get_metrics

# Test cache read
df, _ = read_cache()
if df is None or df.empty:
    print('ERROR: Could not read cache')
    exit(1)
print(f'Data loaded: {len(df)} rows')

# Test metrics
m = get_metrics()
m.increment('test_counter')
print(f'Metrics OK: test_counter = {m.get_counter(\"test_counter\")}')

print('Application test: PASSED')
"

echo ""
echo "============================================================"
echo "All pipelines completed successfully!"
echo "============================================================"
echo ""
echo "To run the app locally:"
echo "  cd app && streamlit run app.py"
echo ""
echo "To deploy to AWS:"
echo "  cd infra && ./scripts/apply.sh"
echo "  cd deploy && ./scripts/deploy.sh <ec2-ip>"
