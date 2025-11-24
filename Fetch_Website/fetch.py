import os
from flask import Flask, request, jsonify
from firecrawl import Firecrawl 

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

if not FIRECRAWL_API_KEY:
    raise ValueError("FIRECRAWL_API_KEY not set in environment or .env file!")

app = Flask(__name__)
firecrawl = Firecrawl(api_key=FIRECRAWL_API_KEY)

def merge_extracted_data(all_data):
    """Merge and deduplicate extracted data from multiple batches"""
    merged = {
        "domain": None,
        "company_name": None,
        "industry": None,
        "company_mission": None,
        "location": None,
        "target_market": [],
        "primary_keywords": [],
        "secondary_keywords": [],
        "trending_topics": [],
        "industry_terms": [],
        "products_by_category": {},  # Group products by category
        "target_audience": None,
        "value_propositions": [],
        "content_themes": []
    }
    
    for item in all_data:
        # Merge single-value fields (take first non-empty)
        if not merged["domain"] and item.get("domain"):
            merged["domain"] = item["domain"]
        if not merged["company_name"] and item.get("company_name"):
            merged["company_name"] = item["company_name"]
        if not merged["industry"] and item.get("industry"):
            merged["industry"] = item["industry"]
        if not merged["company_mission"] and item.get("company_mission"):
            merged["company_mission"] = item["company_mission"]
        if not merged["location"] and item.get("location"):
            merged["location"] = item["location"]
        if not merged["target_audience"] and item.get("target_audience"):
            merged["target_audience"] = item["target_audience"]
        
        # Merge array fields (deduplicate)
        for field in ["target_market", "primary_keywords", "secondary_keywords", 
                      "trending_topics", "industry_terms", "value_propositions", "content_themes"]:
            if item.get(field):
                merged[field].extend(item[field])
        
        # Group products by category
        if item.get("products"):
            for product in item["products"]:
                # Determine category (you can customize this logic)
                category = product.get("category", "Uncategorized")
                
                if category not in merged["products_by_category"]:
                    merged["products_by_category"][category] = []
                
                # Check if product already exists (deduplicate by name)
                product_names = [p["name"] for p in merged["products_by_category"][category]]
                if product.get("name") not in product_names:
                    merged["products_by_category"][category].append(product)
    
    # Deduplicate arrays
    for field in ["target_market", "primary_keywords", "secondary_keywords", 
                  "trending_topics", "industry_terms", "value_propositions", "content_themes"]:
        merged[field] = list(set(merged[field]))
    
    return merged

@app.route('/extract-website', methods=['POST'])
def extract_website():
    try:
        data = request.get_json()
        url = data.get('url')
        print("DEBUG: URL =", url, flush=True)
        
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        print("Mapping website URLs...")
        map_result = firecrawl.map(
            url=url,
            sitemap="include", # can be "only" or "include"
            limit=5000
        )
        
        all_urls = [link.url for link in map_result.links]
        filtered_urls = [
            url for url in all_urls 
            if not any(exclude in url for exclude in ['/products/', '/ar/', 'sitemap.xml'])
        ]
        
        print(f"Found {len(filtered_urls)} main pages")
        
        # Enhanced schema with category
        schema = {
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "company_name": {"type": "string"},
                "industry": {"type": "string"},
                "company_mission": {"type": "string"},
                "location": {"type": "string"},
                "target_market": {"type": "array", "items": {"type": "string"}},
                "primary_keywords": {"type": "array", "items": {"type": "string"}},
                "secondary_keywords": {"type": "array", "items": {"type": "string"}},
                "trending_topics": {"type": "array", "items": {"type": "string"}},
                "industry_terms": {"type": "array", "items": {"type": "string"}},
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "category": {"type": "string"},  # Added category
                            "description": {"type": "string"},
                            "features": {"type": "array", "items": {"type": "string"}},
                            "pricing": {"type": "string"},
                            "keywords": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                },
                "target_audience": {"type": "string"},
                "value_propositions": {"type": "array", "items": {"type": "string"}},
                "content_themes": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["domain", "company_name", "products", "primary_keywords", "location", "target_market"]
        }
        
        # Extract in batches
        all_data = []
        # limit for testing the extraction 
        for i in range(0, len(filtered_urls), 10):
            batch = filtered_urls[i:i+10]
            print(f"Extracting batch {i//10 + 1} ({len(batch)} URLs)...")
            
            result = firecrawl.extract(
                urls=batch,
                prompt="Extract company info, products with their categories, and all relevant keywords.",
                schema=schema
            )
            
            all_data.extend(result.data if isinstance(result.data, list) else [result.data])
        
        # Merge and deduplicate data
        merged_data = merge_extracted_data(all_data)
        
        print(f"Done! Extracted and merged data from {len(all_data)} results")
        
        return jsonify({
            "success": True,
            "total_pages": len(filtered_urls),
            "extracted_count": len(all_data),
            "data": merged_data
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3001)