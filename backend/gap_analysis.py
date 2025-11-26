from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from openai import OpenAI

import logging
try:
    from linkedin_agent import fetch_trends_firecrawl as _fetch_trends_firecrawl
except Exception:
    _fetch_trends_firecrawl = None

EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.getenv("OPENAI_GAP_MODEL", os.getenv("OPENAI_CONTENT_MODEL", "gpt-4.1-mini"))
SIMILARITY_THRESHOLDS = {
    "covered": float(os.getenv("GAP_THRESHOLD_COVERED", 0.65)),
    "weak": float(os.getenv("GAP_THRESHOLD_WEAK", 0.4)),
}

_client: Optional[OpenAI] = None


def fetch_trends_via_firecrawl(
    keywords: List[str],
    topic: Optional[str] = None,
    firecrawl_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Reuse the LinkedIn agent Firecrawl helper to return formatted trend dicts."""

    if not keywords:
        return []
    if _fetch_trends_firecrawl is None:
        raise RuntimeError("Firecrawl integration is not available in this environment.")

    firecrawl_api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
    openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    if not firecrawl_api_key or not openai_api_key:
        raise RuntimeError("FIRECRAWL_API_KEY and OPENAI_API_KEY must be configured.")

    items = _fetch_trends_firecrawl(
        firecrawl_api_key=firecrawl_api_key,
        openai_api_key=openai_api_key,
        keywords=keywords,
        topic=topic,
    )

    prefix = ", ".join(keywords[:3])
    formatted: List[Dict[str, Any]] = []
    for item in items:
        trend_title = getattr(item, "title", None) or getattr(item, "trend", None)
        if not trend_title:
            continue
        description = f"{trend_title} is rising according to live conversations."
        if prefix:
            description = f"{trend_title} is rising within {prefix} conversations."
        source_url = getattr(item, "url", None) or getattr(item, "source", None)
        if source_url:
            description = f"{description} Source: {source_url}"
        formatted.append(
            {
                "trend": trend_title,
                "description": description,
                "keywords": keywords,
                "source": getattr(item, "source", "firecrawl"),
                "url": getattr(item, "url", ""),
            }
        )
    return formatted


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        _client = OpenAI(api_key=api_key)
    return _client


def _embed(texts: List[str]) -> List[np.ndarray]:
    client = _get_client()
    logging.debug("Embedding %d texts", len(texts))
    for idx, sample in enumerate(texts[:5]):
        logging.debug("[EMBED INPUT %d]: %s", idx + 1, sample)
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vectors = [np.array(item.embedding, dtype=np.float32) for item in resp.data]
    logging.debug("Embedding output shapes: %s", [vec.shape for vec in vectors[:5]])
    return vectors


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


@dataclass
class ProductVector:
    business: str
    product: str
    description: str
    vector: np.ndarray


@dataclass
class TrendVector:
    name: str
    insight: str
    evidence: str
    impact: str
    vector: np.ndarray


def _flatten_products(businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for biz in businesses or []:
        biz_name = biz.get("name") or biz.get("company_name") or "Unknown Business"
        for product in biz.get("products", []):
            price_raw = product.get("pricing") or product.get("price")
            items.append(
                {
                    "business": biz_name,
                    "name": product.get("name", "").strip(),
                    "description": (product.get("description") or "").strip(),
                    "keywords": product.get("keywords") or [],
                    "pricing_raw": price_raw,
                    "price_numeric": _parse_price(price_raw),
                }
            )
    return items


def _parse_price(price: Optional[str]) -> Optional[float]:
    if not price:
        return None
    s = str(price).strip()
    for token in ("From", "from", "+"):
        s = s.replace(token, "")
    for symbol in ["$", "€", "£", "L.L", "LL", "LBP"]:
        s = s.replace(symbol, "")
    s = s.strip()
    if not s:
        return None
    token = s.split()[0]
    try:
        return float(token)
    except ValueError:
        return None


def _prepare_product_vectors(businesses: List[Dict[str, Any]]) -> List[ProductVector]:
    rows, texts = [], []
    for biz in businesses or []:
        biz_name = biz.get("name", "Unknown Business")
        for product in biz.get("products", []):
            text = " | ".join(
                filter(
                    None,
                    [
                        product.get("name"),
                        product.get("description"),
                        biz.get("strapline"),
                        biz.get("audience"),
                    ],
                )
            )
            if not text:
                continue
            rows.append((biz_name, product.get("name", "Unnamed"), product.get("description", ""), text))
            texts.append(text)
    vectors = _embed(texts) if texts else []
    logging.debug("Product embedding input: %s", texts)
    logging.debug("Product embedding output shapes: %s", [vec.shape for vec in vectors])
    return [
        ProductVector(business=biz, product=prod, description=desc, vector=vec)
        for (biz, prod, desc, _), vec in zip(rows, vectors)
    ]


def _normalize_trend_record(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    title = (
        raw.get("trend")
        or raw.get("title")
        or raw.get("core_concept")
        or raw.get("industry")
        or raw.get("name")
    )
    if not title:
        return None
    description_parts: List[str] = []
    for field in ("description", "business_value"):
        value = raw.get(field)
        if isinstance(value, str) and value.strip():
            description_parts.append(value.strip())
    core_concept = raw.get("core_concept")
    if core_concept and core_concept != title:
        description_parts.append(str(core_concept))
    target = raw.get("target_audience")
    if isinstance(target, list) and target:
        audience = ", ".join(str(item).strip() for item in target if str(item).strip())
        if audience:
            description_parts.append(f"Audience: {audience}")
    elif isinstance(target, str) and target.strip():
        description_parts.append(f"Audience: {target.strip()}")
    domain = raw.get("domain")
    if isinstance(domain, str) and domain.strip() and domain.lower() != "unknown":
        description_parts.append(f"Domain: {domain.strip()}")
    raw_keywords = []
    for key_field in (
        "keywords",
        "semantic_keywords",
        "products_services",
        "relevant_products",
        "relevant_products_services",
        "relevant_products_or_services",
    ):
        field_value = raw.get(key_field)
        if isinstance(field_value, list):
            raw_keywords.extend(field_value)
    normalized_keywords: List[str] = [
        str(item).strip() for item in raw_keywords if str(item).strip()
    ]
    description = " ".join(description_parts).strip()
    return {
        "trend": title,
        "description": description,
        "keywords": normalized_keywords,
    }


def _flatten_trend_records(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flattened: List[Dict[str, Any]] = []
    for raw in trends or []:
        if isinstance(raw, dict) and isinstance(raw.get("results"), list):
            for child in raw["results"]:
                normalized = _normalize_trend_record(child)
                if normalized:
                    flattened.append(normalized)
        else:
            normalized = _normalize_trend_record(raw)
            if normalized:
                flattened.append(normalized)
    return flattened


def _prepare_trend_vectors(trends: List[Dict[str, Any]]) -> List[TrendVector]:
    rows, texts = [], []
    normalized_trends = _flatten_trend_records(trends)
    for entry in normalized_trends:
        trend_name = entry.get("trend")
        description = entry.get("description") or ""
        keywords = entry.get("keywords") or []
        text = " | ".join(
            filter(
                None,
                [
                    trend_name,
                    description,
                    ", ".join(keywords),
                ],
            )
        )
        if not trend_name or not text:
            continue
        rows.append((trend_name, description, keywords, text))
        texts.append(text)
    vectors = _embed(texts) if texts else []
    logging.debug("Trend embedding input: %s", texts)
    logging.debug("Trend embedding output shapes: %s", [vec.shape for vec in vectors])
    return [
        TrendVector(name=name, insight=desc, evidence=", ".join(keywords), impact="", vector=vec)
        for (name, desc, keywords, _), vec in zip(rows, vectors)
    ]


def _catalog_stats(businesses: List[Dict[str, Any]], flat_products: List[Dict[str, Any]]) -> Dict[str, Any]:
    products_per_business: Dict[str, int] = {}
    for item in flat_products:
        products_per_business[item["business"]] = products_per_business.get(item["business"], 0) + 1

    return {
        "total_products": len(flat_products),
        "total_businesses": len({biz.get("name") or biz.get("company_name") for biz in businesses or []}),
        "products_per_business": products_per_business,
    }


def _pricing_analysis(flat_products: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = [p["price_numeric"] for p in flat_products if p["price_numeric"] is not None]
    if not prices:
        return {"has_pricing": False}

    prices.sort()
    avg_price = float(np.mean(prices))

    def quantile(q: float) -> Optional[float]:
        if not prices:
            return None
        idx = int(q * (len(prices) - 1))
        return prices[idx]

    q1, q3 = quantile(0.25), quantile(0.75)
    buckets = {"low": 0, "mid": 0, "high": 0}
    for value in prices:
        if q1 is not None and value <= q1:
            buckets["low"] += 1
        elif q3 is not None and value >= q3:
            buckets["high"] += 1
        else:
            buckets["mid"] += 1

    return {
        "has_pricing": True,
        "avg_price": round(avg_price, 2),
        "min_price": round(prices[0], 2),
        "max_price": round(prices[-1], 2),
        "q1": round(q1, 2) if q1 is not None else None,
        "q3": round(q3, 2) if q3 is not None else None,
        "price_buckets": buckets,
    }


def _description_quality(flat_products: List[Dict[str, Any]]) -> Dict[str, Any]:
    desc_lengths = [len(p["description"]) for p in flat_products if p["description"]]
    empty_desc = len([p for p in flat_products if not p["description"]])

    name_lengths = [len(p["name"]) for p in flat_products if p["name"]]
    short_titles = len([length for length in name_lengths if length < 20])
    long_titles = len([length for length in name_lengths if length > 60])
    total = len(flat_products) or 1

    return {
        "total_products": len(flat_products),
        "empty_descriptions": empty_desc,
        "empty_descriptions_pct": round((empty_desc / total) * 100, 2) if flat_products else 0,
        "avg_description_length": round(float(np.mean(desc_lengths)), 2) if desc_lengths else 0,
        "avg_title_length": round(float(np.mean(name_lengths)), 2) if name_lengths else 0,
        "short_titles": short_titles,
        "long_titles": long_titles,
    }


def _keyword_coverage(businesses: List[Dict[str, Any]], flat_products: List[Dict[str, Any]]) -> Dict[str, Any]:
    counter_products: Dict[str, int] = {}
    counter_primary: Dict[str, int] = {}
    counter_secondary: Dict[str, int] = {}
    counter_topics: Dict[str, int] = {}

    def bump(counter: Dict[str, int], tokens):
        for token in tokens or []:
            if token:
                key = token.lower()
                counter[key] = counter.get(key, 0) + 1

    for biz in businesses or []:
        bump(counter_primary, biz.get("primary_keywords"))
        bump(counter_secondary, biz.get("secondary_keywords"))
        bump(counter_topics, biz.get("trending_topics"))

    for product in flat_products:
        bump(counter_products, product.get("keywords"))

    def top(counter):
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "top_product_keywords": top(counter_products),
        "top_primary_keywords": top(counter_primary),
        "top_secondary_keywords": top(counter_secondary),
        "trending_topics": top(counter_topics),
    }


def _simple_trend_alignment(flat_products: List[Dict[str, Any]], trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def tokenize(text: str) -> List[str]:
        return [token.strip(" ,.;:!?\"'()").lower() for token in (text or "").split() if token.strip()]

    catalog_tokens: Dict[str, int] = {}
    for product in flat_products:
        for token in tokenize(product.get("name", "")):
            catalog_tokens[token] = catalog_tokens.get(token, 0) + 1
        for keyword in product.get("keywords", []):
            for token in tokenize(keyword):
                catalog_tokens[token] = catalog_tokens.get(token, 0) + 1

    results: List[Dict[str, Any]] = []
    for trend in trends or []:
        label = trend.get("trend") or trend.get("name")
        if not label:
            continue
        tokens = tokenize(label + " " + " ".join(trend.get("keywords") or []))
        if not tokens:
            continue
        matches = [token for token in tokens if catalog_tokens.get(token)]
        normalized = len(matches) / len(tokens)
        if normalized >= 0.7:
            status = "covered"
        elif normalized >= 0.4:
            status = "weak_coverage"
        else:
            status = "gap"
        results.append(
            {
                "trend": label,
                "coverage_score": round(normalized, 2),
                "matched_tokens": matches,
                "status": status,
            }
        )
    return results


def _opportunity_summary(description_stats, pricing_stats, trend_alignment) -> List[str]:
    opps: List[str] = []
    if description_stats.get("empty_descriptions_pct", 0) > 40:
        opps.append("A large portion of products lack descriptions. Filling these improves SEO and conversion.")
    if pricing_stats.get("has_pricing"):
        spread = pricing_stats["max_price"] - pricing_stats["min_price"]
        if spread > 100:
            opps.append("Pricing spans wide bands; consider clearer segmentation across tiers.")
    gaps = [item for item in trend_alignment if item.get("status") == "gap"]
    if gaps:
        names = ", ".join(item["trend"] for item in gaps[:5])
        opps.append(f"Detected market trends with low coverage: {names}. Explore offers in these areas.")
    return opps


def _categorize(score: float) -> str:
    if score >= SIMILARITY_THRESHOLDS["covered"]:
        return "covered"
    if score >= SIMILARITY_THRESHOLDS["weak"]:
        return "weak"
    return "gap"


def _reason_over_gaps(similarity_map: List[Dict[str, Any]], context: str = "") -> Dict[str, Any]:
    if not similarity_map:
        return {"summary": "No valid comparison could be made.", "actions": [], "priority_matrix": []}

    prompt = f"""
You are a market intelligence strategist.

Similarity analysis between business products and market trends:
{json.dumps(similarity_map, indent=2)}

Context:
{context or "N/A"}

Rules:
- similarity >= {SIMILARITY_THRESHOLDS['covered']} → Covered (strong positioning)
- {SIMILARITY_THRESHOLDS['weak']}–{SIMILARITY_THRESHOLDS['covered']} → Weak coverage
- < {SIMILARITY_THRESHOLDS['weak']} → Gap (missing opportunity)

Deliver concise JSON with keys:
1. "insight_summary": bullet-style narrative.
2. "recommendations": list of objects {{ "title", "why_it_matters", "actions", "priority" }}.
3. "priority_matrix": list of objects {{ "opportunity", "priority", "confidence" }}.
Use High/Medium/Low priorities.
"""
    client = _get_client()
    completion = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(completion.choices[0].message.content)
    except Exception:
        return {"summary": completion.choices[0].message.content}


def _propose_product_extensions(
    weak_entries: List[Dict[str, Any]],
    gap_entries: List[Dict[str, Any]],
    context: str = "",
    max_trends: int = 6,
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for entry in gap_entries or []:
        enriched.append(
            {
                **entry,
                "coverage_level": entry.get("coverage_level") or entry.get("category") or "gap",
            }
        )
    for entry in weak_entries or []:
        enriched.append(
            {
                **entry,
                "coverage_level": entry.get("coverage_level") or entry.get("category") or "weak",
            }
        )
    if not enriched:
        return []
    sample = enriched[:max_trends]
    payload = {
        "gaps": sample,
        "context": context,
        "instruction": """
You are a product innovation strategist embedded in a go-to-market intelligence platform.
Your task is to convert each trend alignment entry into a tangible product extension brief.

Overall Objectives
1. For every record, produce a product concept that either patches a weak coverage area or fills a true gap.
2. Highlight how the concept improves customer outcomes and business impact.
3. Estimate the blended working hours and working price (USD) required to scope, design, and launch a lean version.
4. Provide an actionable list of launch steps (3-6 items) that a cross-functional squad can execute.
5. Identify the target persona/segment, the pains relieved, expected success metrics, affected systems, and key risks/dependencies.

Prompting Rules
- Always restate the trend in your own words to prove understanding.
- Use coverage_level to shape the recommendation:
  * gap → net-new product or major capability.
  * weak → enhancement to an existing module or workflow improvement.
- Assume a SaaS team with product, design, eng, data science, and GTM enablement.
- Working hours should reflect total cross-functional effort; price is hours * $120 blended rate unless context dictates otherwise.
- Launch steps must be concrete actions (e.g., “Instrument churn signals for beta cohort”) not vague statements.
- Tone: decisive, operator-focused, free of filler.
Output Format
Return a JSON array where each object contains:
- trend (string)
- coverage_level (string: "gap" or "weak")
- proposal (string, 3–4 sentences describing the concept)
- why_it_helps (string, 2 sentences covering user value + business value)
- target_persona (string describing primary persona/segment and their pain)
- success_metrics (array of strings, each KPI with measurable target)
- system_impact (string covering data/platform dependencies)
- risks (array of strings calling out blockers or assumptions)
- working_hours (number)
- working_price (number)
- launch_steps (array of 3–6 short imperative strings)
""".strip(),
    }
    client = _get_client()
    completion = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a pragmatic SaaS product strategist who designs actionable product extensions.",
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "product_proposals",
                "schema": {
                    "type": "object",
                    "properties": {
                        "proposals": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "trend": {"type": "string"},
                                    "proposal": {"type": "string"},
                                    "why_it_helps": {"type": "string"},
                                    "coverage_level": {"type": "string"},
                                    "target_persona": {"type": "string"},
                                    "success_metrics": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "system_impact": {"type": "string"},
                                    "risks": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "working_hours": {"type": "number"},
                                    "working_price": {"type": "number"},
                                    "launch_steps": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": [
                                    "trend",
                                    "proposal",
                                    "why_it_helps",
                                     "target_persona",
                                     "success_metrics",
                                     "system_impact",
                                     "risks",
                                    "working_hours",
                                    "working_price",
                                    "coverage_level",
                                ],
                            },
                        }
                    },
                    "required": ["proposals"],
                },
            },
        },
    )
    try:
        data = json.loads(completion.choices[0].message.content)
        proposals = data.get("proposals")
        if isinstance(proposals, list):
            return proposals
    except Exception:
        pass
    return []


def run_gap_analysis(
    businesses: List[Dict[str, Any]],
    trends: Optional[List[Dict[str, Any]]] = None,
    additional_context: str = "",
    auto_trend_keywords: Optional[List[str]] = None,
    trend_topic: Optional[str] = None,
    firecrawl_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    generate_product_proposals: bool = False,
) -> Dict[str, Any]:
    trends = trends or []
    if not trends and auto_trend_keywords:
        try:
            trends = fetch_trends_via_firecrawl(
                auto_trend_keywords,
                topic=trend_topic,
                firecrawl_api_key=firecrawl_api_key,
                openai_api_key=openai_api_key,
            )
        except Exception as err:
            raise RuntimeError(f"Unable to fetch trends via Firecrawl: {err}") from err

    flat_products = _flatten_products(businesses)
    catalog_report = {
        "catalog_stats": _catalog_stats(businesses, flat_products),
        "pricing_analysis": _pricing_analysis(flat_products),
        "description_quality": _description_quality(flat_products),
        "keyword_coverage": _keyword_coverage(businesses, flat_products),
        "trend_alignment": _simple_trend_alignment(flat_products, trends),
    }
    catalog_report["opportunity_summary"] = _opportunity_summary(
        catalog_report["description_quality"],
        catalog_report["pricing_analysis"],
        catalog_report["trend_alignment"],
    )

    product_vectors = _prepare_product_vectors(businesses)
    trend_vectors = _prepare_trend_vectors(trends)

    if not product_vectors or not trend_vectors:
        raise ValueError("Insufficient data. Provide at least one product and one trend entry.")

    similarity_map: List[Dict[str, Any]] = []
    coverage_buckets = {"covered": [], "weak": [], "gap": []}

    for trend in trend_vectors:
        best: Optional[Tuple[ProductVector, float]] = None
        for product in product_vectors:
            score = _cosine(trend.vector, product.vector)
            logging.debug(
                "Matrix entry: trend '%s' vs product '%s' -> %.4f",
                trend.name,
                product.product,
                score,
            )
            if best is None or score > best[1]:
                best = (product, score)
        if best is None:
            continue
        product, score = best
        logging.debug(
            "Similarity score for trend '%s' vs best product '%s': %.4f",
            trend.name,
            product.product,
            score,
        )
        category = _categorize(score)
        entry = {
            "trend": trend.name,
            "trend_summary": trend.impact or trend.insight or trend.evidence,
            "best_match_product": product.product,
            "business": product.business,
            "similarity": round(score, 4),
            "category": category,
            "keywords": [],
            "product_summary": product.description,
        }
        similarity_map.append(entry)
        coverage_buckets[category].append(entry)

    insights = _reason_over_gaps(similarity_map, additional_context)
    coverage_counts = {k: len(v) for k, v in coverage_buckets.items()}
    total_trends = sum(coverage_counts.values()) or 1
    coverage_summary = {
        k: {
            "count": count,
            "percent": round((count / total_trends) * 100, 1),
        }
        for k, count in coverage_counts.items()
    }

    gap_keywords = Counter()
    for entry in coverage_buckets["gap"]:
        for kw in entry.get("keywords") or []:
            if kw:
                gap_keywords[kw.lower()] += 1
    top_gap_themes = gap_keywords.most_common(10)
    product_proposals = (
        _propose_product_extensions(coverage_buckets["weak"], coverage_buckets["gap"], additional_context)
        if generate_product_proposals
        else []
    )

    opportunity_map: List[Dict[str, Any]] = []
    for entry in coverage_buckets["gap"][:8]:
        keywords = ", ".join(entry.get("keywords") or []) or "new proof points"
        note = (
            f"Extend {entry['best_match_product']} ({entry['business']}) to address "
            f"{entry['trend']} by emphasizing {keywords}."
        )
        opportunity_map.append(
            {
                "trend": entry["trend"],
                "best_match_product": entry["best_match_product"],
                "business": entry["business"],
                "similarity": entry["similarity"],
                "note": note,
            }
        )

    trend_confidence = sorted(
        catalog_report["trend_alignment"],
        key=lambda x: x.get("coverage_score", 0),
        reverse=True,
    )[:8]
    action_plan = catalog_report.get("opportunity_summary", [])

    return {
        "similarity_map": similarity_map,
        "coverage": coverage_buckets,
        "insights": insights,
        "coverage_summary": coverage_summary,
        "top_gap_themes": top_gap_themes,
        "product_proposals": product_proposals,
        "opportunity_map": opportunity_map,
        "action_plan": action_plan,
        "trend_confidence": trend_confidence,
        "catalog_report": catalog_report,
    }
