#!/usr/bin/env bash
# Run the CodeBuzz Streamlit app from the project root.
# Usage: ./scripts/run_app.sh   (from pipeline directory)
#    or: scripts/run_app.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Use venv if present
if [ -d "$ROOT/.venv/bin" ]; then
  source "$ROOT/.venv/bin/activate"
elif [ -d "$ROOT/venv/bin" ]; then
  source "$ROOT/venv/bin/activate"
fi

# Ensure Streamlit is available
if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "Installing app dependencies (run once)..."
  pip3 install -r app/requirements.txt
fi

echo "Starting CodeBuzz app at http://localhost:8501"
echo "Stop with Ctrl+C. Login via app/.env (APP_USERNAME / APP_PASSWORD)"
exec python3 -m streamlit run app/app.py --server.port 8501 --server.headless true
