#!/bin/bash
# Deploy to EC2 instance
# Usage: ./deploy.sh <ec2-ip> [ssh-key-path]

set -e

EC2_IP="${1:?Usage: ./deploy.sh <ec2-ip> [ssh-key-path]}"
SSH_KEY="${2:-~/.ssh/id_rsa}"
DEPLOY_DIR="/opt/survey-qa"

echo "=== Deploying to $EC2_IP ==="

# Build image locally
echo "[1/4] Building Docker image..."
cd "$(dirname "$0")/../.."
docker build -t survey-qa:latest -f deploy/Dockerfile .

# Save and transfer image
echo "[2/4] Transferring image..."
docker save survey-qa:latest | gzip > /tmp/survey-qa.tar.gz
scp -i "$SSH_KEY" /tmp/survey-qa.tar.gz "ec2-user@$EC2_IP:/tmp/"

# Deploy on remote
echo "[3/4] Deploying on EC2..."
ssh -i "$SSH_KEY" "ec2-user@$EC2_IP" << 'REMOTE_SCRIPT'
set -e

# Load image
echo "Loading Docker image..."
gunzip -c /tmp/survey-qa.tar.gz | docker load
rm /tmp/survey-qa.tar.gz

# Stop existing container
docker stop survey-qa 2>/dev/null || true
docker rm survey-qa 2>/dev/null || true

# Create data volume if not exists
docker volume create survey-data 2>/dev/null || true

# Run new container
echo "Starting container..."
docker run -d \
    --name survey-qa \
    --restart unless-stopped \
    -p 8501:8501 \
    -v survey-data:/app/data \
    survey-qa:latest

# Wait for health
echo "Waiting for health check..."
for i in {1..30}; do
    if curl -sf http://localhost:8501/_stcore/health > /dev/null; then
        echo "Application is healthy!"
        break
    fi
    sleep 2
done

docker ps | grep survey-qa
REMOTE_SCRIPT

echo "[4/4] Deployment complete!"
echo "Application URL: http://$EC2_IP:8501"
