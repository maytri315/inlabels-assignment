from __future__ import annotations

import hashlib
import logging
import time
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
    "Accept": "image/*,*/*"
}



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



def fetch_relevant_images(
    verdicts: List[StoryVerdict],
    output_dir: Path,
    max_images: int = 4,
    seed_salt: str = "",
    pollinations_base_url: str = "https://image.pollinations.ai",
) -> List[Path]:
    """Fetch relevant images for stories from Pollinations AI or Wikimedia Commons."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths: List[Path] = []

    style_hints = [
        "dynamic street reportage framing",
        "premium newsroom visual language",
        "documentary realism with cinematic mood",
        "high-end editorial magazine composition",
    ]

    terms = _extract_terms(verdicts)
    logger.info(f"Attempting to fetch {max_images} images for {len(terms)} story terms")

    for idx, term in enumerate(terms, start=1):
        if len(image_paths) >= max_images:
            break
        
        # Try Pollinations first with retry logic
        success = False
        for poll_attempt in range(3):
            if success:
                break
                
            try:
                logger.debug(f"[{idx}/{max_images}] Fetching image for term: {term} (attempt {poll_attempt + 1})")
                image_path = output_dir / f"asset_{idx}.png"
                
                pollinations_url = _pollinations_image_url(
                    term,
                    seed_salt=seed_salt,
                    style_hint=style_hints[(idx - 1) % len(style_hints)],
                    base_url=pollinations_base_url,
                )
                
                logger.debug(f"Pollinations URL: {pollinations_url[:80]}...")
                blob = requests.get(
                    pollinations_url, 
                    timeout=45,
                    headers=REQUEST_HEADERS
                )
                
                if blob.status_code == 429:
                    # Rate limited - wait exponentially longer each time
                    wait_time = 5 * (2 ** poll_attempt)  # 5s, 10s, 20s
                    logger.warning(f"Pollinations rate limited (429), waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                
                if blob.ok and blob.content and len(blob.content) > 1000:
                    image_path.write_bytes(blob.content)
                    image_paths.append(image_path)
                    logger.info(f"✓ Saved Pollinations image #{idx}: {image_path.name} ({len(blob.content)} bytes)")
                    success = True
                    continue
                elif blob.status_code not in [200, 429]:
                    logger.warning(f"Pollinations returned status {blob.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Pollinations timeout for '{term}' (attempt {poll_attempt + 1})")
                if poll_attempt < 2:
                    time.sleep(3)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Pollinations request error for '{term}': {e}")
        
        # If Pollinations didn't work, try Wikimedia
        if not success:
            try:
                logger.debug(f"Trying Wikimedia fallback for '{term}'...")
                url = _search_wikimedia_image(term)
                
                if not url:
                    logger.warning(f"✗ No fallback image found for '{term}'")
                    continue
                    
                ext = ".jpg" if ".jpg" in url.lower() or ".jpeg" in url.lower() else ".png"
                image_path = output_dir / f"asset_{idx}{ext}"
                
                logger.debug(f"Requesting Wikimedia image: {url[:80]}...")
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
                logger.error(f"✗ Wikimedia timeout for '{term}'")
            except requests.exceptions.RequestException as e:
                logger.error(f"✗ Wikimedia request error for '{term}': {e}")
            except IOError as e:
                logger.error(f"✗ IO error saving image for '{term}': {e}")
            except Exception as e:
                logger.error(f"✗ Unexpected error: {type(e).__name__}: {e}")
        
        if not success:
            logger.warning(f"✗ Failed to fetch image #{idx} for '{term}'")

    logger.info(f"Successfully fetched {len(image_paths)}/{max_images} images")
    return image_paths
