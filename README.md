# Survey Q&A Pipeline

A clean, organized pipeline setup for deploying the Survey Q&A application on AWS. Includes infrastructure provisioning (Terraform), data pipeline (5% stratified sampling), and application deployment with CI/CD via GitHub Actions.

## Project Structure

```
pipeline/
├── infra/                  # Terraform infrastructure
│   ├── main.tf             # Provider, backend
│   ├── variables.tf        # Configurable inputs
│   ├── outputs.tf          # Endpoint URLs, IPs
│   ├── ec2.tf              # EC2 instance
│   ├── s3.tf               # S3 bucket for data
│   ├── security_groups.tf  # Firewall rules
│   └── scripts/            # Terraform wrapper scripts
│
├── data_pipeline/          # Data processing pipeline
│   ├── stages/             # sample → validate → transform → enrich
│   ├── run_pipeline.py     # CLI entry point
│   └── tests/
│
├── app/                    # Streamlit application
│   ├── app.py
│   ├── observability/      # Metrics and tracing
│   └── requirements.txt
│
├── deploy/                 # Deployment configs
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── github_actions/
│       └── deploy.yml      # CI/CD workflow
│
├── docs/                   # Documentation
└── scripts/                # Setup scripts
```

---

## Deployment Guide (Step-by-Step)

Follow these steps in order to deploy the application.

### Prerequisites

- [ ] **AWS Account** with admin access
- [ ] **AWS CLI** installed and configured (`aws configure`)
- [ ] **Terraform** 1.0+ installed
- [ ] **Docker** installed
- [ ] **Python** 3.9+
- [ ] **GitHub Account** with access to this repository

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/codebuzznow-coder/pipelines.git
cd pipelines
```

---

### Step 2: Configure AWS CLI

Ensure your AWS CLI is configured with credentials:

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., `us-east-1`)
- Output format (e.g., `json`)

Verify it works:

```bash
aws sts get-caller-identity
```

---

### Step 3: Create AWS Infrastructure (Terraform)

This creates an EC2 instance, S3 bucket, security groups, and IAM roles.

```bash
cd infra

# (Optional) Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars to customize region, instance type, etc.

# Initialize Terraform
terraform init

# Preview what will be created
./scripts/plan.sh

# Create the infrastructure
./scripts/apply.sh
```

**Save the outputs** - you'll need them for GitHub Actions:
- `ec2_public_ip` - The public IP of your EC2 instance
- `s3_bucket_name` - The S3 bucket for data

---

### Step 4: Create ECR Repository (for Docker images)

```bash
aws ecr create-repository --repository-name survey-qa --region us-east-1
```

---

### Step 5: Set Up GitHub Actions Secrets

Go to your GitHub repository settings:
**https://github.com/codebuzznow-coder/pipelines/settings/secrets/actions**

Click **"New repository secret"** and add each of these:

| Secret Name | Value | Where to find it |
|-------------|-------|------------------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key | AWS Console → IAM → Users → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key | Created with access key |
| `AWS_ACCOUNT_ID` | 12-digit account ID | AWS Console → Top-right dropdown |
| `EC2_HOST` | EC2 public IP | Output from Step 3 (`ec2_public_ip`) |
| `EC2_SSH_KEY` | Contents of your `.pem` file | The private key for your EC2 key pair |

**To get your AWS Account ID:**
```bash
aws sts get-caller-identity --query Account --output text
```

---

### Step 6: Enable GitHub Actions Workflow

Move the workflow file to the correct location:

```bash
mkdir -p .github/workflows
cp deploy/github_actions/deploy.yml .github/workflows/deploy.yml
git add .github
git commit -m "Enable GitHub Actions CI/CD workflow"
git push origin main
```

---

### Step 7: Trigger Deployment

The deployment will automatically run when you push to `main`. You can also trigger it manually:

1. Go to **https://github.com/codebuzznow-coder/pipelines/actions**
2. Click **"Build and Deploy"** workflow
3. Click **"Run workflow"** → **"Run workflow"**

---

### Step 8: Access Your Application

Once deployment completes, access your application at:

```
http://<EC2_PUBLIC_IP>:8501
```

Replace `<EC2_PUBLIC_IP>` with the IP from Step 3.

---

## Local Development (Optional)

### Run Data Pipeline Locally

```bash
cd data_pipeline
pip install -r ../app/requirements.txt
python run_pipeline.py --input /path/to/survey_data --sample-pct 5
```

### Run App Locally with Docker Compose

```bash
cd deploy
docker-compose up --build
```

Access at: http://localhost:8501

---

## Cleanup (Stop AWS Charges)

When you're done, destroy the infrastructure to avoid ongoing charges:

```bash
cd infra
./scripts/destroy.sh
```

Also delete the ECR repository:

```bash
aws ecr delete-repository --repository-name survey-qa --region us-east-1 --force
```

---

## Estimated Costs (4-day demo)

| Resource | Cost |
|----------|------|
| EC2 t3.micro | ~$1 |
| S3 | < $0.10 |
| ECR | < $0.50 |
| **Total** | **~$2-5** |

---

## Troubleshooting

### GitHub Actions fails with "permission denied"
- Verify `EC2_SSH_KEY` secret contains the full private key including `-----BEGIN` and `-----END` lines

### Cannot connect to EC2
- Check security group allows inbound traffic on ports 22 (SSH) and 8501 (app)
- Verify EC2 instance is running: `aws ec2 describe-instances`

### Terraform errors
- Run `terraform init` to download providers
- Check AWS credentials: `aws sts get-caller-identity`

---

## Documentation

- [Architecture Diagram](docs/ARCHITECTURE.md)
- [Data Pipeline Workflow](docs/DATA_WORKFLOW.md)
