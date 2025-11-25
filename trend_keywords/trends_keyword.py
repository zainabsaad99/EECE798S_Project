from flask import Flask, request, jsonify
import os
import json
from openai import OpenAI
from typing import List
import traceback
from firecrawl import Firecrawl 
from dotenv import load_dotenv
load_dotenv()
import requests
app = Flask(__name__)

# Initialize OpenAI client
OPENAI_API_KEY= os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment or .env file!")
client = OpenAI(api_key=OPENAI_API_KEY)


FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY not set in environment or .env file!")

firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)


#=================================================================
#  Seaarchable Phrase Extraction Endpoint For Trend Keywords
#=================================================================
@app.route("/extract-phrases", methods=["POST"])
def extract_full_results(raw_firecrawl_json):
    try:
        # Support current Firecrawl structure
        web_entries = raw_firecrawl_json["data"].get("web", [])
    except:
        return []

    cleaned = []
    for item in web_entries:
        meta = item.get("metadata", {})

        og_image = (
            meta.get("og:image")
            or meta.get("ogImage")
            or meta.get("twitter:image")
            or meta.get("image")
        )

        cleaned.append(
            {
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
            }
        )
    return cleaned


def extract_business_phrases(company_data: dict, model: str = "gpt-4o-mini", debug: bool = True):

    try:
        fields_to_use = [
            "company_mission", "company_name", "content_themes", "industry",
            "industry_terms", "primary_keywords", "secondary_keywords",
            "target_audience", "trending_topics", "value_propositions"
        ]

        texts = []
        for f in fields_to_use:
            val = company_data.get(f)
            if val:
                if isinstance(val, list):
                    texts.extend([str(x) for x in val])
                else:
                    texts.append(str(val))

        corpus = "\n\n".join(texts)[:15000] or "No content"

        sys_prompt = """
                Analyze the following company profile data and extract 8 to 12 multi-word interest phrases for trend searching.

                Requirements:
                1. Each phrase must be 3 to 8 words long.
                2. No single words or bigrams.
                3. No vague generalities such as 'innovation' or 'leadership'
                4. Each phrase must describe a concrete recurring theme or topic visible across the company data.
                5. Each phrase must explicitly reference a product, category, or industry domain (e.g., kitchen, home decor, pet products, car accessories). Phrases without domain context are invalid.
                6. Focus on trends and industry-specific topics that can be searched online.
                7. Exclude slogans, mission statements, or value propositions not tied to specific products or themes.
                8. Output only a JSON array of clean phrases.
                """


        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": corpus},
            ],
            temperature=0.2,
        )

        raw = resp.choices[0].message.content.strip()
        raw_clean = raw.replace("```json", "").replace("```", "").strip()

        if debug:
            print("[OPENAI BUSINESS PHRASES] raw:", raw_clean, flush=True)

        try:
            arr = json.loads(raw_clean)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception as e:
            if debug:
                print("[OPENAI BUSINESS PHRASES] JSON parse error:", e, flush=True)

        # fallback: return non-empty lines
        return [line.strip() for line in raw.split("\n") if line.strip()][:12]

    except Exception as e:
        print("[EXTRACT BUSINESS PHRASES ERROR]", traceback.format_exc(), flush=True)
        return []

# ------------------- Batch Extraction -------------------
@app.route("/extract-phrases-batch", methods=["POST"])
def extract_phrases_batch():
    try:
        data = request.get_json(force=True)
        websites = data.get("websites", [])
        if not websites:
            return jsonify({"error": "No websites provided"}), 400

        results = []
        for website in websites:
            website_id = website.get("id")
            try:
                phrases = extract_business_phrases(website)
            except Exception as e:
                print(f"[ERROR] Extracting phrases for website {website_id}: {e}", flush=True)
                phrases = []

            results.append({
                "website_id": website_id,
                "domain": website.get("domain"),
                "trend_keywords": phrases
            })

        return jsonify({"success": True, "results": results}), 200

    except Exception as e:
        print("[BATCH EXTRACTION ERROR]", traceback.format_exc(), flush=True)
        return jsonify({"error": str(e)}), 500




#=================================================================
#  Search For trend  based on extracted keywords
#=================================================================
# ------------------------------
# LLM Persona
# ------------------------------
# SYSTEM_PROMPT = """
# You are TrendExtract, a professional trend-analysis engine.
# Given a single input article, extract:
# - 3–6 design/market/UX trends
# - why the trend matters
# - evidence from the text
# - business impact (1 sentence)

# Output STRICTLY in JSON:
# {
#   "title": "",
#   "trends": [
#     {
#       "name": "",
#       "insight": "",
#       "evidence": "",
#       "impact": ""
#     }
#   ]
# }
# """
SYSTEM_PROMPT = """
You are TrendMatch, an analytical model that extracts structured, comparable information from web trend articles.

Your goal is to produce a compact, normalized JSON representation of each trend suitable for cosine-similarity matching with company profiles (which include company mission, audience, and products with descriptions).

### What to do
Analyze the article text to extract:
- The **main industry or domain** this trend belongs to
- The **core concept** or practice being discussed
- The **target audience** or users/businesses affected
- The **types of relevant products or services**
- The **practical business value or benefit**
- A list of **semantic keywords or multi-word phrases**

### Rules for consistency
1. Always output the same JSON keys, even if data is not found.
2. If a field is not clearly mentioned, set its value to `"unknown"` or an empty array (`[]`).
3. Do not include explanations, commentary, or extra text.
4. Keep phrasing factual, short, and domain-specific.
5. Output only one valid JSON object.

### Output format
{
  "title": "<short descriptive title>",
  "domain": "<main industry or field, or 'unknown'>",
  "core_concept": "<main idea or 'unknown'>",
  "target_audience": "<who this applies to, or 'unknown'>",
  "relevant_products_or_services": [
    "<list of relevant items or leave [] if none>"
  ],
  "business_value": "<functional benefit or 'unknown'>",
  "keywords": [
    "<list of key multi-word phrases or leave [] if none>"
  ]
}
"""

# ------------------------------
# Firecrawl Search
# ------------------------------
def firecrawl_search(keyword):
    query = f"latest trends about {keyword}"
    response = requests.post(
        "https://api.firecrawl.dev/v2/search",
        headers={
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "limit": 5,
            "scrapeOptions": {"formats": ["markdown"]},
        },
    )
    return {
        "keyword": keyword,
        "query": query,
        "data": response.json() if response.status_code == 200 else None,
        "error": None if response.status_code == 200 else response.text,
    }

# ------------------------------
# Extract Articles from Firecrawl
# ------------------------------
def extract_full_results(raw_firecrawl_json):
    """
    Firecrawl returns:
    {
        "data": {
            "web": [ ... ]
        }
    }
    """
    try:
        web_entries = raw_firecrawl_json.get("data", {}).get("web", [])
        print("Web entries count:", len(web_entries), flush=True)
    except Exception as e:
        print("[ERROR] extract_full_results:", e, flush=True)
        return []

    cleaned = []
    for item in web_entries:
        meta = item.get("metadata", {})
        og_image = meta.get("og:image") or meta.get("ogImage") or meta.get("twitter:image") or meta.get("image")
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

# ------------------------------
# Call GPT on Single Article
# ------------------------------
def call_llm(article):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(article)},
            ],
            temperature=0,
        )
        # Fix for new OpenAI SDK
        content = response.choices[0].message.content

        return json.loads(content)
    except Exception as e:
        return {"error": "Invalid JSON from model", "raw": str(e)}

# ------------------------------
# Generate Trends Endpoint
# ------------------------------
@app.route("/generate-trends", methods=["POST"])
def generate_trends():
    print("[GENERATE TRENDS] Request received", flush=True)
    data = request.get_json()
    keywords = data.get("keywords", [])

    if not keywords:
        return jsonify({"error": "Missing keywords[]"}), 400

    final_output = []

    for kw in keywords:
        search_result = firecrawl_search(kw)

        if search_result["error"]:
            final_output.append({"keyword": kw, "error": search_result["error"]})
            continue

        extracted_articles = extract_full_results(search_result["data"])
        trend_results = []

        for article in extracted_articles:
            trend_json = call_llm(article)
            trend_results.append(trend_json)

        final_output.append({"keyword": kw, "results": trend_results})

    return jsonify(final_output), 200


@app.route("/generate-first-trend", methods=["POST"])
def generate_first_trend():
    print("[GENERATE FIRST TREND] Request received", flush=True)
    data = request.get_json()
    keywords = data.get("keywords", [])

    if not keywords:
        return jsonify({"error": "Missing keywords[]"}), 400

    final_output = []

    for kw in keywords:
        search_result = firecrawl_search(kw)

        if search_result["error"]:
            final_output.append({"keyword": kw, "error": search_result["error"]})
            continue

        extracted_articles = extract_full_results(search_result["data"])

        if not extracted_articles:
            final_output.append({"keyword": kw, "error": "No articles found"})
            continue

        # Only process the first article
        first_article = extracted_articles[0]
        trend_json = call_llm(first_article)

        final_output.append({"keyword": kw, "result": trend_json})

    return jsonify(final_output), 200

# ------------------------------
# Run Flask App
# ------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3002)
