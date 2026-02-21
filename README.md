# CodeBuzz – Survey Q&A Pipeline

A clean, organized pipeline setup for deploying the CodeBuzz Survey Q&A application on AWS. Includes infrastructure provisioning (Terraform), data pipeline (5% stratified sampling), and application deployment with CI/CD via GitHub Actions.

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
│   ├── validations.py      # Cache/data validations (used by UI & CLI)
│   ├── evals.py            # Query + data evals (used by UI & CLI)
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
├── .github/workflows/      # GitHub Actions
│   ├── deploy.yml          # Build image, deploy to EC2
│   └── run-pipeline.yml    # Run data pipeline on EC2 (S3 → container)
│
├── docs/                   # Documentation
└── scripts/                # Setup scripts
│   └── run_validations_evals.py   # Validations & evals CLI (report + optional --json)
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
| `EC2_HOST` | EC2 public IP | Output from Step 3 (`terraform output public_ip`). Required for Run Data Pipeline workflow. |
| `EC2_SSH_KEY` | Contents of your `.pem` file | The private key for your EC2 key pair. Required for Run Data Pipeline workflow. Security group must allow SSH (port 22) from `0.0.0.0/0`. |

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

## How to Run the Data Pipeline

### Option 1: GitHub Action (recommended — no upload from your laptop)

1. Put your CSV/ZIP files in S3 under a prefix (e.g. `survey_data/`): `s3://YOUR_BUCKET/survey_data/`.
2. In GitHub: **Actions** → **Run Data Pipeline** → enter S3 path (e.g. `s3://survey-qa-data-XXXXXXXX/survey_data/`) → **Run workflow**.
3. When the job succeeds, the pipeline has run on EC2 and the cache is built **on the server**.
4. Open the app at **http://YOUR_EC2_IP:8501** and click **🔄 Refresh data** in the sidebar. The data will load from the server cache — **you do not need to upload files from your laptop**.

### Option 2: From the app (upload in the browser)

Open http://YOUR_EC2_IP:8501 → **Data Pipeline** in the sidebar → upload CSV/ZIP files → Run Pipeline. Then switch to **Visualization** to use the data.

### Option 3: Locally

`cd data_pipeline && pip install -r ../app/requirements.txt && python run_pipeline.py --input ../survey_data` (put CSV or ZIP files in `survey_data/` first).

**Pipeline duration:** On a t3.medium with multiple survey CSVs, a full run can take **15–45 minutes**. Use a smaller **sample %** (e.g. 1–2%) in the workflow for faster runs (~5–15 min).

### Optional: OpenAI for query conversion

In the app, open **Ask a Question** → **Query settings (optional OpenAI)**. You can:
- Check **Use OpenAI to interpret questions** and provide an API key (see below). The app converts your question into filters and parameters via the API (no SQL is generated).
- Click **Test API** to verify the key works before running queries.
- Leave OpenAI disabled to use **keyword parsing** only (no API key required).

**Where to get the API key (do not commit keys):**
- **Local:** Copy `.env` from `data_to_decisions` into the **pipeline** project root: `cp /path/to/data_to_decisions/.env /path/to/pipeline/.env`. The file must contain `OPENAI_API_KEY=sk-...`. `.env` is in `.gitignore` and will not be committed.
- **Streamlit Cloud / production:** Set `OPENAI_API_KEY` in Streamlit secrets.
- **UI:** You can also paste the key in the Query settings field (not recommended for shared deployments).

## Local Development (Optional)

### Run Data Pipeline Locally

```bash
cd data_pipeline
pip install -r ../app/requirements.txt
python run_pipeline.py --input ../survey_data --sample-pct 5
```
Put your CSV or ZIP files in the `survey_data/` folder at the project root (or use any path).

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

### Run Data Pipeline workflow: "S3 path" error
- Use the **S3 URI**, not the AWS Console URL.
- **Wrong:** `https://us-east-1.console.aws.amazon.com/s3/buckets/survey-qa-data-301625833185?region=us-east-1&tab=objects`
- **Correct:** `s3://survey-qa-data-301625833185/survey_data/` (use your bucket name and the folder that contains your CSV/ZIP files)

### Run Data Pipeline: "No CSV or ZIP at s3://... EC2 instance may need IAM access"
- **Quick fix (grant EC2 access to the bucket):** In `infra/terraform.tfvars` add (use your bucket name): `ec2_additional_s3_bucket_arns = ["arn:aws:s3:::survey-qa-data-301625833185"]`. Run `cd infra && terraform apply`. Then confirm the EC2 instance has the IAM role: AWS Console → EC2 → instance → **Security** → **IAM role** (e.g. `survey-qa-demo-role`). If empty, attach that role and re-run the workflow.
- **Files location:** The workflow syncs the **prefix** you give (e.g. `survey_data/`). Upload CSV or ZIP files **under that prefix** (e.g. `s3://your-bucket/survey_data/2024.csv` or `survey_data/files.zip`). If the prefix is empty or has no `.csv`/`.zip`, you’ll see this error.
- **EC2 IAM:** The EC2 instance needs the IAM role that has S3 access. If you used this repo’s Terraform, the instance profile is attached. Verify: AWS Console → EC2 → your instance → **Security** → **IAM role** (e.g. `survey-qa-demo-role`). If there is no role, re-run `terraform apply` or attach the role `survey-qa-<env>-role` to the instance.
- **Bucket not created by Terraform:** If the bucket (e.g. `survey-qa-data-301625833185`) was created outside this Terraform, add its ARN so the EC2 role can access it. In `infra/terraform.tfvars`:  
  `ec2_additional_s3_bucket_arns = ["arn:aws:s3:::survey-qa-data-301625833185"]`  
  Then run `terraform apply`. You can also use this for a bucket in the same account that Terraform didn’t create.

### Deploy / Run Data Pipeline: "Connection timed out" or "Connection timed out during banner exchange"
- Port 22 is not reachable from GitHub. The workflow retries 3 times; if it still fails, allow SSH from anywhere: in `infra/variables.tf` set `allowed_cidr = "0.0.0.0/0"` for port 22, then `terraform apply`. Ensure EC2 is running with a public IP and **EC2_HOST** is that IP.

### Run Data Pipeline workflow: "ssh: connect to host ... port 22: Connection timed out"
- GitHub Actions runs from **GitHub’s IPs**, not your own. If your EC2 security group allows only **your IP** (e.g. 173.66.55.228), SSH from GitHub will be blocked.
- **Options:**
  1. **Allow SSH from anywhere (for workflow only):** In Terraform `infra/variables.tf`, set `allowed_cidr = "0.0.0.0/0"`, run `terraform apply`. Restrict again after the run if you want.
  2. **Run the pipeline without SSH:** Use the app’s **Data Pipeline** tab at `http://YOUR_EC2_IP:8501`, upload CSV/ZIP there and run the pipeline in the browser.
  3. **Run from your machine:** From a machine that can reach EC2 (e.g. your laptop), run:  
     `aws s3 sync s3://YOUR_BUCKET/survey_data/ ./survey_data/` then SSH to EC2 and run the pipeline there, or use the web UI.
- **Fix:** In `infra/variables.tf` set `allowed_cidr = "0.0.0.0/0"`, run `terraform apply`. Ensure `EC2_HOST` and `EC2_SSH_KEY` are set in GitHub secrets.

### Run Data Pipeline: "Connection reset by peer" / "kex_exchange_identification: read: Connection reset by peer"
- The workflow now uses **SSH -T** (no pseudo-terminal) and **retries up to 3 times** with a 15s delay. If it still fails:
  1. **Security group:** Inbound port 22 must allow **0.0.0.0/0** (GitHub’s IPs change).
  2. **EC2 state:** Instance must be **running**; if it was just started, wait 1–2 minutes for SSH to be ready.
  3. **Re-run the job:** Transient network/rate limits often clear on a second run.
  4. **Run locally:** Use the app’s **Data Pipeline** tab at `http://YOUR_EC2_IP:8501` and upload CSV/ZIP, or run the pipeline from your machine via SSH.

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
