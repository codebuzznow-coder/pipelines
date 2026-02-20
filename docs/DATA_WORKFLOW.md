# Data Pipeline Workflow

## Overview

The data pipeline processes survey data through 4 stages. Sampling runs first to reduce volume before resource-intensive validate/transform/enrich stages.

## Pipeline Stages

```mermaid
flowchart TB
    subgraph Input["Input"]
        CSV1["survey_2021.csv"]
        CSV2["survey_2022.csv"]
        CSV3["survey_2023.csv"]
        CSV4["survey_2024.csv"]
        CSV5["survey_2025.csv"]
    end
    
    subgraph Stage1["Stage 1: Sample"]
        S1["Extract primary role"]
        S2["Group by role"]
        S3["Sample 5% per role"]
        S4["Min 1 per role"]
    end
    
    subgraph Stage2["Stage 2: Validate"]
        V1["Remove duplicates"]
        V2["Check required columns"]
        V3["Quarantine bad rows"]
    end
    
    subgraph Stage3["Stage 3: Transform"]
        T1["Normalize year format"]
        T2["Clean compensation"]
        T3["Standardize countries"]
        T4["Coerce types"]
    end
    
    subgraph Stage4["Stage 4: Enrich"]
        E1["Add year_label"]
        E2["Add region_group"]
        E3["Add experience_bucket"]
        E4["Add comp_tier"]
    end
    
    subgraph Output["Output"]
        DB[("SQLite Cache<br/>survey_cache.db")]
    end
    
    Input --> Stage1
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
    Stage4 --> DB
```

## Stage Details

### Stage 1: Sample

```mermaid
flowchart TB
    subgraph Input["Input: 50,000 rows"]
        R1["Developer, full-stack: 15,000"]
        R2["Developer, back-end: 10,000"]
        R3["Data scientist: 5,000"]
        R4["DevOps: 3,000"]
        R5["Other roles: 17,000"]
    end
    
    subgraph Sampling["5% Sample (min 1 per role)"]
        S["Sample 5% from each role"]
    end
    
    subgraph Output["Output: ~2,500 rows"]
        O1["Developer, full-stack: 750"]
        O2["Developer, back-end: 500"]
        O3["Data scientist: 250"]
        O4["DevOps: 150"]
        O5["Other roles: 850"]
    end
    
    Input --> Sampling --> Output
```

**Algorithm:**
1. Extract primary role (first role in semicolon-separated DevType)
2. Group rows by primary role
3. For each role: sample `max(1, round(count * 0.05))` rows
4. Combine all sampled rows

**Properties:**
- Runs first to reduce data volume before validate/transform/enrich
- Maintains role proportions (same distribution as original)
- Guarantees at least 1 row per role (min_per_stratum=1)
- Reproducible (fixed random seed=42)
- ~95% reduction in data size

### Stage 2: Validate

```mermaid
flowchart LR
    Raw["Raw Data<br/>~50,000 rows"]
    
    subgraph Validation
        D["Remove exact duplicates"]
        I["Remove duplicate IDs"]
        N["Check key columns"]
    end
    
    Valid["Valid Data"]
    Q["Quarantine<br/>(>50% null)"]
    
    Raw --> D --> I --> N
    N -->|"Pass"| Valid
    N -->|"Fail"| Q
```

**Checks performed:**
- Remove exact duplicate rows
- Remove duplicate ResponseIds (keep first)
- Quarantine rows with >50% nulls in key columns (ResponseId, DevType, survey_year)

### Stage 3: Transform

```mermaid
flowchart LR
    subgraph Before
        Y1["survey_year: '2024.0'"]
        C1["Country: 'USA'"]
        W1["WorkExp: '5 years'"]
        S1["CompTotal: '-1'"]
    end
    
    subgraph After
        Y2["survey_year: '2024'"]
        C2["Country: 'United States'"]
        W2["WorkExp: 5"]
        S2["CompTotal: null"]
    end
    
    Before --> T["Transform"] --> After
```

**Transformations:**
- Normalize year: `"2024.0"` → `"2024"`
- Normalize country: `"USA"` → `"United States"`
- Convert WorkExp to numeric
- Clean compensation: remove negative values and outliers (>$10M)
- Strip whitespace from all string columns

### Stage 4: Enrich

```mermaid
flowchart LR
    Input["Transformed Data"]
    
    subgraph Enrichment
        YL["year_label<br/>'2024'"]
        RG["region_group<br/>'North America'"]
        EB["experience_bucket<br/>'3-5 years'"]
        CT["comp_tier<br/>'100-150k'"]
        SRC["_source<br/>'pipeline-20240219'"]
    end
    
    Output["Enriched Data"]
    
    Input --> Enrichment --> Output
```

**Fields added:**
| Field | Description | Example |
|-------|-------------|---------|
| `year_label` | Clean year string | `"2024"` |
| `region_group` | Continent from country | `"North America"` |
| `experience_bucket` | Work experience range | `"3-5 years"` |
| `comp_tier` | Compensation bracket | `"100-150k"` |
| `_source` | Pipeline run ID | `"pipeline-20240219_143022"` |
| `_enriched_at` | Timestamp | `"2024-02-19T14:30:22Z"` |

## Output: SQLite Cache

```mermaid
erDiagram
    survey_data {
        string ResponseId
        string Country
        string DevType
        string survey_year
        string year_label
        string region_group
        string experience_bucket
        string comp_tier
        int WorkExp
        float ConvertedCompYearly
        string _source
        string _enriched_at
    }
    
    cache_meta {
        string key PK
        string value
    }
```

**Cache metadata:**
- `built_at`: ISO timestamp of cache creation
- `source`: Description (e.g., "5.0% stratified sample")
- `years`: Years in the data (e.g., "2021, 2022, 2023, 2024, 2025")

## Running the Pipeline

### Command Line

```bash
# Basic usage
python run_pipeline.py --input /path/to/survey_data

# With options
python run_pipeline.py \
    --input /path/to/survey_data \
    --sample-pct 5 \
    --seed 42

# Skip cache (just run stages)
python run_pipeline.py --input ./data --skip-cache
```

### Output Structure

```
data/
├── cache/
│   └── survey_cache.db      # Final SQLite cache
├── stages/
│   ├── 01_sample/
│   │   ├── output.parquet
│   │   └── stats.json
│   ├── 02_validate/
│   │   ├── output.parquet
│   │   └── stats.json
│   ├── 03_transform/
│   │   ├── output.parquet
│   │   └── stats.json
│   ├── 04_enrich/
│   │   ├── output.parquet
│   │   └── stats.json
│   └── run_20240219_143022.json
```

## Metrics

Pipeline run produces statistics at each stage:

```json
{
  "run_id": "20240219_143022",
  "stages": {
    "load": {"rows": 50000, "files": 5},
    "validate": {"rows_valid": 49500, "rows_quarantined": 500},
    "transform": {"transforms_applied": ["normalized survey_year", "cleaned CompTotal"]},
    "enrich": {"fields_added": ["year_label", "region_group"]},
    "sample": {"rows_in": 49500, "rows_out": 2475, "reduction_pct": 95.0}
  },
  "cache": {"ok": true, "rows": 2475}
}
```
