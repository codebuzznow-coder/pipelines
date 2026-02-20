#!/bin/bash
# Destroy all Terraform-managed resources
set -e
cd "$(dirname "$0")/.."

echo "=== Terraform Destroy ==="
echo "WARNING: This will delete all resources (EC2, S3, EIP, etc.)"
echo ""

read -p "Are you sure? Type 'yes' to confirm: " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

terraform destroy

echo ""
echo "All resources destroyed. No more AWS charges for this infrastructure."
