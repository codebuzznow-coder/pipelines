#!/bin/bash
# Run Terraform plan to preview changes
set -e
cd "$(dirname "$0")/.."

echo "=== Terraform Plan ==="

# Initialize if needed
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

# Plan
terraform plan -out=tfplan

echo ""
echo "Plan saved to tfplan. Run ./scripts/apply.sh to apply."
