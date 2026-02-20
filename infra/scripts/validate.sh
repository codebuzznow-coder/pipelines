#!/bin/bash
# Validate Terraform configuration
set -e
cd "$(dirname "$0")/.."

echo "=== Terraform Validate ==="

# Initialize if needed
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

# Format check
echo "Checking format..."
terraform fmt -check -recursive || {
    echo "Format issues found. Run: terraform fmt -recursive"
    exit 1
}

# Validate
echo "Validating configuration..."
terraform validate

echo ""
echo "Validation passed."
