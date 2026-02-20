# Architecture

## System Overview

```mermaid
flowchart TB
    subgraph Developer["Developer Machine"]
        Code[("GitHub Repo")]
        TF["Terraform"]
    end
    
    subgraph AWS["AWS Cloud"]
        subgraph Infra["Infrastructure (Terraform)"]
            EC2["EC2 Instance<br/>t3.micro"]
            S3["S3 Bucket<br/>Survey Data"]
            SG["Security Group<br/>Port 8501"]
            EIP["Elastic IP"]
        end
        
        subgraph Container["Docker Container"]
            App["Streamlit App<br/>Port 8501"]
            Cache[("SQLite Cache<br/>survey_cache.db")]
            Metrics[("Metrics DB<br/>metrics.db")]
        end
    end
    
    subgraph Users["End Users"]
        Browser["Web Browser"]
    end
    
    Code -->|"git push"| GHA["GitHub Actions"]
    GHA -->|"Build & Push"| ECR["Amazon ECR"]
    ECR -->|"docker pull"| EC2
    
    TF -->|"terraform apply"| Infra
    S3 -->|"aws s3 sync"| Container
    
    EC2 --- EIP
    EIP --- SG
    SG -->|"8501"| App
    
    App --> Cache
    App --> Metrics
    
    Browser -->|"HTTP"| EIP
```

## Component Diagram

```mermaid
flowchart LR
    subgraph Pipeline["Pipelines"]
        direction TB
        P1["1. Infra Pipeline<br/>(Terraform)"]
        P2["2. Data Pipeline<br/>(Python)"]
        P3["3. Deploy Pipeline<br/>(Docker/GitHub Actions)"]
    end
    
    subgraph Infra["Infrastructure"]
        EC2["EC2"]
        S3["S3"]
        SG["Security Group"]
    end
    
    subgraph Data["Data Layer"]
        Raw["Raw CSV/ZIP"]
        Stages["Pipeline Stages"]
        Cache["SQLite Cache"]
    end
    
    subgraph App["Application"]
        UI["Streamlit UI"]
        QE["Query Engine"]
        Viz["Visualizer"]
        Obs["Observability"]
    end
    
    P1 --> Infra
    P2 --> Data
    P3 --> App
    
    Raw --> Stages
    Stages --> Cache
    Cache --> QE
    QE --> Viz
    Viz --> UI
    UI --> Obs
```

## Pipeline Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant TF as Terraform
    participant AWS as AWS
    participant GH as GitHub
    participant EC2 as EC2
    
    Note over Dev,EC2: 1. Infrastructure Pipeline
    Dev->>TF: terraform apply
    TF->>AWS: Create EC2, S3, SG, EIP
    AWS-->>Dev: Outputs (IP, bucket)
    
    Note over Dev,EC2: 2. Data Pipeline
    Dev->>Dev: python run_pipeline.py
    Dev->>Dev: sample → validate → transform → enrich
    Dev->>AWS: Upload cache to S3
    
    Note over Dev,EC2: 3. Deploy Pipeline
    Dev->>GH: git push
    GH->>GH: Run tests
    GH->>AWS: Build & push to ECR
    GH->>EC2: Deploy container
    EC2->>AWS: Sync data from S3
    EC2-->>Dev: App URL ready
```

## Data Flow

```mermaid
flowchart LR
    subgraph Input["Input"]
        CSV["Survey CSVs<br/>(2021-2025)"]
    end
    
    subgraph Pipeline["Data Pipeline"]
        V["Validate<br/>- Dedupe<br/>- Null check"]
        T["Transform<br/>- Types<br/>- Normalize"]
        E["Enrich<br/>- Year label<br/>- Region"]
        S["Sample<br/>- 5% stratified<br/>- By role"]
    end
    
    subgraph Output["Output"]
        DB[("SQLite Cache<br/>~2.5K rows")]
    end
    
    CSV --> V --> T --> E --> S --> DB
```

## Deployment Architecture

```mermaid
flowchart TB
    subgraph Local["Local Development"]
        Code["Source Code"]
        Docker["Docker Build"]
    end
    
    subgraph CI["GitHub Actions"]
        Test["Run Tests"]
        Build["Build Image"]
        Push["Push to ECR"]
    end
    
    subgraph AWS["AWS"]
        ECR["ECR Registry"]
        EC2["EC2 Instance"]
        Vol["Docker Volume<br/>(Persistent)"]
    end
    
    Code --> Test
    Test --> Build
    Build --> Push
    Push --> ECR
    ECR --> EC2
    EC2 --- Vol
    
    Vol -->|"Survives restart"| Cache[("Cache + Metrics")]
```

## Observability

```mermaid
flowchart TB
    subgraph App["Application"]
        Query["User Query"]
        Logic["Query Processing"]
    end
    
    subgraph Metrics["Metrics Collector"]
        Counter["Counters<br/>- queries_total<br/>- errors_total"]
        Gauge["Gauges<br/>- app_last_start"]
        Timing["Timings<br/>- query_duration_ms"]
        Events["Events<br/>- query text<br/>- errors"]
    end
    
    subgraph Storage["Persistent Storage"]
        DB[("metrics.db<br/>SQLite")]
    end
    
    Query --> Logic
    Logic --> Counter
    Logic --> Timing
    Logic --> Events
    
    Counter --> DB
    Gauge --> DB
    Timing --> DB
    Events --> DB
    
    DB -->|"Survives"| Restart["App/DB Restart"]
```

## Security

```mermaid
flowchart LR
    subgraph Internet["Internet"]
        User["User"]
    end
    
    subgraph AWS["AWS"]
        SG["Security Group"]
        EC2["EC2"]
    end
    
    User -->|"8501 (App)"| SG
    User -->|"22 (SSH)"| SG
    SG --> EC2
    
    EC2 -->|"443 (HTTPS)"| S3["S3"]
    EC2 -->|"443"| ECR["ECR"]
```

## Cost Summary

| Component | Spec | Monthly Cost |
|-----------|------|--------------|
| EC2 | t3.micro | ~$8–10 |
| EBS | 20GB gp3 | ~$2 |
| S3 | < 5GB | < $0.15 |
| Data Transfer | Light | ~$1 |
| **Total** | | **~$12–15/month** |

For 4-day demo: **~$2–3**
