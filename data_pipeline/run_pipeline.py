#!/usr/bin/env python3
"""
Data pipeline CLI: load → sample → validate → transform → enrich → cache.

Sample runs first to reduce data volume before resource-intensive stages.

Usage:
    python run_pipeline.py --input /path/to/survey_data
    python run_pipeline.py --input data.csv --sample-pct 5 --seed 42
    python run_pipeline.py --input survey.zip   # extracts and uses CSVs inside
"""
import argparse
import json
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

import pandas as pd

try:
    from config import ensure_dirs, STAGE_DIR, SAMPLE_PCT, RANDOM_SEED
    from stages import validate_data, transform_data, enrich_data, stratified_sample
    from cache import build_cache, get_cache_stats
except ImportError:
    from .config import ensure_dirs, STAGE_DIR, SAMPLE_PCT, RANDOM_SEED
    from .stages import validate_data, transform_data, enrich_data, stratified_sample
    from .cache import build_cache, get_cache_stats


def discover_csv_files(
    input_path: str,
    extract_dir: Optional[Path] = None,
) -> List[Path]:
    """
    Find CSV files in input path (file or directory).
    Supports .csv files and .zip archives (extracts and uses CSVs inside).
    """
    p = Path(input_path)
    csv_paths: List[Path] = []

    if p.is_file():
        if p.suffix.lower() == ".csv":
            return [p]
        if p.suffix.lower() == ".zip":
            extract_dir = extract_dir or Path(tempfile.mkdtemp())
            extract_to = extract_dir / p.stem
            extract_to.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(p, "r") as z:
                z.extractall(extract_to)
            return sorted(extract_to.rglob("*.csv"))
        return []

    if not p.is_dir():
        return []

    # Directory: collect CSVs and extract any zips
    csv_paths = list(p.rglob("*.csv"))

    if extract_dir is None:
        extract_dir = Path(tempfile.mkdtemp())

    for zip_path in p.rglob("*.zip"):
        extract_to = extract_dir / zip_path.stem
        extract_to.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_to)
        csv_paths.extend(extract_to.rglob("*.csv"))

    return sorted(set(csv_paths))


def load_data(
    csv_files: List[Path],
    log: Optional[Callable[[str], None]] = None,
    skip_schema_files: bool = False,
) -> pd.DataFrame:
    """Load and concatenate CSV files, adding survey_year from filename.
    Set skip_schema_files=True to skip *schema*.csv on low-memory instances (avoids column explosion).
    """
    _log = log if log else (lambda msg: print(msg, flush=True))
    frames = []
    for f in csv_files:
        if skip_schema_files and "schema" in f.name.lower():
            _log(f"  Skipping schema file: {f.name}")
            continue
        try:
            df = pd.read_csv(f, low_memory=False)
            # Extract year from filename (e.g. survey_2024.csv -> 2024)
            import re
            match = re.search(r"(20\d{2})", f.name)
            if match and "survey_year" not in df.columns:
                df["survey_year"] = match.group(1)
            frames.append(df)
            _log(f"  Loaded {f.name}: {len(df)} rows")
        except Exception as e:
            _log(f"  Error loading {f.name}: {e}")
    
    if not frames:
        return pd.DataFrame()
    _log("  Concatenating dataframes...")
    out = pd.concat(frames, axis=0, ignore_index=True)
    _log("  Done concatenating.")
    return out


def save_stage_output(df: pd.DataFrame, stage_name: str, stats: Dict[str, Any]):
    """Save stage output and stats."""
    stage_dir = STAGE_DIR / stage_name
    stage_dir.mkdir(parents=True, exist_ok=True)
    
    # Save parquet
    df.to_parquet(stage_dir / "output.parquet", index=False)
    
    # Save stats
    with open(stage_dir / "stats.json", "w") as f:
        json.dump(stats, f, indent=2, default=str)


def run_pipeline(
    input_path: str,
    sample_pct: float = SAMPLE_PCT,
    seed: int = RANDOM_SEED,
    skip_cache: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Run the full data pipeline.
    
    If log_callback is provided, it will be called with each log line (for UI progress).
    
    Returns:
        Pipeline run summary
    """
    def log(msg: str = "") -> None:
        print(msg, flush=True)
        if log_callback:
            log_callback(msg)

    ensure_dirs()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    result = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "input_path": input_path,
        "sample_pct": sample_pct * 100,
        "stages": {},
        "ok": False
    }
    
    log(f"\n{'='*60}")
    log(f"Data Pipeline Run: {run_id}")
    log(f"{'='*60}")
    
    # 1. Load data (supports .csv and .zip; zips are extracted to a temp dir)
    log("\n[1/6] Loading data...")
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_files = discover_csv_files(input_path, extract_dir=Path(tmpdir))
        if not csv_files:
            result["error"] = f"No CSV files found in {input_path} (looked for .csv and .zip)"
            log(f"  ERROR: {result['error']}")
            return result

        log(f"  Found {len(csv_files)} CSV file(s)")
        df = load_data(csv_files, log=log)
    if df.empty:
        result["error"] = "No data loaded"
        return result
    
    result["stages"]["load"] = {"rows": len(df), "files": len(csv_files)}
    log(f"  Total: {len(df)} rows, {len(df.columns)} columns")
    
    # 2. Sample first (reduce volume before heavy stages)
    log(f"\n[2/6] Stratified sampling ({sample_pct*100}% by role)...")
    log("  Sampling by role (may take a few minutes on large data)...")
    df_sampled, sample_stats = stratified_sample(df, sample_pct=sample_pct, seed=seed)
    save_stage_output(df_sampled, "01_sample", sample_stats)
    result["stages"]["sample"] = {
        "rows_in": sample_stats["rows_in"],
        "rows_out": sample_stats["rows_out"],
        "reduction_pct": sample_stats["reduction_pct"]
    }
    log(f"  {sample_stats['rows_in']} → {sample_stats['rows_out']} rows ({sample_stats['reduction_pct']}% reduction)")
    
    # 3. Validate
    log("\n[3/6] Validating data...")
    df_valid, df_quarantine, validate_stats = validate_data(df_sampled)
    save_stage_output(df_valid, "02_validate", validate_stats)
    result["stages"]["validate"] = validate_stats
    log(f"  Valid: {validate_stats['rows_valid']}, Quarantined: {validate_stats['rows_quarantined']}")
    
    # 4. Transform
    log("\n[4/6] Transforming data...")
    df_transformed, transform_stats = transform_data(df_valid)
    save_stage_output(df_transformed, "03_transform", transform_stats)
    result["stages"]["transform"] = transform_stats
    log(f"  Transforms: {len(transform_stats['transforms_applied'])}")
    
    # 5. Enrich
    log("\n[5/6] Enriching data...")
    df_enriched, enrich_stats = enrich_data(df_transformed, source_label=f"pipeline-{run_id}")
    save_stage_output(df_enriched, "04_enrich", enrich_stats)
    result["stages"]["enrich"] = enrich_stats
    log(f"  Fields added: {enrich_stats['fields_added']}")
    
    # 6. Build cache
    if not skip_cache:
        log("\n[6/6] Building SQLite cache...")
        cache_result = build_cache(df_enriched, source=f"{sample_pct*100}% stratified sample")
        result["cache"] = cache_result
        if cache_result.get("ok"):
            log(f"  Cache: {cache_result['rows']} rows, {cache_result['path']}")
        else:
            log(f"  Cache error: {cache_result.get('message')}")
    
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["ok"] = True
    
    log(f"\n{'='*60}")
    log(f"Pipeline completed: {result['run_id']}")
    log(f"{'='*60}\n")
    
    # Save run summary
    summary_path = STAGE_DIR / f"run_{run_id}.json"
    with open(summary_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    log(f"Run summary: {summary_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Data pipeline: load → sample → validate → transform → enrich → cache"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to CSV file or directory containing CSVs"
    )
    parser.add_argument(
        "--sample-pct",
        type=float,
        default=SAMPLE_PCT * 100,
        help=f"Sample percentage (default: {SAMPLE_PCT * 100})"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help=f"Random seed (default: {RANDOM_SEED})"
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Skip building SQLite cache"
    )
    args = parser.parse_args()
    
    sample_pct = args.sample_pct / 100.0
    if sample_pct <= 0 or sample_pct > 1:
        print("Error: --sample-pct must be in (0, 100]")
        sys.exit(1)
    
    result = run_pipeline(
        input_path=args.input,
        sample_pct=sample_pct,
        seed=args.seed,
        skip_cache=args.skip_cache
    )
    
    if not result.get("ok"):
        sys.exit(1)
    
    # Print cache stats
    stats = get_cache_stats()
    if stats.get("exists"):
        print(f"\nCache stats:")
        print(f"  Rows: {stats['rows']}")
        print(f"  Size: {stats['size_mb']} MB")
        print(f"  Years: {stats['years']}")


if __name__ == "__main__":
    main()
