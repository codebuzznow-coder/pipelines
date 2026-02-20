# Survey Q&A Pipeline

A clean, organized pipeline setup for deploying the Survey Q&A application on AWS. Includes infrastructure provisioning (Terraform), data pipeline (5% stratified sampling), and application deployment with persistent observability metrics.

## Project Structure

```
pipeline/
├── infra/                  # 1. Terraform infrastructure pipeline
│   ├── main.tf             # Provider, backend
│   ├── variables.tf        # Configurable inputs
│   ├── outputs.tf          # Endpoint URLs, IPs
│   ├── ec2.tf              # EC2 instance
│   ├── s3.tf               # S3 bucket for data
│   ├── security_groups.tf  # Firewall rules
│   └── scripts/            # Terraform wrapper scripts
│       ├── validate.sh     # terraform validate
│       ├── plan.sh         # terraform plan
│       ├── apply.sh        # terraform apply
│       └── destroy.sh      # terraform destroy
│
├── data_pipeline/          # 2. Data pipeline (validate → enrich → 5% sample)
│   ├── config.py           # Paths, settings
│   ├── stages/
│   │   ├── validate.py     # Schema and null checks
│   │   ├── transform.py    # Type coercion, cleaning
│   │   ├── enrich.py       # Add year labels, region
│   │   └── sample.py       # 5% stratified sample by role
│   ├── cache.py            # SQLite cache read/write
│   ├── run_pipeline.py     # CLI entry point
│   └── tests/
│       └── test_pipeline.py
│
├── app/                    # 3. Application code
│   ├── app.py              # Streamlit UI
│   ├── data_processor.py   # Query logic
│   ├── query_engine.py     # NL → query type
│   ├── visualizer.py       # Charts
│   ├── observability/
│   │   ├── metrics.py      # Persistent metrics (SQLite-backed)
│   │   └── config.py       # Metrics config
│   └── requirements.txt
│
├── deploy/                 # 4. Deployment pipeline
│   ├── Dockerfile          # Container image
│   ├── docker-compose.yml  # Local/dev compose
│   ├── scripts/
│   │   ├── deploy.sh       # Deploy to EC2
│   │   ├── startup.sh      # Container entrypoint
│   │   └── healthcheck.sh  # Health check
│   └── github_actions/
│       └── deploy.yml      # CI/CD workflow
│
├── docs/
│   ├── ARCHITECTURE.md     # Architecture diagram (Mermaid)
│   └── DATA_WORKFLOW.md    # Data pipeline workflow
│
└── scripts/
    ├── setup.sh            # One-time setup
    └── run_all.sh          # Run all pipelines
```

## Quick Start

### Prerequisites

- Python 3.9+
- Terraform 1.0+
- AWS CLI configured (`aws configure`)
- Docker (for deployment)

### 1. Setup

```bash
cd /Users/snarla/aiml/pipeline
./scripts/setup.sh
```

### 2. Infrastructure (Terraform)

```bash
cd infra
./scripts/validate.sh   # Check config
./scripts/plan.sh       # Preview changes
./scripts/apply.sh      # Create resources
# After demo:
./scripts/destroy.sh    # Tear down
```

### 3. Data Pipeline

```bash
cd data_pipeline
python run_pipeline.py --input /path/to/survey_data --sample-pct 5
```

### 4. Deploy Application

```bash
cd deploy
./scripts/deploy.sh
```

## Pipelines Overview

| Pipeline | Purpose | Key outputs |
|----------|---------|-------------|
| **Infra** | Create/destroy AWS resources (EC2, S3, SG) | Public IP, S3 bucket |
| **Data** | Validate → transform → enrich → 5% sample → SQLite | `survey_cache.db` |
| **Deploy** | Build image, push, deploy to EC2 | Running app URL |

## Costs (4-day demo)

- **EC2 t3.micro**: ~$1
- **S3**: < $0.10
- **Total**: ~$2–5 (without ALB)

After the demo, run `./infra/scripts/destroy.sh` to stop all charges.

## Documentation

- [Architecture Diagram](docs/ARCHITECTURE.md)
- [Data Pipeline Workflow](docs/DATA_WORKFLOW.md)
