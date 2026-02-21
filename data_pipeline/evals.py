"""
Evaluations: query parsing correctness and data quality metrics.

Each eval returns a dict: {"name", "score", "message", "details"}.
Run via scripts/run_validations_evals.py for a clear report.
"""
from typing import Any, Dict, List, Optional

try:
    from config import ROLE_COLUMN
    from cache import read_cache
except ImportError:
    from .config import ROLE_COLUMN
    from .cache import read_cache

# Query parsing evals: (question, expected_country or None, expected_top_n or None)
QUERY_EVAL_CASES = [
    ("Top 5 roles in USA", "United States", 5),
    ("Top 10 roles in United States", "United States", 10),
    ("Show developer roles in India", "India", 10),
    ("Top 15 in Germany", "Germany", 15),
    ("What are the top roles?", None, 10),
    ("Top 20 roles UK", "United Kingdom", 20),
]


def _get_query_parser():
    """Import parse_query_keyword from app if available."""
    try:
        from query_parsing import parse_query_keyword
        return parse_query_keyword
    except ImportError:
        pass
    import sys
    from pathlib import Path
    app_dir = Path(__file__).resolve().parent.parent / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    try:
        from query_parsing import parse_query_keyword
        return parse_query_keyword
    except ImportError:
        return None


def eval_keyword_parsing() -> Dict[str, Any]:
    """Evaluate keyword-based query parsing against expected (country, top_n)."""
    parse_query_keyword = _get_query_parser()
    if parse_query_keyword is None:
        return {
            "name": "eval_keyword_parsing",
            "score": 0.0,
            "message": "Could not import query_parsing",
            "details": {},
        }
    correct = 0
    total = len(QUERY_EVAL_CASES)
    details = []
    for question, exp_country, exp_top_n in QUERY_EVAL_CASES:
        country, top_n, _ = parse_query_keyword(question, default_top_n=10)
        ok_country = (country == exp_country)
        ok_top = (exp_top_n is None) or (top_n == exp_top_n)
        ok = ok_country and ok_top
        if ok:
            correct += 1
        details.append({
            "question": question[:40],
            "expected": (exp_country, exp_top_n),
            "got": (country, top_n),
            "pass": ok,
        })
    score = correct / total if total else 0.0
    return {
        "name": "eval_keyword_parsing",
        "score": score,
        "message": f"{correct}/{total} query cases correct ({score*100:.0f}%)",
        "details": {"cases": details, "correct": correct, "total": total},
    }


def eval_data_coverage() -> Dict[str, Any]:
    """Evaluate data quality: fraction of rows with key fields populated."""
    df, _ = read_cache()
    if df is None or df.empty:
        return {
            "name": "eval_data_coverage",
            "score": 0.0,
            "message": "No cache data",
            "details": {},
        }
    total = len(df)
    devtype_ok = df[ROLE_COLUMN].astype(str).str.strip().replace("", None).notna().sum() if ROLE_COLUMN in df.columns else 0
    country_ok = df["Country"].astype(str).str.strip().replace("", None).notna().sum() if "Country" in df.columns else 0
    score_dev = (devtype_ok / total) if total else 0
    score_country = (country_ok / total) if total else 0
    score = (score_dev + score_country) / 2
    return {
        "name": "eval_data_coverage",
        "score": score,
        "message": f"DevType {score_dev*100:.1f}%, Country {score_country*100:.1f}% coverage",
        "details": {"rows": total, "devtype_filled": devtype_ok, "country_filled": country_ok},
    }


def eval_role_distribution_spread() -> Dict[str, Any]:
    """Evaluate that we have multiple distinct roles (not all same)."""
    df, _ = read_cache()
    if df is None or df.empty or ROLE_COLUMN not in df.columns:
        return {"name": "eval_role_spread", "score": 0.0, "message": "No data", "details": {}}
    roles = []
    for v in df[ROLE_COLUMN].dropna():
        s = str(v).strip()
        if ";" in s:
            roles.extend([r.strip() for r in s.split(";") if r.strip()])
        elif s and s != "nan":
            roles.append(s)
    unique = len(set(roles))
    # Good if we have at least 5 distinct roles
    score = min(1.0, unique / 5.0) if unique else 0.0
    return {
        "name": "eval_role_spread",
        "score": score,
        "message": f"{unique} distinct roles (target >= 5)",
        "details": {"unique_roles": unique, "total_mentions": len(roles)},
    }


def run_all_evals(openai_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Run all evaluations. Optionally run OpenAI parsing eval if api_key provided."""
    results = [
        eval_keyword_parsing(),
        eval_data_coverage(),
        eval_role_distribution_spread(),
    ]
    if openai_api_key and (openai_api_key or "").strip():
        results.append(eval_openai_parsing((openai_api_key or "").strip()))
    return results


def eval_openai_parsing(api_key: str) -> Dict[str, Any]:
    """Evaluate OpenAI query parsing: run a few questions and check valid structure."""
    try:
        from query_parsing import parse_query_with_openai
    except ImportError:
        return {"name": "eval_openai_parsing", "score": 0.0, "message": "query_parsing not available", "details": {}}
    cases = [("Top 5 roles in USA", 5), ("Roles in India", 10)]
    correct = 0
    details = []
    for question, default_n in cases:
        country, top_n, interp, err = parse_query_with_openai(api_key, question, default_top_n=default_n)
        if err:
            details.append({"question": question[:30], "error": err, "pass": False})
            continue
        # Expect USA -> United States, India -> India
        ok = top_n >= 1 and (country is None or isinstance(country, str))
        if ok:
            correct += 1
        details.append({"question": question[:30], "country": country, "top_n": top_n, "pass": ok})
    score = correct / len(cases) if cases else 0.0
    return {
        "name": "eval_openai_parsing",
        "score": score,
        "message": f"{correct}/{len(cases)} OpenAI parsing cases valid",
        "details": {"cases": details},
    }
