"""
LinkedIn Content Agent module - extracted from open_linkedin.py
Contains all the core functionality for LinkedIn content generation
"""

from __future__ import annotations

import os
import re
import json
import time
import tempfile
import shutil
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

import requests
from pydantic import BaseModel

# Optional imports
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None

try:
    from firecrawl import Firecrawl
except Exception:
    Firecrawl = None

from PIL import Image

# Constants
PHANTOM_LAUNCH_URL = "https://api.phantombuster.com/api/v2/agents/launch"
PHANTOM_FETCH_OUTPUT_URL = "https://api.phantombuster.com/api/v2/containers/fetch-output"

SCRAPE_AGENT_ID = "157605755168271"  # LinkedIn Activities Scraper
POST_AGENT_ID = "4269915876888936"    # LinkedIn Auto Poster

DEFAULT_POLL_SECONDS = 5
DEFAULT_MAX_WAIT_SECONDS = 180
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


# Data structures
@dataclass
class PostItem:
    postUrl: Optional[str]
    imgUrl: Optional[str]
    type: Optional[str]
    postContent: Optional[str]
    likeCount: Optional[int]
    commentCount: Optional[int]
    repostCount: Optional[int]
    postDate: Optional[str]
    action: Optional[str]
    author: Optional[str]
    authorUrl: Optional[str]
    profileUrl: Optional[str]
    timestamp: Optional[str]
    postTimestamp: Optional[str]


class TrendItem(BaseModel):
    title: str
    url: str
    source: Optional[str] = None


# HTTP utilities
def _http_post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 60, debug: bool = True) -> Dict[str, Any]:
    if debug:
        print(f"[HTTP POST] url: {url}")
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if debug:
        print(f"[HTTP POST] status: {r.status_code}")
    r.raise_for_status()
    return r.json()


def _http_get_text(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 60, debug: bool = True) -> str:
    if debug:
        print(f"[HTTP GET] url: {url}")
    r = requests.get(url, headers=headers, timeout=timeout)
    if debug:
        print(f"[HTTP GET] status: {r.status_code}")
    r.raise_for_status()
    return r.text


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 60, debug: bool = True) -> Dict[str, Any]:
    if debug:
        print(f"[HTTP GET JSON] url: {url}")
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    if debug:
        print(f"[HTTP GET JSON] status: {r.status_code}")
    r.raise_for_status()
    return r.json()


# PhantomBuster functions
def launch_linkedin_scrape(phantom_api_key: str, session_cookie: str, user_agent: str, profile_url: str, number_of_lines_per_launch: int = 1, number_max_posts: int = 20, csv_name: str = "result", debug: bool = True) -> str:
    headers = {
        "x-phantombuster-key": phantom_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "id": SCRAPE_AGENT_ID,
        "argument": {
            "numberOfLinesPerLaunch": number_of_lines_per_launch,
            "numberMaxOfPosts": number_max_posts,
            "csvName": csv_name,
            "activitiesToScrape": ["Post"],
            "spreadsheetUrl": profile_url,
            "sessionCookie": session_cookie,
            "userAgent": user_agent,
        },
    }
    data = _http_post_json(PHANTOM_LAUNCH_URL, headers, payload, debug=debug)
    container_id = str(data.get("containerId") or data.get("id") or "")
    if not container_id:
        raise RuntimeError("No container id returned by PhantomBuster")
    return container_id


def fetch_container_output_for_json_url(phantom_api_key: str, container_id: str, poll_seconds: int = DEFAULT_POLL_SECONDS, max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS, debug: bool = True, progress_callback=None) -> str:
    """
    Fetch container output with optional progress callback.
    progress_callback should be a function that takes a message string.
    """
    headers = {"x-phantombuster-key": phantom_api_key}
    deadline = time.time() + max_wait_seconds
    primary_pat = re.compile(r"JSON saved at\s+(https?://\S+?)\s+result\.json", re.IGNORECASE)
    fallback_pat = re.compile(r"(https?://\S*?result\.json)", re.IGNORECASE)
    found_url = None
    poll_count = 0
    last_progress_time = time.time()

    while time.time() < deadline and not found_url:
        url_with_id = f"{PHANTOM_FETCH_OUTPUT_URL}?id={container_id}"
        text = _http_get_text(url_with_id, headers=headers, debug=debug)
        m = primary_pat.search(text)
        if m:
            base = m.group(1).rstrip("/")
            found_url = f"{base}/result.json"
            break
        m2 = fallback_pat.search(text)
        if m2:
            found_url = m2.group(1)
            break
        
        poll_count += 1
        elapsed = int(time.time() - (deadline - max_wait_seconds))
        
        # Send progress updates every 15 seconds or every 3 polls
        if progress_callback and (time.time() - last_progress_time >= 15 or poll_count % 3 == 0):
            if elapsed < 60:
                msg = f"Scraping in progress... ({elapsed}s elapsed)"
            elif elapsed < 120:
                msg = f"Still scraping... This usually takes 2-3 minutes ({elapsed}s elapsed)"
            else:
                msg = f"Scraping taking longer than usual... Please wait ({elapsed}s elapsed)"
            progress_callback(msg)
            last_progress_time = time.time()
        
        if debug:
            print(f"[FETCH OUTPUT] result url not found yet, sleeping {poll_seconds}")
        time.sleep(poll_seconds)

    if not found_url:
        raise TimeoutError("Could not locate result.json url in PhantomBuster output")
    return found_url


def download_posts_json(json_url: str, debug: bool = True) -> List[PostItem]:
    r = requests.get(json_url, timeout=60)
    r.raise_for_status()
    arr = r.json()
    posts: List[PostItem] = []
    if isinstance(arr, list):
        for x in arr:
            item_data = {k: x.get(k) for k in PostItem.__annotations__.keys()}
            posts.append(PostItem(**item_data))
    if debug:
        print(f"[DOWNLOAD POSTS] total posts: {len(posts)}")
    return posts


def trigger_phantombuster_autopost(phantom_api_key: str, session_cookie: str, user_agent: str, sheet_url: str, number_of_posts_per_launch: int = 1, debug: bool = True) -> Dict[str, Any]:
    headers = {
        "x-phantombuster-key": phantom_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "id": POST_AGENT_ID,
        "argument": {
            "numberTweetsPerLaunch": 10,
            "visibility": "anyone",
            "sessionCookie": session_cookie,
            "userAgent": user_agent,
            "spreadsheetUrl": sheet_url,
            "numberOfPostsPerLaunch": number_of_posts_per_launch,
        },
    }
    return _http_post_json(PHANTOM_LAUNCH_URL, headers, payload, debug=debug)


# OpenAI helpers
def summarize_image_with_openai(image_url: str, openai_api_key: str, model: str = DEFAULT_OPENAI_MODEL, debug: bool = True) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=openai_api_key)
    content = [
        {"type": "text", "text": "Summarize this LinkedIn image post in two sentences. No hashtags."},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]
    resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}], temperature=0.2)
    summary = resp.choices[0].message.content.strip()
    if debug:
        print(f"[OPENAI IMG] summary: {summary}")
    return summary


def extract_common_interests(posts: List[PostItem], openai_api_key: str, model: str = DEFAULT_OPENAI_MODEL, max_image_summaries: int = 5, debug: bool = True) -> List[str]:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=openai_api_key)
    texts: List[str] = []
    for p in posts:
        if p.postContent:
            texts.append(str(p.postContent))
    image_summaries = 0
    for p in posts:
        if not p.postContent and p.imgUrl and image_summaries < max_image_summaries:
            try:
                summary = summarize_image_with_openai(p.imgUrl, openai_api_key, model=model, debug=debug)
                texts.append(summary)
                image_summaries += 1
            except Exception as e:
                if debug:
                    print(f"[OPENAI IMG] error for image summary: {e}")
    corpus = "\n\n".join(texts)[:15000]
    sys_prompt = (
        "Analyze the following LinkedIn posts and image summaries and extract eight to twelve "
        "multi word interest phrases. Requirements: "
        "1. Each phrase must be 3 to 8 words long. "
        "2. No single words or bigrams. "
        "3. No vague generalities like 'innovation' or 'leadership'. "
        "4. Each phrase must describe a concrete recurring theme or topic visible across the posts. "
        "5. Output only a JSON array of clean phrases."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": corpus or "No content"},
        ],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()
    if debug:
        print(f"[OPENAI KW] raw: {raw_clean}")
    try:
        arr = json.loads(raw_clean)
        if isinstance(arr, list):
            return [str(x).strip().lower() for x in arr if str(x).strip()]
    except Exception as e:
        if debug:
            print(f"[OPENAI KW] parse error: {e}")
    return [w.strip().lower() for w in raw.split("\n") if w.strip()][:12]


def infer_writing_style_from_posts(posts: List[PostItem], openai_api_key: str, model: str = DEFAULT_OPENAI_MODEL, debug: bool = True) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=openai_api_key)
    sample = "\n\n".join([p.postContent or "" for p in posts])[:15000]
    sys_prompt = (
        "You will receive multiple LinkedIn posts from one profile. "
        "Summarize the writing style in six to ten bullet style points. "
        "Cover tone, sentence length, structure, vocabulary, use of emojis, "
        "use of hashtags, and type of calls to action. "
        "Keep the description precise and actionable. "
        "IMPORTANT: Do NOT use markdown formatting (no **, no -, no bullet points). "
        "Write in plain text with clear, readable sentences. "
        "Each point should be a complete sentence or short paragraph."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": sample or "No content"},
        ],
    )
    notes = resp.choices[0].message.content.strip()
    if debug:
        print(f"[STYLE] notes: {notes[:400]}")
    return notes


def generate_linkedin_post(openai_key: str, topic: str, style_notes: Optional[str], keywords: List[str], model: str = DEFAULT_OPENAI_MODEL, debug: bool = True) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    client = OpenAI(api_key=openai_key)
    sys_prompt = (
        "You are a LinkedIn copywriter. Write a polished LinkedIn post about the given topic "
        "and do NOT introduce unrelated topics. Focus only on the provided topic. "
        "If other keywords are provided, ignore them and write only about the topic. "
        "Start with a strong hook. Use two or three short paragraphs, each with a single clear idea. "
        "Include a simple call to action near the end. Finish with six to ten relevant hashtags on a separate line. "
        "Keep the entire post under about 1300 characters."
    )
    user_content = (
        f"Topic: {topic}\n\n"
        f"Style guidance:\n{style_notes or 'Neutral professional tone with clear structure and no specific constraints.'}\n\n"
        "Note: Do NOT use any user interest keywords or other profile keywords. Write only about the topic above."
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.6,
    )
    post_text = resp.choices[0].message.content.strip()
    if debug:
        print(f"[GEN POST] length: {len(post_text)}")
    return post_text


def _sanitize_keywords_input(keywords, debug=False):
    if keywords is None:
        return []
    if isinstance(keywords, List):
        cleaned = []
        for k in keywords:
            if isinstance(k, str):
                ck = k.strip().strip('`')
                if ck and ck not in ["[", "]"]:
                    cleaned.append(ck)
        return cleaned
    if isinstance(keywords, str):
        txt = keywords.strip().strip("`")
        txt2 = txt.replace("```json", "").replace("```", "").strip()
        try:
            arr = json.loads(txt2)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except:
            pass
        parts = re.split(r"[\n,]+", txt2)
        return [p.strip() for p in parts if p.strip()]
    return []


# Firecrawl functions
def fetch_trends_firecrawl(firecrawl_api_key: str, openai_api_key: str, keywords: Optional[List[str]] = None, topic: Optional[str] = None, max_web_items: int = 10, max_news_items: int = 10, debug: bool = True) -> List[TrendItem]:
    if Firecrawl is None:
        raise RuntimeError("firecrawl package is not installed")
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    if not firecrawl_api_key:
        raise RuntimeError("Firecrawl API key is missing")
    cleaned = _sanitize_keywords_input(keywords, debug=debug)
    if topic and topic.strip():
        query_text = f"latest trends about {topic.strip()}"
    else:
        kw = cleaned[:6]
        if not kw:
            kw = ["technology", "business", "innovation"]
        joined = ", ".join(kw)
        query_text = f"latest trends about {joined}"
    if debug:
        print(f"[FIRECRAWL] query: {query_text}")
    firecrawl_client = Firecrawl(api_key=firecrawl_api_key)
    result = firecrawl_client.search(query=query_text, limit=max_web_items + max_news_items)
    data = result if hasattr(result, "web") or hasattr(result, "news") else None
    data_web = data.web if hasattr(data, "web") and data.web else []
    data_news = data.news if hasattr(data, "news") and data.news else []
    client = OpenAI(api_key=openai_api_key)
    summaries: List[str] = []

    def summarize(text_block: str) -> str:
        try:
            resp = client.chat.completions.create(
                model=DEFAULT_OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Summarize the item in one clear sentence."},
                    {"role": "user", "content": text_block},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if debug:
                print(f"[SUMMARY ERROR] {e}")
            return ""

    for item in data_web[:max_web_items]:
        title = item.title or ""
        desc = item.description or ""
        url = item.url or ""
        block = f"{title}. {desc}. Source: {url}"
        summaries.append(summarize(block))
    for item in data_news[:max_news_items]:
        title = item.title or ""
        desc = item.snippet or ""
        url = item.url or ""
        block = f"{title}. {desc}. Source: {url}"
        summaries.append(summarize(block))
    combined_text = "\n".join(summaries)[:15000]
    if debug:
        print(f"[FIRECRAWL] combined summary length: {len(combined_text)}")
    sys_prompt = (
        "You are an expert trend analyst. "
        "Extract exactly five clear phrase level trends. "
        "Return only a JSON array of five strings."
    )
    resp = client.chat.completions.create(
        model=DEFAULT_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": combined_text or "No data"},
        ],
        temperature=0.3,
    )
    raw = resp.choices[0].message.content.strip()
    raw_clean = raw.replace("```json", "").replace("```", "").strip()
    try:
        phrases = json.loads(raw_clean)
        if isinstance(phrases, list):
            phrases = [p.strip() for p in phrases if p.strip()]
        else:
            phrases = []
    except Exception:
        phrases = [line.strip() for line in raw_clean.split("\n") if line.strip()]
    phrases = phrases[:5]
    first_url = ""
    if len(data_web) > 0:
        first_url = data_web[0].url or ""
    trend_items = [TrendItem(title=phrase, url=first_url, source="firecrawl") for phrase in phrases]
    return trend_items


# Google Sheets functions
def save_post_to_google_sheet(sheet_url: str, content: str, service_account_json_path: str, debug: bool = True) -> Tuple[str, int]:
    if gspread is None or Credentials is None:
        raise RuntimeError("gspread or google auth is not installed")
    if debug:
        print(f"[GSHEETS] save content length: {len(content)}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(service_account_json_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    ws = sh.sheet1
    ws.append_row([content], value_input_option="RAW")
    if debug:
        print(f"[GSHEETS] append done {ws.id} {ws.row_count}")
    return (ws.id, ws.row_count)


def clear_google_sheet(sheet_url: str, service_account_json_path: str, debug: bool = True) -> bool:
    """Clear all data from the Google Sheet (except header row if exists)"""
    if gspread is None or Credentials is None:
        raise RuntimeError("gspread or google auth is not installed")
    if debug:
        print(f"[GSHEETS] clearing sheet: {sheet_url}")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(service_account_json_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    ws = sh.sheet1
    
    # Get all values
    all_values = ws.get_all_values()
    if not all_values:
        if debug:
            print(f"[GSHEETS] sheet is already empty")
        return True
    
    # Clear all rows (including header if you want, or keep first row)
    # Option 1: Clear everything including header
    ws.clear()
    
    # Option 2: If you want to keep header row, uncomment below and comment above
    # if len(all_values) > 1:
    #     ws.delete_rows(2, len(all_values))
    
    if debug:
        print(f"[GSHEETS] cleared {len(all_values)} rows")
    return True


# Tool implementations for function calling
def scrape_profile_tool(phantom_api_key: str, session_cookie: str, user_agent: str, profile_url: str, progress_callback=None) -> Dict[str, Any]:
    """
    Scrape profile with optional progress callback.
    progress_callback should be a function that takes a message string.
    """
    if progress_callback:
        progress_callback("Launching PhantomBuster scrape...")
    
    container_id = launch_linkedin_scrape(
        phantom_api_key=phantom_api_key,
        session_cookie=session_cookie,
        user_agent=user_agent,
        profile_url=profile_url,
    )
    
    if progress_callback:
        progress_callback("Scrape launched! Waiting for results...")
    
    json_url = fetch_container_output_for_json_url(
        phantom_api_key=phantom_api_key,
        container_id=container_id,
        progress_callback=progress_callback,
    )
    
    if progress_callback:
        progress_callback("Scrape completed! Downloading posts...")
    
    posts = download_posts_json(json_url)
    
    if progress_callback:
        progress_callback(f"Downloaded {len(posts)} posts successfully!")
    
    return {
        "json_url": json_url,
        "posts": [p.__dict__ for p in posts],
    }


def extract_keywords_tool(openai_api_key: str, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    post_objs = [
        PostItem(**{k: d.get(k) for k in PostItem.__annotations__.keys()})
        for d in posts
    ]
    keywords = extract_common_interests(post_objs, openai_api_key=openai_api_key)
    return {"keywords": keywords}


def infer_style_tool(openai_api_key: str, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    post_objs = [
        PostItem(**{k: d.get(k) for k in PostItem.__annotations__.keys()})
        for d in posts
    ]
    style = infer_writing_style_from_posts(post_objs, openai_api_key=openai_api_key)
    return {"style_notes": style}


def fetch_trends_firecrawl_tool(firecrawl_api_key: str, openai_api_key: str, keywords: List[str], topic: Optional[str] = None) -> Dict[str, Any]:
    items = fetch_trends_firecrawl(
        firecrawl_api_key=firecrawl_api_key,
        openai_api_key=openai_api_key,
        keywords=keywords,
        topic=topic,
    )
    return {"trends": [item.model_dump() for item in items]}


def call_tool_by_name(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    print(f"[DISPATCH] tool: {name}")
    try:
        if name == "scrape_profile_tool":
            return scrape_profile_tool(**args)
        if name == "extract_keywords_tool":
            return extract_keywords_tool(**args)
        if name == "infer_style_tool":
            return infer_style_tool(**args)
        if name == "fetch_trends_firecrawl_tool":
            return fetch_trends_firecrawl_tool(**args)
    except Exception as e:
        print(f"[DISPATCH] tool error: {e}")
        return {"error": str(e)}
    return {"error": f"unknown tool {name}"}


def make_functions_schema() -> List[Dict[str, Any]]:
    """Create function schemas for OpenAI function calling"""
    return [
        {
            "name": "scrape_profile_tool",
            "description": "Scrape a LinkedIn profile posts via PhantomBuster and return posts array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phantom_api_key": {"type": "string"},
                    "session_cookie": {"type": "string"},
                    "user_agent": {"type": "string"},
                    "profile_url": {"type": "string"},
                },
                "required": ["phantom_api_key", "session_cookie", "user_agent", "profile_url"],
            },
        },
        {
            "name": "extract_keywords_tool",
            "description": "Extract recurring interest phrases from posts content and image summaries using OpenAI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openai_api_key": {"type": "string"},
                    "posts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["openai_api_key", "posts"],
            },
        },
        {
            "name": "infer_style_tool",
            "description": "Infer writing style from LinkedIn posts using OpenAI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openai_api_key": {"type": "string"},
                    "posts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["openai_api_key", "posts"],
            },
        },
        {
            "name": "fetch_trends_firecrawl_tool",
            "description": (
                "Fetch up to five phrase level trends using Firecrawl search and OpenAI. "
                "If topic is provided, trends are focused on that topic. "
                "Otherwise trends are focused on the provided keywords."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "firecrawl_api_key": {"type": "string"},
                    "openai_api_key": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "topic": {"type": "string"},
                },
                "required": ["firecrawl_api_key", "openai_api_key", "keywords"],
            },
        },
    ]


# Agent orchestration using function calling
def run_agent_sequence(openai_api_key: str, phantom_api_key: str, firecrawl_api_key: str, session_cookie: str, user_agent: str, user_profile_url: str, style_profile_url: str, debug: bool = True) -> Dict[str, Any]:
    """
    Agent loop that uses OpenAI function calling.
    GPT orchestrates the workflow by deciding which tools to call and in what order.
    The final assistant message must be a JSON object string with:
    {
      "json_url": str,
      "keywords": list[str],
      "style_notes": str,
      "trends": list[TrendItem-like dict]
    }
    """
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")

    client = OpenAI(api_key=openai_api_key)

    # Check if style profile is same as user profile (optimize scraping)
    use_same_profile = (user_profile_url == style_profile_url)
    
    if use_same_profile:
        system_prompt = (
            "You are an automation agent for a LinkedIn content tool. "
            "The user profile and style profile are the same, so you only need to scrape once. "
            "You must perform the following steps using the provided tools. "
            "First, scrape the user profile to get posts (only once since it's the same profile). "
            "Second, extract recurring interest phrases from the user posts. "
            "Third, infer writing style from the same user posts (use the same posts from step 1). "
            "Fourth, fetch Firecrawl trends using the interest phrases and no specific topic. "
            "When you have completed all steps, reply with a single JSON object only, "
            "with this exact structure: "
            "{"
            '"json_url": "<string with the user profile scrape json url>", '
            '"keywords": ["list", "of", "interest phrases"], '
            '"style_notes": "<string with style description>", '
            '"trends": [<array of trend objects exactly as returned by fetch_trends_firecrawl_tool>]'
            "}. "
            "Do not add explanations or extra text outside the JSON."
        )
    else:
        system_prompt = (
            "You are an automation agent for a LinkedIn content tool. "
            "You must perform the following steps using the provided tools. "
            "First, scrape the user profile to get posts. "
            "Second, extract recurring interest phrases from the user posts. "
            "Third, scrape the style profile to get posts. "
            "Fourth, infer writing style from the style profile posts. "
            "Fifth, fetch Firecrawl trends using the interest phrases and no specific topic. "
            "When you have completed all steps, reply with a single JSON object only, "
            "with this exact structure: "
            "{"
            '"json_url": "<string with the user profile scrape json url>", '
            '"keywords": ["list", "of", "interest phrases"], '
            '"style_notes": "<string with style description>", '
            '"trends": [<array of trend objects exactly as returned by fetch_trends_firecrawl_tool>]'
            "}. "
            "Do not add explanations or extra text outside the JSON."
        )

    user_payload = {
        "phantom_api_key": phantom_api_key,
        "firecrawl_api_key": firecrawl_api_key,
        "openai_api_key": openai_api_key,
        "session_cookie": session_cookie,
        "user_agent": user_agent,
        "user_profile_url": user_profile_url,
        "style_profile_url": style_profile_url,
    }

    functions_schema = make_functions_schema()

    history: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload)},
    ]
    last_tool_result: Optional[Dict[str, Any]] = None
    max_steps = 10

    for step in range(max_steps):
        if debug:
            print(f"[AGENT] step {step + 1}")

        resp = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            messages=history,
            functions=functions_schema,
            function_call="auto",
            temperature=0.2,
        )

        msg = resp.choices[0].message

        # Check for function_call (matching original open_linkedin.py)
        if msg.function_call:
            fn = msg.function_call
            name = fn.name
            try:
                args = json.loads(fn.arguments or "{}")
            except Exception:
                args = {}

            if debug:
                print(f"[AGENT] function call: {name}, args: {args}")
            
            tool_result = call_tool_by_name(name, args)
            last_tool_result = tool_result

            history.append({
                "role": "assistant",
                "content": None,
                "function_call": {"name": name, "arguments": json.dumps(args)},
            })
            history.append({
                "role": "function",
                "name": name,
                "content": json.dumps(tool_result),
            })
            continue

        # Final response
        content = msg.content or ""
        if debug:
            print(f"[AGENT] final text: {content[:400]}")

        try:
            result = json.loads(content)
            if isinstance(result, dict):
                result["tool_result"] = last_tool_result
                result["success"] = True
                return result
        except Exception:
            pass

        return {
            "success": False,
            "raw_message": content,
            "tool_result": last_tool_result,
            "error": "Could not parse final JSON response"
        }

    return {
        "success": False,
        "error": "Reached max steps without a final answer.",
        "tool_result": last_tool_result,
    }

