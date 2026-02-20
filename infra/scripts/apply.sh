#!/bin/bash
# Apply Terraform changes
set -e
cd "$(dirname "$0")/.."

echo "=== Terraform Apply ==="

# Check for existing plan
if [ -f "tfplan" ]; then
    echo "Applying saved plan..."
    terraform apply tfplan
    rm -f tfplan
else
    echo "No saved plan. Running plan + apply..."
    terraform apply
fi

echo ""
echo "=== Outputs ==="
terraform output

echo ""
echo "Infrastructure created. App URL:"
terraform output -raw app_url
echo ""
