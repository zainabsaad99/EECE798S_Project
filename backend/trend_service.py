import json
import os
from typing import List, Dict, Any, Optional

import requests
from openai import OpenAI

TREND_SYSTEM_PROMPT = """
You are TrendMatch, an analytical model that extracts structured, comparable information from web trend articles.

Your goal is to produce a compact, normalized JSON representation of each trend suitable for cosine-similarity matching with company profiles (which include company mission, audience, and products with descriptions).

Analyze the article text to extract:
- The main industry or domain this trend belongs to
- The core concept or practice being discussed
- The target audience or users/businesses affected
- The types of relevant products or services
- The practical business value or benefit
- A list of semantic keywords or multi-word phrases

Rules:
1. Always output the same JSON keys, even if data is not found.
2. If a field is not clearly mentioned, set its value to "unknown" or an empty array ([]).
3. Do not include explanations, commentary, or extra text.
4. Keep phrasing factual, short, and domain-specific.
5. Output only one valid JSON object.
""".strip()


def _get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def firecrawl_search(keyword: str, firecrawl_api_key: Optional[str], limit: int = 5) -> Dict[str, Any]:
    api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError("FIRECRAWL_API_KEY is not configured.")
    query = f"latest trends about {keyword}"
    response = requests.post(
        "https://api.firecrawl.dev/v2/search",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "limit": limit,
            "scrapeOptions": {"formats": ["markdown"]},
        },
        timeout=60,
    )
    return {
        "keyword": keyword,
        "query": query,
        "data": response.json() if response.status_code == 200 else None,
        "error": None if response.status_code == 200 else response.text,
    }


def extract_full_results(raw_firecrawl_json: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not raw_firecrawl_json:
        return []
    try:
        web_entries = raw_firecrawl_json.get("data", {}).get("web", [])  # type: ignore[attr-defined]
    except Exception:
        return []

    cleaned = []
    for item in web_entries:
        meta = item.get("metadata", {}) or {}
        og_image = (
            meta.get("og:image")
            or meta.get("ogImage")
            or meta.get("twitter:image")
            or meta.get("image")
        )
        cleaned.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "description": item.get("description"),
            "markdown": item.get("markdown"),
            "og_image": og_image,
            "published_time": meta.get("article:published_time"),
            "modified_time": meta.get("article:modified_time"),
            "site_name": meta.get("og:site_name"),
            "meta_description": meta.get("description"),
            "raw_metadata": meta,
        })
    return cleaned


def call_llm(article: Dict[str, Any], client: Optional[OpenAI] = None, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    try:
        client = client or _get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TREND_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(article)},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as exc:
        return {"error": "Invalid JSON from model", "raw": str(exc)}


def generate_trends_from_keywords(
    keywords: List[str],
    firecrawl_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Run Firecrawl + OpenAI TrendMatch workflow and return the same payload as /generate-trends."""
    keywords = [kw for kw in (keywords or []) if isinstance(kw, str) and kw.strip()]
    if not keywords:
        return []

    client = _get_openai_client(openai_api_key)
    results: List[Dict[str, Any]] = []
    for kw in keywords:
        try:
            search_result = firecrawl_search(kw, firecrawl_api_key, limit=limit)
        except Exception as exc:
            results.append({"keyword": kw, "error": str(exc)})
            continue

        if search_result.get("error"):
            results.append({"keyword": kw, "error": search_result.get("error")})
            continue

        articles = extract_full_results(search_result.get("data"))
        trend_entries = []
        for article in articles:
            trend_entries.append(call_llm(article, client=client))
        results.append({"keyword": kw, "results": trend_entries})
    return results
