"""
Content generation helpers powered by OpenAI.
Creates platform-specific post plans and companion image data.
"""

from __future__ import annotations

import base64
import json
import os
import time
from io import BytesIO
from typing import Any, Dict, List, Optional

from openai import OpenAI
from PIL import Image

SUPPORTED_PLATFORMS = ["linkedin", "instagram_feed", "instagram_story", "twitter", "tiktok"]
DEFAULT_TEXT_MODEL = os.getenv("OPENAI_CONTENT_MODEL", "gpt-4.1-mini")
DEFAULT_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
DEFAULT_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024")
DEFAULT_VIDEO_MODEL = os.getenv("OPENAI_VIDEO_MODEL", "sora-2")

def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

DEFAULT_LOGO_POSITION = os.getenv("OPENAI_LOGO_POSITION", "bottom-right")
DEFAULT_LOGO_SCALE = _env_float("OPENAI_LOGO_SCALE", 0.18)

# Default image sizing per channel (falls back to DEFAULT_IMAGE_SIZE)
PLATFORM_IMAGE_SIZES = {
    "linkedin": os.getenv("OPENAI_IMAGE_SIZE_LINKEDIN", "1024x1024"),
    "instagram_feed": os.getenv("OPENAI_IMAGE_SIZE_INSTAGRAM_FEED", "1024x1024"),
    "instagram_story": os.getenv("OPENAI_IMAGE_SIZE_INSTAGRAM_STORY", "1024x1792"),
    "twitter": os.getenv("OPENAI_IMAGE_SIZE_TWITTER", "1024x576"),
    "tiktok": os.getenv("OPENAI_IMAGE_SIZE_TIKTOK", "1024x1792"),
}

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured in the backend environment.")
        _client = OpenAI(api_key=api_key)
    return _client


def generate_social_plan(
    brand_summary: str,
    campaign_goal: str,
    target_audience: str,
    platforms: List[str],
    num_posts_per_platform: int = 3,
    extra_instructions: str = "",
    model: str = DEFAULT_TEXT_MODEL,
) -> Dict[str, Any]:
    """Generate platform aware posts and matching image prompts."""

    valid_platforms = [p for p in platforms if p in SUPPORTED_PLATFORMS]
    if not valid_platforms:
        raise ValueError(f"No valid platforms provided. Supported platforms: {SUPPORTED_PLATFORMS}")

    system_prompt = """
You are a senior social media strategist and copywriter.

You will be given:
- A brand summary
- A campaign goal
- A target audience
- A list of platforms
- Desired number of posts per platform

Your job:
1. For each platform, create posts that are NATIVELY formatted for that platform.
2. For each post, also create an IMAGE PROMPT that a text-to-image model can use.

Platform guidelines:
- linkedin
  * Tone: professional, value-packed, thought leadership, story-driven.
  * Format: short paragraphs, optional bullets, no hashtags overload (0–3).

- instagram_feed
  * Tone: emotional + aspirational.
  * Format: hook in first line, then 1–3 short paragraphs, 3–8 hashtags.
  * Image style: visually striking, lifestyle or product-focused.
  * Include 5–12 hashtags at the END of the caption.

- instagram_story
  * Tone: very short, punchy, CTA-driven.
  * Format: 1–3 short text screens (describe them), clear CTA.
  * Image style: bold typography, minimal text, strong contrast.

- twitter
  * Tone: concise, punchy, sometimes contrarian.
  * Format: 1–2 tweets per post concept (thread allowed), max ~240 chars each.
  * Hashtags: 0–3 max.

- tiktok
  * Tone: casual, fun, behind-the-scenes, educational hooks.
  * Format: script-style with:
        - HOOK (first 3 seconds)
        - BODY (what to show/say)
        - CTA
  * Image prompt should describe the key scene or thumbnail.
  * Use 3–6 hashtags.

CRITICAL:
- Do NOT invent specific numbers (e.g., “500% ROI”) unless user provided them.
- Do NOT claim certifications, awards, or partnerships that weren't given.
- Posts should align with the brand’s personality inferred from the brief.
- Image prompts must be concrete, visual descriptions (no abstract marketing jargon).

Return only valid JSON with the structure:
{
  "platforms": [
    {
      "name": "linkedin",
      "posts": [
        {
          "text": "...",
          "image_prompt": "...",
          "notes": "optional helper note"
        }
      ]
    }
  ]
}
""".strip()

    user_payload = {
        "brand_summary": brand_summary,
        "campaign_goal": campaign_goal,
        "target_audience": target_audience,
        "platforms": valid_platforms,
        "num_posts_per_platform": num_posts_per_platform,
        "extra_instructions": extra_instructions,
    }

    client = _get_client()
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Generate social posts and image prompts in JSON only. "
                    "Here is the campaign brief:\n"
                    + json.dumps(user_payload, ensure_ascii=False, indent=2)
                ),
            },
        ],
        response_format={"type": "json_object"},
    )

    data = json.loads(completion.choices[0].message.content)
    return data


def generate_image_with_gpt(
    prompt: str,
    size: str = DEFAULT_IMAGE_SIZE,
    model: str = DEFAULT_IMAGE_MODEL,
    base_image_bytes: Optional[bytes] = None,
    base_image_name: Optional[str] = None,
) -> str:
    """Generate or edit an image via OpenAI's image model and return a data URI."""
    client = _get_client()
    if base_image_bytes:
        # When the user supplies a reference asset we use the edit endpoint so GPT-Image
        # can honor both the provided pixels and the new textual guidance.
        image_buffer = BytesIO(base_image_bytes)
        image_buffer.name = base_image_name or "reference.png"
        result = client.images.edit(
            model=model,
            prompt=prompt,
            image=image_buffer,
            size=size,
        )
    else:
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
        )
    b64_data = result.data[0].b64_json
    return f"data:image/png;base64,{b64_data}"


def generate_video_with_sora(prompt: str, model: str = DEFAULT_VIDEO_MODEL, max_duration: int = 4) -> str:
    """Generate a video via OpenAI's Sora model and return a data URI.
    
    Args:
        prompt: Text prompt for video generation
        model: Sora model name (default: sora-2)
        max_duration: Maximum video duration in seconds (default: 4)
    """
    client = _get_client()
    
    # Create video generation request
    video = client.videos.create(
        model=model,
        prompt=prompt,
        max_duration=max_duration,  # Maximum duration in seconds (typically 4 for Sora)
    )
    
    # Poll for completion
    while video.status in ("in_progress", "queued"):
        time.sleep(2)  # Wait 2 seconds between checks
        video = client.videos.retrieve(video.id)
        
        if video.status == "failed":
            error_message = getattr(getattr(video, "error", None), "message", "Video generation failed")
            raise RuntimeError(f"Video generation failed: {error_message}")
    
    if video.status != "completed":
        raise RuntimeError(f"Video generation ended with status: {video.status}")
    
    # Download video content
    video_content = client.videos.download_content(video.id, variant="video")
    video_bytes = video_content.read()
    
    # Convert to base64 data URI
    b64_data = base64.b64encode(video_bytes).decode("utf-8")
    return f"data:video/mp4;base64,{b64_data}"


def overlay_logo_on_image(
    image_data_uri: str,
    logo_bytes: bytes,
    position: str = DEFAULT_LOGO_POSITION,
    scale: float = DEFAULT_LOGO_SCALE,
) -> str:
    """Paste the uploaded logo onto the generated base image and return data URI."""
    if not image_data_uri or not logo_bytes:
        return image_data_uri
    try:
        header, b64_data = image_data_uri.split(",", 1)
    except ValueError:
        return image_data_uri

    base_image = Image.open(BytesIO(base64.b64decode(b64_data))).convert("RGBA")
    logo_image = Image.open(BytesIO(logo_bytes)).convert("RGBA")

    scale = max(0.05, min(scale, 0.5))
    target_width = max(1, int(base_image.width * scale))
    aspect = logo_image.height / float(logo_image.width or 1)
    target_height = max(1, int(target_width * aspect))
    logo_image = logo_image.resize((target_width, target_height), Image.LANCZOS)

    margin = max(4, int(base_image.width * 0.03))
    positions = {
        "top-left": (margin, margin),
        "top-right": (base_image.width - target_width - margin, margin),
        "bottom-left": (margin, base_image.height - target_height - margin),
        "bottom-right": (base_image.width - target_width - margin, base_image.height - target_height - margin),
        "center": ((base_image.width - target_width) // 2, (base_image.height - target_height) // 2),
    }
    px, py = positions.get(position.lower(), positions["bottom-right"])
    px = max(0, min(base_image.width - target_width, px))
    py = max(0, min(base_image.height - target_height, py))

    base_image.paste(logo_image, (px, py), logo_image)
    buffer = BytesIO()
    base_image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def attach_images_to_plan(
    social_plan: Dict[str, Any],
    platform_image_sizes: Optional[Dict[str, str]] = None,
    default_size: str = DEFAULT_IMAGE_SIZE,
    model: str = DEFAULT_IMAGE_MODEL,
    logo_bytes: Optional[bytes] = None,
    logo_position: str = DEFAULT_LOGO_POSITION,
    logo_scale: float = DEFAULT_LOGO_SCALE,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach generated images (as base64 data URIs) to each post."""
    size_map = PLATFORM_IMAGE_SIZES.copy()
    if platform_image_sizes:
        size_map.update({k: v for k, v in platform_image_sizes.items() if isinstance(v, str)})

    for platform in social_plan.get("platforms", []):
        platform_name = platform.get("name", "").lower()
        image_size = size_map.get(platform_name, default_size)
        for post in platform.get("posts", []):
            prompt = post.get("image_prompt")
            if not prompt:
                continue
            try:
                uri = generate_image_with_gpt(prompt, size=image_size, model=model, base_image_bytes=reference_image_bytes, base_image_name=reference_image_name,)
                if logo_bytes:
                    uri = overlay_logo_on_image(uri, logo_bytes, position=logo_position, scale=logo_scale)
                post["image_data_uri"] = uri
                post.pop("image_error", None)
            except Exception as exc:
                post["image_data_uri"] = None
                post["image_error"] = str(exc)
    return social_plan


def attach_videos_to_plan(
    social_plan: Dict[str, Any],
    model: str = DEFAULT_VIDEO_MODEL,
    max_duration: int = 4,
) -> Dict[str, Any]:
    """Attach generated videos (as base64 data URIs) to each post.
    
    Args:
        social_plan: The social media plan with posts
        model: Sora model name (default: sora-2)
        max_duration: Maximum video duration in seconds (default: 4)
    """
    for platform in social_plan.get("platforms", []):
        for post in platform.get("posts", []):
            # Use image_prompt as video prompt, or create a video-specific prompt
            prompt = post.get("image_prompt") or post.get("video_prompt")
            if not prompt:
                # Create a video prompt from the text if no image prompt exists
                text = post.get("text", "")
                if text:
                    prompt = f"Create a dynamic, engaging video reel for: {text[:200]}"
                else:
                    continue
            
            try:
                uri = generate_video_with_sora(prompt, model=model, max_duration=max_duration)
                post["video_data_uri"] = uri
                post.pop("video_error", None)
            except Exception as exc:
                post["video_data_uri"] = None
                post["video_error"] = str(exc)
    return social_plan


def generate_social_content_and_images(
    brand_summary: str,
    campaign_goal: str,
    target_audience: str,
    platforms: List[str],
    num_posts_per_platform: int = 3,
    extra_instructions: str = "",
    image_size: str = DEFAULT_IMAGE_SIZE,
    platform_image_sizes: Optional[Dict[str, str]] = None,
    logo_bytes: Optional[bytes] = None,
    logo_position: str = DEFAULT_LOGO_POSITION,
    logo_scale: float = DEFAULT_LOGO_SCALE,
    proposal_context: Optional[Dict[str, Any]] = None,
    outputs: Optional[List[str]] = None,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_name: Optional[str] = None,
) -> Dict[str, Any]:
    """High-level helper to create posts and matching visuals."""
    plan = generate_social_plan(
        brand_summary=brand_summary,
        campaign_goal=campaign_goal,
        target_audience=target_audience,
        platforms=platforms,
        num_posts_per_platform=num_posts_per_platform,
        extra_instructions=extra_instructions,
    )
    
    # Check which outputs are requested
    should_generate_images = False
    should_generate_videos = False
    if outputs:
        should_generate_images = any(
            output.lower() in ['poster', 'image', 'images'] 
            for output in outputs
        )
        should_generate_videos = any(
            output.lower() in ['video', 'reel', 'videos', 'reels'] 
            for output in outputs
        )
    
    if should_generate_images:
        plan = attach_images_to_plan(
            plan,
            platform_image_sizes=platform_image_sizes,
            default_size=image_size,
            logo_bytes=logo_bytes,
            logo_position=logo_position,
            logo_scale=logo_scale,
            reference_image_bytes=reference_image_bytes,
            reference_image_name=reference_image_name,
        )
    
    if should_generate_videos:
        plan = attach_videos_to_plan(
            plan,
            model=DEFAULT_VIDEO_MODEL,
            max_duration=4,  # Sora typically supports up to 4 seconds
        )
    
    return plan
