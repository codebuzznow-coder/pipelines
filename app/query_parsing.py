"""
Query parsing: keyword-based fallback and optional OpenAI conversion.

When OpenAI is configured, the user's question is sent to the API and converted
into structured parameters (country filter, top_n). Otherwise keyword rules are used.
"""
import json
import os
import re
from typing import Any, Dict, Optional, Tuple

# Optional OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None


def test_openai_api(api_key: str) -> Tuple[bool, str]:
    """
    Verify the OpenAI API key with a minimal request.
    Returns (success, message).
    """
    if not OPENAI_AVAILABLE:
        return False, "OpenAI package not installed (pip install openai)."
    key = (api_key or "").strip()
    if not key:
        return False, "API key is empty."
    try:
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        out = (r.choices[0].message.content or "").strip()
        return True, f"API OK. Response: {out[:50]}"
    except Exception as e:
        return False, str(e)


SURVEY_CONTEXT = """
The survey data has columns: Country, DevType (developer role, may be semicolon-separated), survey_year, and others.
We support: filtering by country, and returning top N developer roles (aggregated from DevType).
Return valid JSON only, no markdown or explanation.
"""


def parse_query_with_openai(
    api_key: str,
    query: str,
    default_top_n: int = 10,
) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """
    Use OpenAI to convert natural language question to structured params.

    Returns:
        (country_filter, top_n, interpretation_text, error_message)
        On success error_message is None. On failure, country_filter/top_n/interpretation may be None.
    """
    if not OPENAI_AVAILABLE:
        return None, None, None, "OpenAI package not installed (pip install openai)."
    if not api_key or not api_key.strip():
        return None, None, None, "OpenAI API key is empty."

    prompt = f"""{SURVEY_CONTEXT}

User question: "{query}"

Extract:
1. country_filter: exact country name if the user asks for a specific country (e.g. USA/United States, India, Germany), or null for global.
2. top_n: number of top results (e.g. 5, 10, 15). Default {default_top_n} if not specified.
3. interpretation: one short sentence describing how you interpreted the question.

Return only a JSON object with keys: country_filter (string or null), top_n (integer), interpretation (string).
Example: {{"country_filter": "United States", "top_n": 5, "interpretation": "Top 5 developer roles in the United States."}}
"""

    try:
        client = OpenAI(api_key=api_key.strip())
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract structured parameters from survey questions. Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        # Remove markdown code block if present
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        country = data.get("country_filter")
        if country is not None and not isinstance(country, str):
            country = None
        top_n = data.get("top_n")
        if top_n is not None and isinstance(top_n, (int, float)):
            top_n = max(1, min(100, int(top_n)))
        else:
            top_n = default_top_n
        interpretation = data.get("interpretation") or "Query interpreted with OpenAI."
        return (country if country else None), top_n, interpretation, None
    except json.JSONDecodeError as e:
        return None, default_top_n, None, f"OpenAI returned invalid JSON: {e}"
    except Exception as e:
        return None, default_top_n, None, str(e)


def parse_query_keyword(query: str, default_top_n: int) -> Tuple[Optional[str], int, str]:
    """
    Simple keyword-based parsing (no API).

    Returns:
        (country_filter, top_n, interpretation_text)
    """
    query_lower = query.lower()
    country_filter = None
    if "usa" in query_lower or "united states" in query_lower:
        country_filter = "United States"
    elif "india" in query_lower:
        country_filter = "India"
    elif "germany" in query_lower:
        country_filter = "Germany"
    elif "uk" in query_lower or "united kingdom" in query_lower:
        country_filter = "United Kingdom"

    # Try to extract a number for top_n
    top_n = default_top_n
    match = re.search(r"\b(top\s*)?(\d+)\b", query_lower, re.IGNORECASE)
    if match:
        n = int(match.group(2))
        if 1 <= n <= 100:
            top_n = n

    parts = []
    if country_filter:
        parts.append(f"Country filter: {country_filter} (from keywords)")
    else:
        parts.append("Country filter: None (global)")
    parts.append(f"Top N: {top_n} (from keywords or default)")
    interpretation = " | ".join(parts)
    return country_filter, top_n, interpretation
