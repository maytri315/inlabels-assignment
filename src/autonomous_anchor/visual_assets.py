from __future__ import annotations

import hashlib
import logging
import time
import textwrap
import random
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from urllib.parse import quote_plus
from typing import Iterable, List

import requests

from .models import StoryVerdict

logger = logging.getLogger(__name__)
WIKIMEDIA_SEARCH_API = "https://commons.wikimedia.org/w/api.php"

# User agent to avoid being blocked
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "image/jpeg,image/png;q=0.9,*/*;q=0.8",
}
HF_INFERENCE_UNAVAILABLE = False
HF_ROUTER_BASE = "https://router.huggingface.co/hf-inference"
HF_LEGACY_BASE = "https://api-inference.huggingface.co"
HF_FALLBACK_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-3-medium-diffusers",
]


def _generate_placeholder_image(target: Path, text: str = "MOCKR") -> Path:
    """Generate a simple placeholder PNG with headline text."""
    try:
        width, height = 720, 1280
        img = Image.new("RGB", (width, height), (12, 14, 18))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 48)
        except Exception:
            font = ImageFont.load_default()

        # Draw centered text
        lines = textwrap.wrap(text or "MOCKR", width=20)
        y = height // 2 - (len(lines) * 26)
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            draw.text(((width - w) // 2, y), line, font=font, fill=(220, 225, 235))
            y += (bbox[3] - bbox[1]) + 12

        target.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(target), format="PNG")
        return target
    except Exception:
        # If generation fails, touch an empty file so later code finds something
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
        return target



def _extract_terms(verdicts: Iterable[StoryVerdict]) -> List[str]:
    terms: List[str] = []
    for verdict in verdicts:
        words = verdict.story.title.split()
        candidate = " ".join(words[:4]).strip()
        if candidate:
            terms.append(candidate)
    if not terms:
        terms.append("India city news")
    return terms


def _build_prompt_context(verdict: StoryVerdict, script_text: str = "") -> str:
    story = verdict.story
    script_excerpt = " ".join(line.strip() for line in script_text.splitlines() if line.strip())
    script_excerpt = script_excerpt[:320]
    evidence_bits = []
    for item in verdict.evidence[:2]:
        snippet = getattr(item, "snippet", "") or ""
        if snippet:
            evidence_bits.append(snippet.strip())
    evidence_text = " ".join(evidence_bits)[:220]

    parts = [
        story.title,
        getattr(story, "summary", "") or "",
        f"category {getattr(story, 'category', 'general')}",
        f"verdict {verdict.verdict}",
        f"truth score {verdict.truth_score}/100",
        verdict.reason or "",
        evidence_text,
        script_excerpt,
    ]
    cleaned = " ".join(part.strip() for part in parts if part and str(part).strip())
    return cleaned[:500]



def _search_wikimedia_image(term: str, max_retries: int = 2) -> str | None:
    """Search Wikimedia Commons for an image matching the term."""
    for attempt in range(max_retries):
        try:
            params = {
                "action": "query",
                "generator": "search",
                "gsrnamespace": 6,
                "gsrsearch": term,
                "gsrlimit": 3,  # Get multiple results in case first ones fail
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
            }
            
            logger.debug(f"Wikimedia search attempt {attempt + 1}/{max_retries} for '{term}'")
            response = requests.get(
                WIKIMEDIA_SEARCH_API, 
                params=params, 
                timeout=20,
                headers=REQUEST_HEADERS
            )
            
            if response.status_code == 429:
                logger.warning(f"Wikimedia rate limited (429), waiting before retry...")
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
                
            response.raise_for_status()
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            
            for page in pages.values():
                infos = page.get("imageinfo", [])
                if infos:
                    url = infos[0].get("url")
                    if url:
                        logger.debug(f"Found Wikimedia image for '{term}': {url[:80]}")
                        return url
                        
            logger.debug(f"No Wikimedia images found for '{term}'")
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"Wikimedia timeout for '{term}' (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.HTTPError as e:
            if "403" in str(e):
                logger.warning(f"Wikimedia blocked (403) - may be rate limiting or blocked IP")
            else:
                logger.warning(f"Wikimedia HTTP error for '{term}': {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"Wikimedia error for '{term}': {type(e).__name__}: {e}")
            return None
            
    return None


def _pollinations_image_url(
    prompt: str,
    width: int = 720,
    height: int = 1280,
    seed_salt: str = "",
    style_hint: str = "",
    base_url: str = "https://image.pollinations.ai",
) -> str:
    style_prefix = (
        "cinematic editorial photograph, modern broadcast design, soft volumetric light, "
        "shallow depth of field, clean composition, rich contrast, realistic textures"
    )
    prompt_text = f"{style_prefix}, {style_hint}, {prompt}, 4k quality, no text, no watermark"
    safe_prompt = quote_plus(prompt_text)
    seed_src = f"{prompt}|{seed_salt}|{style_hint}"
    seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:8], 16)
    return f"{base_url}/prompt/{safe_prompt}?width={width}&height={height}&seed={seed}"


def _hf_sdxl_image(
    prompt: str,
    width: int = 720,
    height: int = 1280,
    model: str = "stabilityai/stable-diffusion-xl-base-1.0",
    hf_api_key: str = "",
    timeout: int = 120,
) -> bytes | None:
    """Request an image from Hugging Face Inference API and return raw image bytes or None."""
    global HF_INFERENCE_UNAVAILABLE
    if not hf_api_key or not model:
        return None

    candidates = []
    for candidate in [model, *HF_FALLBACK_IMAGE_MODELS]:
        cleaned = str(candidate or "").strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    headers = {
        "Authorization": f"Bearer {hf_api_key}",
        "Accept": "image/jpeg",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "width": width,
            "height": height,
        },
        "options": {"wait_for_model": True},
    }

    saw_endpoint_missing = False
    for candidate_model in candidates:
        endpoints = [
            f"{HF_ROUTER_BASE}/models/{candidate_model}",
            f"{HF_LEGACY_BASE}/models/{candidate_model}",
        ]
        for url in endpoints:
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout, stream=True)
                if resp.status_code == 200 and resp.content and len(resp.content) > 1000:
                    content_type = (resp.headers.get("content-type") or "").lower()
                    if content_type and not content_type.startswith("image/"):
                        logger.warning(
                            f"HF returned 200 with non-image content-type {content_type} for model={candidate_model}"
                        )
                        continue
                    if candidate_model != model:
                        logger.info(f"HF image fallback model succeeded: {candidate_model}")
                    return resp.content

                body = ""
                try:
                    body = (resp.text or "")[:240]
                except Exception:
                    body = ""

                # 404 is common on legacy endpoints for unsupported paths; try remaining endpoints/models first.
                if resp.status_code == 404:
                    saw_endpoint_missing = True
                    continue

                # 400/410 usually means the model is unsupported/deprecated on this provider.
                if resp.status_code in {400, 410}:
                    logger.warning(
                        f"HF model unavailable on endpoint (status={resp.status_code}, model={candidate_model}): {body}"
                    )
                    break

                if resp.status_code in {401, 403}:
                    logger.warning(f"HF auth/permission error (status={resp.status_code}): {body}")
                    HF_INFERENCE_UNAVAILABLE = True
                    return None

                logger.warning(f"HF returned status {resp.status_code} for model={candidate_model} at {url}")
            except requests.exceptions.Timeout:
                logger.warning(f"HF timeout for prompt '{prompt[:60]}'")
            except requests.exceptions.RequestException as e:
                logger.warning(f"HF request error: {e}")

    if saw_endpoint_missing:
        HF_INFERENCE_UNAVAILABLE = True
        logger.warning(
            "HF Inference endpoint/model route unavailable for configured account; using fallback providers for this run"
        )

    return None



def fetch_relevant_images(
    verdicts: List[StoryVerdict],
    output_dir: Path,
    script_text: str = "",
    max_images: int = 4,
    seed_salt: str = "",
    pollinations_base_url: str = "https://image.pollinations.ai",
    hf_api_key: str = "",
    hf_image_model: str = "stabilityai/stable-diffusion-xl-base-1.0",
) -> List[Path]:
    """Fetch relevant images for stories. Priority: Hugging Face SDXL → Pollinations AI → Wikimedia Commons → Placeholders.
    
    HuggingFace is tried first for fast, high-quality image generation with variety of styles.
    Fallback to Pollinations if HF fails. Falls back to Wikimedia Commons, then generates placeholders.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: List[Path] = []

    logger.info(f"[fetch_relevant_images] Starting with {len(verdicts or [])} verdicts, output_dir={output_dir}")

    style_hints = [
        "dynamic street reportage framing",
        "premium newsroom visual language",
        "documentary realism with cinematic mood",
        "high-end editorial magazine composition",
    ]

    # Extract terms from verdicts or use default fallback terms
    try:
        if verdicts:
            terms = _extract_terms(verdicts)
        else:
            logger.warning("[fetch_relevant_images] No verdicts provided, using default terms")
            terms = []
    except Exception as e:
        logger.error(f"[fetch_relevant_images] CRITICAL: Failed to extract terms: {type(e).__name__}: {e}")
        terms = []
    
    # Ensure we have at least some terms to work with
    if not terms:
        logger.warning("[fetch_relevant_images] No terms extracted, using default fallback terms")
        terms = ["News Story", "Breaking News", "Today's Story", "Latest Update"][:max_images]
    
    logger.info(f"[fetch_relevant_images] Using {len(terms)} terms: {terms}")
    logger.info(f"[fetch_relevant_images] Attempting to fetch {max_images} images, will fallback to placeholders if needed")

    for idx, term in enumerate(terms, start=1):
        if len(image_paths) >= max_images:
            logger.info(f"[fetch_relevant_images] Reached max_images limit ({max_images})")
            break

        logger.debug(f"[fetch_relevant_images] Processing term #{idx}/{len(terms)}: '{term}'")
        
        verdict = verdicts[idx - 1] if idx - 1 < len(verdicts) else None
        prompt_context = _build_prompt_context(verdict, script_text) if verdict else term
        
        # Try HF SDXL first (higher variety / styles)
        success = False
        if hf_api_key and not HF_INFERENCE_UNAVAILABLE:  # Only try if API key is configured and endpoint is available
            try:
                logger.debug(f"[fetch_relevant_images] Trying Hugging Face SDXL for '{term}'")
                hf_bytes = _hf_sdxl_image(
                    prompt=(
                        f"{prompt_context}, cinematic editorial photograph, news documentary frame, "
                        f"clean composition, high detail, no text, no watermark"
                    ),
                    width=720,
                    height=1280,
                    model=hf_image_model,
                    hf_api_key=hf_api_key,
                    timeout=120,
                )
                if hf_bytes:
                    image_path = output_dir / f"asset_{idx}.png"
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    image_path.write_bytes(hf_bytes)
                    image_paths.append(image_path)
                    logger.info(f"✓ Saved HuggingFace SDXL image #{idx}: {image_path.name} ({len(hf_bytes)} bytes)")
                    success = True
            except Exception as e:
                logger.warning(f"[fetch_relevant_images] HF SDXL error for '{term}': {type(e).__name__}: {e}")
        else:
            if not hf_api_key:
                logger.debug("[fetch_relevant_images] Skipping HF SDXL (no API key configured)")
            elif HF_INFERENCE_UNAVAILABLE:
                logger.debug("[fetch_relevant_images] Skipping HF SDXL (endpoint unavailable in this run)")

        # Try Pollinations next with stronger retry logic
        if not success:  # Only try Pollinations if HF failed
            pollinations_attempts = 5
            pollinations_timeout = 90
            for poll_attempt in range(pollinations_attempts):
                if success:
                    break

                try:
                    logger.debug(f"[fetch_relevant_images] [{idx}/{max_images}] Pollinations attempt {poll_attempt + 1}/{pollinations_attempts} for: {term}")
                    image_path = output_dir / f"asset_{idx}.png"
                    image_path.parent.mkdir(parents=True, exist_ok=True)

                    pollinations_url = _pollinations_image_url(
                        prompt_context,
                        seed_salt=seed_salt,
                        style_hint=(
                            f"{style_hints[(idx - 1) % len(style_hints)]}, "
                            f"aligned to the reel script and headline"
                        ),
                        base_url=pollinations_base_url,
                    )

                    logger.debug(f"[fetch_relevant_images] Pollinations URL: {pollinations_url[:120]}...")
                    blob = requests.get(
                        pollinations_url,
                        timeout=pollinations_timeout,
                        headers=REQUEST_HEADERS,
                        stream=False,
                    )

                    logger.debug(f"[fetch_relevant_images] Pollinations response status={blob.status_code}")

                    if blob.status_code == 429:
                        wait_time = 5 * (2 ** poll_attempt) + random.uniform(0, 2)
                        logger.warning(f"[fetch_relevant_images] Pollinations rate limited (429), waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)
                        continue

                    if blob.ok and blob.content and len(blob.content) > 1000:
                        image_path.write_bytes(blob.content)
                        image_paths.append(image_path)
                        logger.info(f"✓ Saved Pollinations image #{idx}: {image_path.name} ({len(blob.content)} bytes)")
                        success = True
                        continue
                    elif blob.status_code not in [200, 429]:
                        logger.warning(f"[fetch_relevant_images] Pollinations returned status {blob.status_code}")

                except requests.exceptions.Timeout:
                    logger.warning(f"[fetch_relevant_images] Pollinations timeout for '{term}' (attempt {poll_attempt + 1})")
                    if poll_attempt < pollinations_attempts - 1:
                        sleep_time = (2 ** poll_attempt) * 3 + random.uniform(0, 1)
                        time.sleep(sleep_time)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"[fetch_relevant_images] Pollinations request error: {type(e).__name__}: {e}")
        
        # If Pollinations didn't work, try Wikimedia
        if not success:
            try:
                logger.debug(f"[fetch_relevant_images] Trying Wikimedia fallback for '{term}'...")
                url = _search_wikimedia_image(prompt_context or term)
                
                if not url:
                    logger.warning(f"[fetch_relevant_images] ✗ No Wikimedia image found for '{term}'")
                else:
                    ext = ".jpg" if ".jpg" in url.lower() or ".jpeg" in url.lower() else ".png"
                    image_path = output_dir / f"asset_{idx}{ext}"
                    image_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    logger.debug(f"[fetch_relevant_images] Requesting Wikimedia image: {url[:80]}...")
                    fallback_blob = requests.get(
                        url, 
                        timeout=30,
                        headers=REQUEST_HEADERS
                    )
                    fallback_blob.raise_for_status()
                    
                    if fallback_blob.content and len(fallback_blob.content) > 1000:
                        image_path.write_bytes(fallback_blob.content)
                        image_paths.append(image_path)
                        logger.info(f"✓ Saved Wikimedia image #{idx}: {image_path.name} ({len(fallback_blob.content)} bytes)")
                        success = True
                    
            except requests.exceptions.Timeout:
                logger.error(f"[fetch_relevant_images] ✗ Wikimedia timeout for '{term}'")
            except requests.exceptions.RequestException as e:
                logger.error(f"[fetch_relevant_images] ✗ Wikimedia request error: {type(e).__name__}: {e}")
            except IOError as e:
                logger.error(f"[fetch_relevant_images] ✗ IO error: {type(e).__name__}: {e}")
            except Exception as e:
                logger.error(f"[fetch_relevant_images] ✗ Unexpected error: {type(e).__name__}: {e}")
        
        if not success:
            logger.warning(f"[fetch_relevant_images] ✗ All image sources failed for #{idx} '{term}' - creating placeholder")
            try:
                placeholder_path = output_dir / f"asset_{idx}.png"
                placeholder_path.parent.mkdir(parents=True, exist_ok=True)
                placeholder_text = prompt_context or term
                _generate_placeholder_image(placeholder_path, text=placeholder_text)
                image_paths.append(placeholder_path)
                logger.info(f"✓ Created placeholder image #{idx}: {placeholder_path.name}")
                success = True
            except Exception as e:
                logger.error(f"[fetch_relevant_images] Failed to create placeholder: {type(e).__name__}: {e}")

    logger.info(f"[fetch_relevant_images] COMPLETE: Successfully fetched {len(image_paths)}/{max_images} images")
    
    # CRITICAL FALLBACK: If we have NO images at all, generate placeholders for EVERY term
    if not image_paths:
        logger.warning(f"[fetch_relevant_images] ⚠⚠⚠ CRITICAL: NO IMAGES RETURNED! Creating placeholder images as FALLBACK ⚠⚠⚠")
        try:
            for idx, term in enumerate(terms[:max_images], start=1):
                placeholder_path = output_dir / f"asset_{idx}.png"
                placeholder_path.parent.mkdir(parents=True, exist_ok=True)
                placeholder_text = term[:60] if term else f"Story {idx}"
                logger.warning(f"[fetch_relevant_images] Generating FALLBACK placeholder #{idx}: {placeholder_text}")
                _generate_placeholder_image(placeholder_path, text=placeholder_text)
                image_paths.append(placeholder_path)
                logger.info(f"[fetch_relevant_images] ✓ Created FALLBACK placeholder #{idx}: {placeholder_path.name}")
        except Exception as e:
            logger.error(f"[fetch_relevant_images] CRITICAL ERROR creating fallback placeholders: {type(e).__name__}: {e}", exc_info=True)
    
    logger.info(f"[fetch_relevant_images] FINAL RESULT: {len(image_paths)} images available")
    return image_paths
