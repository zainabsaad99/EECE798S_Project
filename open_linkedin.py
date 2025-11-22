"""
One page LinkedIn Content Agent with OpenAI function calling tools

Flow
1. User enters keys and required inputs in one form
2. User uploads Google service account json
3. Click Run Agent
   The backend does the following through an agent:
   scrape_user_profile -> extract interest phrases
   scrape_other_profile -> infer writing style
   fetch trends for the user domain using Firecrawl search
4. The UI shows five phrase level trend suggestions and a free text topic input
5. Click Generate Post to create a LinkedIn post in the inferred style
   If a manual topic is given, the backend can use Firecrawl again to refine topic trends
6. Optional Save to Google Sheets and Autopost with PhantomBuster

Requirements
Python 3.10+
pip install requests gradio pydantic gspread google-auth openai pillow firecrawl
"""

from __future__ import annotations

import os
import re
import io
import json
import time
import shutil
import tempfile
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple

import requests
import gradio as gr
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


# ======================================================================
# Constants and configuration
# ======================================================================

PHANTOM_LAUNCH_URL = "https://api.phantombuster.com/api/v2/agents/launch"
PHANTOM_FETCH_OUTPUT_URL = "https://api.phantombuster.com/api/v2/containers/fetch-output"

SCRAPE_AGENT_ID = "6779421181804593"  # LinkedIn Activities Scraper
POST_AGENT_ID = "5247540140692981"    # LinkedIn Auto Poster

DEFAULT_POLL_SECONDS = 5
DEFAULT_MAX_WAIT_SECONDS = 180

# Use a GPT 4 family model
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


# ======================================================================
# Data structures
# ======================================================================

@dataclass
class PostItem:
    """
    Representation of a single LinkedIn post entry as returned by PhantomBuster.
    Only the fields that we care about are included here.
    """
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
    """
    Simple structure to hold a single trend phrase.
    The title is the full phrase.
    The url is optional and points to one relevant source if available.
    """
    title: str
    url: str
    source: Optional[str] = None


# ======================================================================
# HTTP utilities
# ======================================================================

def _http_post_json(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout: int = 60,
    debug: bool = True,
) -> Dict[str, Any]:
    if debug:
        print("[HTTP POST] url:", url)
        print(
            "[HTTP POST] headers:",
            {k: ("***" if "key" in k.lower() else v) for k, v in headers.items()},
        )
        try:
            preview = json.dumps(payload)[:1000]
        except Exception:
            preview = str(payload)[:1000]
        print("[HTTP POST] payload preview:", preview)

    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if debug:
        print("[HTTP POST] status:", r.status_code)
        print("[HTTP POST] response preview:", r.text[:1000].replace("\n", "\\n"))

    r.raise_for_status()
    return r.json()


def _http_get_text(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    debug: bool = True,
) -> str:
    if debug:
        print("[HTTP GET] url:", url)
        if headers:
            print(
                "[HTTP GET] headers:",
                {k: ("***" if "key" in k.lower() else v) for k, v in headers.items()},
            )

    r = requests.get(url, headers=headers, timeout=timeout)
    if debug:
        print("[HTTP GET] status:", r.status_code)
        print("[HTTP GET] response preview:", r.text[:1000].replace("\n", "\\n"))

    r.raise_for_status()
    return r.text


def _http_get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    debug: bool = True,
) -> Dict[str, Any]:
    if debug:
        print("[HTTP GET JSON] url:", url)
        if headers:
            print(
                "[HTTP GET JSON] headers:",
                {k: ("***" if "key" in k.lower() else v) for k, v in headers.items()},
            )
        if params:
            try:
                params_preview = json.dumps(params)[:1000]
            except Exception:
                params_preview = str(params)[:1000]
            print("[HTTP GET JSON] params preview:", params_preview)

    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    if debug:
        print("[HTTP GET JSON] status:", r.status_code)
        print("[HTTP GET JSON] response preview:", r.text[:1000].replace("\n", "\\n"))

    r.raise_for_status()
    return r.json()


# ======================================================================
# PhantomBuster scraping and autopost functions
# ======================================================================

def launch_linkedin_scrape(
    phantom_api_key: str,
    session_cookie: str,
    user_agent: str,
    profile_url: str,
    number_of_lines_per_launch: int = 1,
    number_max_posts: int = 20,
    csv_name: str = "result",
    debug: bool = True,
) -> str:
    if debug:
        print("[SCRAPE LAUNCH] profile_url:", profile_url)

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

    if debug:
        print("[SCRAPE LAUNCH] container_id:", container_id)

    if not container_id:
        raise RuntimeError("No container id returned by PhantomBuster")

    return container_id


def fetch_container_output_for_json_url(
    phantom_api_key: str,
    container_id: str,
    poll_seconds: int = DEFAULT_POLL_SECONDS,
    max_wait_seconds: int = DEFAULT_MAX_WAIT_SECONDS,
    debug: bool = True,
) -> str:
    if debug:
        print("[FETCH OUTPUT] container_id:", container_id)

    headers = {"x-phantombuster-key": phantom_api_key}
    deadline = time.time() + max_wait_seconds

    primary_pat = re.compile(
        r"JSON saved at\s+(https?://\S+?)\s+result\.json",
        re.IGNORECASE,
    )
    fallback_pat = re.compile(
        r"(https?://\S*?result\.json)",
        re.IGNORECASE,
    )

    found_url = None

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

        if debug:
            print("[FETCH OUTPUT] result url not found yet, sleeping", poll_seconds)

        time.sleep(poll_seconds)

    if not found_url:
        raise TimeoutError("Could not locate result.json url in PhantomBuster output")

    if debug:
        print("[FETCH OUTPUT] result json url:", found_url)

    return found_url


def download_posts_json(json_url: str, debug: bool = True) -> List[PostItem]:
    if debug:
        print("[DOWNLOAD POSTS] json_url:", json_url)

    r = requests.get(json_url, timeout=60)

    if debug:
        print("[DOWNLOAD POSTS] status:", r.status_code)

    r.raise_for_status()
    arr = r.json()

    posts: List[PostItem] = []

    if isinstance(arr, list):
        for x in arr:
            item_data = {k: x.get(k) for k in PostItem.__annotations__.keys()}
            posts.append(PostItem(**item_data))

    if debug:
        print("[DOWNLOAD POSTS] total posts:", len(posts))

    return posts


def trigger_phantombuster_autopost(
    phantom_api_key: str,
    session_cookie: str,
    user_agent: str,
    sheet_url: str,
    number_of_posts_per_launch: int = 1,
    debug: bool = True,
) -> Dict[str, Any]:
    if debug:
        print("[AUTOPOST] sheet_url:", sheet_url)

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


# ======================================================================
# OpenAI helpers
# ======================================================================

def summarize_image_with_openai(
    image_url: str,
    openai_api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    debug: bool = True,
) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")

    client = OpenAI(api_key=openai_api_key)

    content = [
        {"type": "text", "text": "Summarize this LinkedIn image post in two sentences. No hashtags."},
        {"type": "image_url", "image_url": {"url": image_url}},
    ]

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )

    summary = resp.choices[0].message.content.strip()

    if debug:
        print("[OPENAI IMG] summary:", summary)

    return summary


def extract_common_interests(
    posts: List[PostItem],
    openai_api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    max_image_summaries: int = 5,
    debug: bool = True,
) -> List[str]:
    """
    Now extracts multi word interest phrases rather than single keywords.
    """
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
                summary = summarize_image_with_openai(
                    image_url=p.imgUrl,
                    openai_api_key=openai_api_key,
                    model=model,
                    debug=debug,
                )
                texts.append(summary)
                image_summaries += 1
            except Exception as e:
                if debug:
                    print("[OPENAI IMG] error for image summary:", e)

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
        print("[OPENAI KW] raw:", raw_clean)

    try:
        arr = json.loads(raw_clean)
        if isinstance(arr, list):
            return [str(x).strip().lower() for x in arr if str(x).strip()]
    except Exception as e:
        if debug:
            print("[OPENAI KW] parse error:", e)

    return [w.strip().lower() for w in raw.split("\n") if w.strip()][:12]


def infer_writing_style_from_posts(
    posts: List[PostItem],
    openai_api_key: str,
    model: str = DEFAULT_OPENAI_MODEL,
    debug: bool = True,
) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")

    client = OpenAI(api_key=openai_api_key)

    sample = "\n\n".join([p.postContent or "" for p in posts])[:15000]

    sys_prompt = (
        "You will receive multiple LinkedIn posts from one profile. "
        "Summarize the writing style in six to ten bullet style points. "
        "Cover tone, sentence length, structure, vocabulary, use of emojis, "
        "use of hashtags, and type of calls to action. "
        "Keep the description precise and actionable."
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
        print("[STYLE] notes:", notes[:400])

    return notes


def generate_linkedin_post(
    openai_key: str,
    topic: str,
    style_notes: Optional[str],
    keywords: List[str],
    model: str = DEFAULT_OPENAI_MODEL,
    debug: bool = True,
) -> str:
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
        print("[GEN POST] length:", len(post_text))
        print("[GEN POST] preview:", post_text[:300].replace("\n", " "))

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


# ======================================================================
# Firecrawl based trend fetching
# ======================================================================

def fetch_trends_firecrawl(
    firecrawl_api_key: str,
    openai_api_key: str,
    keywords: Optional[List[str]] = None,
    topic: Optional[str] = None,
    max_web_items: int = 10,
    max_news_items: int = 10,
    debug: bool = True,
) -> List[TrendItem]:

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
        print("[FIRECRAWL] query:", query_text)

    firecrawl_client = Firecrawl(api_key=firecrawl_api_key)
    result = firecrawl_client.search(query=query_text,
                                     limit=max_web_items + max_news_items)

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
                print("[SUMMARY ERROR]", e)
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
        print("[FIRECRAWL] combined summary length:", len(combined_text))

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

    trend_items = [
        TrendItem(title=phrase, url=first_url, source="firecrawl")
        for phrase in phrases
    ]

    return trend_items


# ======================================================================
# Google Sheets save helper
# ======================================================================

def save_post_to_google_sheet(
    sheet_url: str,
    content: str,
    service_account_json_path: str,
    debug: bool = True,
) -> Tuple[str, int]:
    if gspread is None or Credentials is None:
        raise RuntimeError("gspread or google auth is not installed")

    if debug:
        print("[GSHEETS] save content length:", len(content))

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(
        service_account_json_path,
        scopes=scopes,
    )

    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    ws = sh.sheet1

    ws.append_row([content], value_input_option="RAW")

    if debug:
        print("[GSHEETS] append done", ws.id, ws.row_count)

    return (ws.id, ws.row_count)


# ======================================================================
# Tool schemas for function calling
# ======================================================================

def make_functions_schema() -> List[Dict[str, Any]]:
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
                "required": [
                    "phantom_api_key",
                    "session_cookie",
                    "user_agent",
                    "profile_url",
                ],
            },
        },
        {
            "name": "extract_keywords_tool",
            "description": "Extract recurring interest phrases from posts content and image summaries using OpenAI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openai_api_key": {"type": "string"},
                    "posts": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
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
                    "posts": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
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
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "topic": {"type": "string"},
                },
                "required": ["firecrawl_api_key", "openai_api_key", "keywords"],
            },
        },
        {
            "name": "generate_post_tool",
            "description": "Generate a LinkedIn post in a specified style using OpenAI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openai_api_key": {"type": "string"},
                    "topic": {"type": "string"},
                    "style_notes": {"type": "string"},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                },
                "required": [
                    "openai_api_key",
                    "topic",
                    "style_notes",
                    "keywords",
                ],
            },
        },
        {
            "name": "save_to_sheet_tool",
            "description": "Save a LinkedIn post to a Google Sheet using a service account json file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_url": {"type": "string"},
                    "content": {"type": "string"},
                    "service_account_json_path": {"type": "string"},
                },
                "required": [
                    "sheet_url",
                    "content",
                    "service_account_json_path",
                ],
            },
        },
        {
            "name": "autopost_tool",
            "description": "Trigger PhantomBuster autoposter to publish from a Google Sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phantom_api_key": {"type": "string"},
                    "session_cookie": {"type": "string"},
                    "user_agent": {"type": "string"},
                    "sheet_url": {"type": "string"},
                },
                "required": [
                    "phantom_api_key",
                    "session_cookie",
                    "user_agent",
                    "sheet_url",
                ],
            },
        },
    ]


# ======================================================================
# Tool implementations
# ======================================================================

def scrape_profile_tool(
    phantom_api_key: str,
    session_cookie: str,
    user_agent: str,
    profile_url: str,
) -> Dict[str, Any]:
    container_id = launch_linkedin_scrape(
        phantom_api_key=phantom_api_key,
        session_cookie=session_cookie,
        user_agent=user_agent,
        profile_url=profile_url,
    )

    json_url = fetch_container_output_for_json_url(
        phantom_api_key=phantom_api_key,
        container_id=container_id,
    )

    posts = download_posts_json(json_url)

    return {
        "json_url": json_url,
        "posts": [p.__dict__ for p in posts],
    }


def extract_keywords_tool(
    openai_api_key: str,
    posts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    post_objs = [
        PostItem(**{k: d.get(k) for k in PostItem.__annotations__.keys()})
        for d in posts
    ]

    keywords = extract_common_interests(post_objs, openai_api_key=openai_api_key)

    return {"keywords": keywords}


def infer_style_tool(
    openai_api_key: str,
    posts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    post_objs = [
        PostItem(**{k: d.get(k) for k in PostItem.__annotations__.keys()})
        for d in posts
    ]

    style = infer_writing_style_from_posts(
        post_objs,
        openai_api_key=openai_api_key,
    )

    return {"style_notes": style}


def fetch_trends_firecrawl_tool(
    firecrawl_api_key: str,
    openai_api_key: str,
    keywords: List[str],
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    items = fetch_trends_firecrawl(
        firecrawl_api_key=firecrawl_api_key,
        openai_api_key=openai_api_key,
        keywords=keywords,
        topic=topic,
    )

    return {"trends": [item.model_dump() for item in items]}


def generate_post_tool(
    openai_api_key: str,
    topic: str,
    style_notes: str,
    keywords: List[str],
) -> Dict[str, Any]:
    post = generate_linkedin_post(
        openai_key=openai_api_key,
        topic=topic,
        style_notes=style_notes,
        keywords=keywords,
    )

    return {"post": post}


def save_to_sheet_tool(
    sheet_url: str,
    content: str,
    service_account_json_path: str,
) -> Dict[str, Any]:
    ws_id, row_count = save_post_to_google_sheet(
        sheet_url=sheet_url,
        content=content,
        service_account_json_path=service_account_json_path,
    )

    return {"worksheet_id": ws_id, "row_count": row_count}


def autopost_tool(
    phantom_api_key: str,
    session_cookie: str,
    user_agent: str,
    sheet_url: str,
) -> Dict[str, Any]:
    resp = trigger_phantombuster_autopost(
        phantom_api_key=phantom_api_key,
        session_cookie=session_cookie,
        user_agent=user_agent,
        sheet_url=sheet_url,
    )

    return {"autopost_response": resp}


def call_tool_by_name(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    print("[DISPATCH] tool:", name)

    try:
        if name == "scrape_profile_tool":
            return scrape_profile_tool(**args)
        if name == "extract_keywords_tool":
            return extract_keywords_tool(**args)
        if name == "infer_style_tool":
            return infer_style_tool(**args)
        if name == "fetch_trends_firecrawl_tool":
            return fetch_trends_firecrawl_tool(**args)
        if name == "generate_post_tool":
            return generate_post_tool(**args)
        if name == "save_to_sheet_tool":
            return save_to_sheet_tool(**args)
        if name == "autopost_tool":
            return autopost_tool(**args)
    except Exception as e:
        print("[DISPATCH] tool error:", e)
        return {"error": str(e)}

    return {"error": f"unknown tool {name}"}


# ======================================================================
# Agent loop using function calling
# ======================================================================

def run_agent_sequence(
    openai_api_key: str,
    system_prompt: str,
    user_payload: Dict[str, Any],
    functions_schema: List[Dict[str, Any]],
    max_steps: int = 10,
) -> Dict[str, Any]:
    """
    Agent loop that uses function calling.
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

    history: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(user_payload),
        },
    ]
    last_tool_result: Optional[Dict[str, Any]] = None

    for step in range(max_steps):
        print(f"[AGENT] step {step + 1}")

        resp = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            messages=history,
            functions=functions_schema,
            function_call="auto",
            temperature=0.2,
        )

        msg = resp.choices[0].message

        if msg.function_call:
            fn = msg.function_call
            name = fn.name
            try:
                args = json.loads(fn.arguments or "{}")
            except Exception:
                args = {}

            print("[AGENT] function call:", name, "args:", args)
            tool_result = call_tool_by_name(name, args)
            last_tool_result = tool_result

            history.append(
                {
                    "role": "assistant",
                    "content": None,
                    "function_call": {"name": name, "arguments": json.dumps(args)},
                }
            )
            history.append(
                {
                    "role": "function",
                    "name": name,
                    "content": json.dumps(tool_result),
                }
            )

            continue

        content = msg.content or ""
        print("[AGENT] final text:", content[:400])

        try:
            result = json.loads(content)
            if isinstance(result, dict):
                result["tool_result"] = last_tool_result
                return result
        except Exception:
            pass

        return {
            "raw_message": content,
            "tool_result": last_tool_result,
        }

    return {
        "error": "Reached max steps without a final answer.",
        "tool_result": last_tool_result,
    }


# ======================================================================
# Gradio user interface
# ======================================================================

with gr.Blocks(title="LinkedIn Content Agent") as demo:
    gr.Markdown("## LinkedIn Content Agent")

    with gr.Column():
        gr.Markdown(
            "Enter your keys and inputs, upload a Google service account json, then click Run Agent."
        )

        with gr.Row():
            openai_key_in = gr.Textbox(
                label="OpenAI API Key",
                type="password",
            )
            phantom_key_in = gr.Textbox(
                label="PhantomBuster API Key",
                type="password",
            )
            firecrawl_key_in = gr.Textbox(
                label="Firecrawl API Key for trends",
                type="password",
            )

        with gr.Row():
            session_cookie_in = gr.Textbox(
                label="LinkedIn session cookie",
                type="password",
            )
            user_agent_in = gr.Textbox(
                label="Browser User Agent",
            )

        with gr.Row():
            user_profile_url_in = gr.Textbox(
                label="Your LinkedIn profile url for scraping interests",
            )
            style_profile_url_in = gr.Textbox(
                label="Another LinkedIn profile url for style inference",
            )

        with gr.Row():
            sheet_url_in = gr.Textbox(
                label="Google Sheet url for saving and autopost",
            )
            sa_json_file_in = gr.File(
                label="Upload Google service account json",
            )

        run_btn = gr.Button("Run Agent")

    status_out = gr.Markdown()
    json_url_out = gr.Textbox(
        label="Scrape result json url",
        interactive=False,
    )
    keywords_out = gr.JSON(
        label="Extracted user interest phrases",
    )
    style_out = gr.Textbox(
        label="Inferred writing style notes",
        lines=10,
    )
    trends_out = gr.JSON(
        label="Trend suggestions from Firecrawl (phrase level)",
    )

    gr.Markdown("Choose a trend or type a topic.")
    with gr.Row():
        topic_choice_in = gr.Dropdown(
            choices=[],
            label="Pick a suggested trend phrase",
            interactive=True,
        )
        topic_manual_in = gr.Textbox(
            label="Or type a custom topic to refine trends and generate a post",
        )

    gen_btn = gr.Button("Generate LinkedIn Post")
    post_out = gr.Textbox(
        label="Post draft",
        lines=14,
    )

    with gr.Row():
        do_save_chk = gr.Checkbox(
            label="Save to Google Sheet",
            value=True,
        )
        do_autopost_chk = gr.Checkbox(
            label="Autopost with PhantomBuster",
            value=False,
        )

    submit_btn = gr.Button("Save and possibly Autopost")
    saved_out = gr.Textbox(
        label="Save information",
    )
    autopost_out = gr.JSON(
        label="Autopost response",
    )

    state_all = gr.State(value={})

    # ------------------------------------------------------------------
    # Callback for Run Agent (agentic flow)
    # ------------------------------------------------------------------

    def on_run_agent(
        openai_key,
        phantom_key,
        firecrawl_key,
        session_cookie,
        user_agent,
        user_profile_url,
        style_profile_url,
        sheet_url,
        sa_file,
    ):
        logs: List[str] = []

        def log(x: str):
            print(x)
            logs.append(x)

        missing = []
        if not openai_key:
            missing.append("OpenAI API Key")
        if not phantom_key:
            missing.append("PhantomBuster API Key")
        if not firecrawl_key:
            missing.append("Firecrawl API Key")
        if not session_cookie:
            missing.append("LinkedIn session cookie")
        if not user_agent:
            missing.append("User Agent")
        if not user_profile_url:
            missing.append("Your LinkedIn profile url")
        if not style_profile_url:
            missing.append("Style LinkedIn profile url")

        if missing:
            return (
                f"Missing required fields: {', '.join(missing)}",
                "",
                None,
                "",
                None,
                gr.update(choices=[]),
                {},
            )

        sa_path = None
        if sa_file is not None:
            try:
                tmpdir = tempfile.mkdtemp(prefix="sajson_")
                sa_path = os.path.join(tmpdir, os.path.basename(sa_file.name))
                shutil.copy(sa_file.name, sa_path)
                log("Service account json saved to a temporary path.")
            except Exception as e:
                log(f"Could not stage service account json: {e}")

        try:
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
                "phantom_api_key": phantom_key,
                "firecrawl_api_key": firecrawl_key,
                "openai_api_key": openai_key,
                "session_cookie": session_cookie,
                "user_agent": user_agent,
                "user_profile_url": user_profile_url,
                "style_profile_url": style_profile_url,
            }

            functions_schema = make_functions_schema()

            agent_result = run_agent_sequence(
                openai_api_key=openai_key,
                system_prompt=system_prompt,
                user_payload=user_payload,
                functions_schema=functions_schema,
            )

            if "error" in agent_result and not agent_result.get("json_url"):
                log(f"Agent error: {agent_result['error']}")
                return (
                    f"Error while running agent: {agent_result['error']}",
                    "",
                    None,
                    "",
                    None,
                    gr.update(choices=[]),
                    {},
                )

            json_url = agent_result.get("json_url", "") or ""
            keywords = agent_result.get("keywords", []) or []
            style_notes = agent_result.get("style_notes", "") or ""
            trends = agent_result.get("trends", []) or []

            trend_titles = [t.get("title", "") for t in trends if isinstance(t, dict) and t.get("title")]

            log(f"Agent json_url: {json_url}")
            log(f"Keywords: {keywords}")
            log(f"Trend phrases fetched: {len(trends)}")

            st = {
                "openai_key": openai_key,
                "phantom_key": phantom_key,
                "firecrawl_key": firecrawl_key,
                "session_cookie": session_cookie,
                "user_agent": user_agent,
                "sheet_url": sheet_url or "",
                "sa_path": sa_path,
                "keywords": keywords,
                "style_notes": style_notes,
                "trends": trends,
                "json_url": json_url,
            }

            status_text = (
                "Agent finished scraping and analysis. "
                "You can now pick one of the suggested trend phrases or type your own topic."
            )

            return (
                status_text,
                json_url,
                keywords,
                style_notes,
                trends,
                gr.update(choices=trend_titles),
                st,
            )

        except Exception as e:
            log(f"Agent error: {e}")
            return (
                f"Error while running agent: {e}",
                "",
                None,
                "",
                None,
                gr.update(choices=[]),
                {},
            )

    # ------------------------------------------------------------------
    # Callback for Generate LinkedIn Post
    # ------------------------------------------------------------------

    def on_generate_post(state, picked_title, manual_topic):
        if not state or not state.get("openai_key"):
            return "Please run the agent first to populate interests, style, and trends."

        topic = None
        refined_trends = None

        manual_topic = (manual_topic or "").strip()
        picked_title = (picked_title or "").strip()

        if manual_topic:
            openai_key = state["openai_key"]
            firecrawl_key = state.get("firecrawl_key") or ""
            keywords = state.get("keywords") or []

            if firecrawl_key:
                try:
                    res = fetch_trends_firecrawl_tool(
                        firecrawl_api_key=firecrawl_key,
                        openai_api_key=openai_key,
                        keywords=keywords,
                        topic=manual_topic,
                    )
                    refined_trends = res.get("trends", []) or []
                except Exception as e:
                    print("[GENERATE] Firecrawl topic trends error:", e)

            if refined_trends:
                first_phrase = refined_trends[0].get("title") or ""
                topic = first_phrase or manual_topic
            else:
                topic = manual_topic
        else:
            topic = picked_title

        if not topic:
            return "Please pick a suggested trend or type a custom topic first."

        openai_key = state["openai_key"]
        style_notes = state.get("style_notes") or ""
        keywords = state.get("keywords") or []

        print("[GENERATE] final topic:", topic)
        print("[GENERATE] keywords (ignored for generation):", keywords[:12])

        post = generate_linkedin_post(
            openai_key=openai_key,
            topic=topic,
            style_notes=style_notes,
            keywords=[],
        )

        state["current_post"] = post
        if refined_trends is not None:
            state["topic_trends"] = refined_trends

        return post

    # ------------------------------------------------------------------
    # Callback for Save and possibly Autopost
    # ------------------------------------------------------------------

    def on_submit(state, do_save, do_autopost):
        if not state:
            return "State is empty. Please run the agent and generate a post first.", None

        post = state.get("current_post")
        if not post:
            return "No post has been generated yet. Please generate a post first.", None

        saved_info = "Not saved."
        try:
            if do_save and state.get("sheet_url") and state.get("sa_path"):
                ws_id, row_count = save_post_to_google_sheet(
                    sheet_url=state["sheet_url"],
                    content=post,
                    service_account_json_path=state["sa_path"],
                )
                saved_info = (
                    f"Post saved to sheet. Worksheet id {ws_id}, current row count {row_count}."
                )
        except Exception as e:
            saved_info = f"Save to sheet failed: {e}"

        autopost_resp = None
        try:
            if (
                do_autopost
                and state.get("phantom_key")
                and state.get("session_cookie")
                and state.get("user_agent")
                and state.get("sheet_url")
            ):
                autopost_resp = trigger_phantombuster_autopost(
                    phantom_api_key=state["phantom_key"],
                    session_cookie=state["session_cookie"],
                    user_agent=state["user_agent"],
                    sheet_url=state["sheet_url"],
                )
        except Exception as e:
            autopost_resp = {"error": str(e)}

        return saved_info, autopost_resp

    # Wire callbacks

    run_btn.click(
        on_run_agent,
        inputs=[
            openai_key_in,
            phantom_key_in,
            firecrawl_key_in,
            session_cookie_in,
            user_agent_in,
            user_profile_url_in,
            style_profile_url_in,
            sheet_url_in,
            sa_json_file_in,
        ],
        outputs=[
            status_out,
            json_url_out,
            keywords_out,
            style_out,
            trends_out,
            topic_choice_in,
            state_all,
        ],
    )

    gen_btn.click(
        on_generate_post,
        inputs=[state_all, topic_choice_in, topic_manual_in],
        outputs=[post_out],
    )

    submit_btn.click(
        on_submit,
        inputs=[state_all, do_save_chk, do_autopost_chk],
        outputs=[saved_out, autopost_out],
    )


if __name__ == "__main__":
    print("[MAIN] launching Gradio UI")
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        share=True,
    )
