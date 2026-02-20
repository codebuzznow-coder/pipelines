#!/bin/bash
# Initial setup script
# Run from pipeline/ directory: ./scripts/setup.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Survey Q&A Pipeline Setup ==="

# Check prerequisites
echo ""
echo "[1/5] Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "Python 3 required but not found."; exit 1; }
echo "  Python: $(python3 --version)"

command -v terraform >/dev/null 2>&1 && echo "  Terraform: $(terraform version -json | python3 -c 'import sys,json; print(json.load(sys.stdin)["terraform_version"])')" || echo "  Terraform: not found (optional)"

command -v docker >/dev/null 2>&1 && echo "  Docker: $(docker --version)" || echo "  Docker: not found (required for deploy)"

command -v aws >/dev/null 2>&1 && echo "  AWS CLI: $(aws --version 2>&1 | cut -d' ' -f1)" || echo "  AWS CLI: not found (required for AWS deploy)"

# Create directories
echo ""
echo "[2/5] Creating directories..."
mkdir -p data/cache data/stages
mkdir -p survey_data
echo "  Created: data/, survey_data/"

# Install Python dependencies
echo ""
echo "[3/5] Installing Python dependencies..."
pip3 install -r app/requirements.txt --quiet
echo "  Dependencies installed."

# Make scripts executable
echo ""
echo "[4/5] Setting script permissions..."
chmod +x scripts/*.sh
chmod +x infra/scripts/*.sh
chmod +x deploy/scripts/*.sh
chmod +x data_pipeline/run_pipeline.py
echo "  Scripts are now executable."

# Verify structure
echo ""
echo "[5/5] Verifying project structure..."
echo "  infra/         - Terraform infrastructure"
echo "  data_pipeline/ - Data processing pipeline"
echo "  app/           - Streamlit application"
echo "  deploy/        - Docker and deployment"
echo "  docs/          - Documentation"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Add survey CSVs to survey_data/"
echo "  2. Run data pipeline:   cd data_pipeline && python run_pipeline.py --input ../survey_data"
echo "  3. Test app locally:    cd app && streamlit run app.py"
echo "  4. Deploy to AWS:       cd infra && ./scripts/apply.sh"
echo ""
echo "Documentation: docs/ARCHITECTURE.md, docs/DATA_WORKFLOW.md"
