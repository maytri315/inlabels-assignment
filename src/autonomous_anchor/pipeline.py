from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Set

from .config import Settings
from .crosscheck import _infer_category, cross_check_stories
from .ingest import fetch_recent_stories
from .models import AnchorPackage
from .script_writer import build_news_minute_script
from .video_maker import render_news_video
from .visual_assets import fetch_relevant_images
from .voiceover import synthesize_voiceover

logger = logging.getLogger(__name__)


CATEGORY_ALIASES = {
    "tech": "technology",
}


def category_folder_name(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in value.strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    cleaned = cleaned or "general"
    return CATEGORY_ALIASES.get(cleaned, cleaned)



def _story_key(title: str, link: str) -> str:
    clean_link = (link or "").split("?", 1)[0].strip().lower()
    if clean_link:
        return clean_link
    return " ".join((title or "").lower().split())


def _recent_story_keys(output_dir: Path, max_runs: int = 24) -> Set[str]:
    if not output_dir.exists():
        return set()

    keys: Set[str] = set()
    verdict_files = sorted(
        output_dir.rglob("verdicts.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for verdicts_path in verdict_files[:max_runs]:
        try:
            payload = json.loads(verdicts_path.read_text(encoding="utf-8"))
            for row in payload:
                keys.add(_story_key(title=str(row.get("title", "")), link=str(row.get("link", ""))))
        except Exception:
            continue

    return keys


def _pick_stories(stories: Iterable, max_stories: int, blocked_keys: Set[str]):
    selected = []
    used = set()

    for story in stories:
        key = _story_key(story.title, story.link)
        if key in blocked_keys or key in used:
            continue
        selected.append(story)
        used.add(key)
        if len(selected) >= max_stories:
            return selected

    for story in stories:
        key = _story_key(story.title, story.link)
        if key in used:
            continue
        selected.append(story)
        used.add(key)
        if len(selected) >= max_stories:
            break

    return selected


def _prioritize_stories_by_categories(stories: Iterable, preferred_categories: Optional[Iterable[str]]):
    if not preferred_categories:
        return list(stories)

    preferred = {category_folder_name(c) for c in preferred_categories if str(c).strip()}
    if not preferred:
        return list(stories)

    favored = []
    others = []
    for story in stories:
        category = category_folder_name(_infer_category(story))
        story.category = category
        if category in preferred:
            favored.append(story)
        else:
            others.append(story)

    # Prefer selected categories first, then fall back to other stories.
    return favored + others


def _filter_stories_by_categories(stories: Iterable, preferred_categories: Optional[Iterable[str]]):
    if not preferred_categories:
        return list(stories)

    preferred = {category_folder_name(c) for c in preferred_categories if str(c).strip()}
    if not preferred:
        return list(stories)

    matched = []
    for story in stories:
        category = category_folder_name(_infer_category(story))
        story.category = category
        if category in preferred:
            matched.append(story)

    return matched


def run_anchor_cycle(
    settings: Settings,
    preferred_categories: Optional[Iterable[str]] = None,
    skip_image_fetch: bool = False,
    force_personalization_bucket: Optional[str] = None,
) -> AnchorPackage:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    candidate_stories = fetch_recent_stories(
        feed_url=settings.news_feed_url,
        lookback_hours=settings.lookback_hours,
        max_stories=max(settings.max_stories * 6, settings.max_stories + 10),
    )
    prioritized_stories = _prioritize_stories_by_categories(
        stories=candidate_stories,
        preferred_categories=preferred_categories,
    )

    if preferred_categories:
        matched_stories = _filter_stories_by_categories(
            stories=prioritized_stories,
            preferred_categories=preferred_categories,
        )
        if matched_stories:
            prioritized_stories = matched_stories

    stories = _pick_stories(
        stories=prioritized_stories,
        max_stories=settings.max_stories,
        blocked_keys=_recent_story_keys(Path(settings.output_dir), max_runs=24),
    )

    verdicts = cross_check_stories(
        stories=stories,
        api_key=settings.google_api_key,
        cse_id=settings.google_cse_id,
    )

    if preferred_categories:
        preferred = {category_folder_name(c) for c in preferred_categories if str(c).strip()}
        if preferred:
            verdicts.sort(
                key=lambda v: (0 if (v.story.category or "general").lower() in preferred else 1)
            )

    top_category = category_folder_name((verdicts[0].story.category if verdicts else "general") or "general")
    if force_personalization_bucket:
        personalization_bucket = category_folder_name(force_personalization_bucket)
    else:
        personalization_bucket = category_folder_name(top_category)
    run_dir = Path(settings.output_dir) / personalization_bucket / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    script_text = build_news_minute_script(
        verdicts=verdicts,
        style=settings.roast_style,
        groq_api_key=settings.groq_api_key,
        groq_model=settings.groq_model,
    )
    script_path = run_dir / "script.txt"
    script_path.write_text(script_text, encoding="utf-8")

    verdicts_path = run_dir / "verdicts.json"
    verdicts_path.write_text(
        json.dumps(
            [
                {
                    "title": v.story.title,
                    "link": v.story.link,
                    "source": v.story.source,
                    "category": v.story.category,
                    "published_at": v.story.published_at.isoformat(),
                    "verdict": v.verdict,
                    "score": v.score,
                    "truth_score": v.truth_score,
                    "confidence_level": v.confidence_level,
                    "red_flags": v.red_flags,
                    "reason": v.reason,
                    "roast_line": v.roast_line,
                    "evidence": [
                        {
                            "title": ev.title,
                            "link": ev.link,
                            "source": ev.source,
                            "snippet": ev.snippet,
                        }
                        for ev in v.evidence
                    ],
                }
                for v in verdicts
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    if not skip_image_fetch:
        logger.info(f"Starting image asset fetching... (verdicts={len(verdicts)}, category={top_category})")
        try:
            image_assets = fetch_relevant_images(
                verdicts=verdicts,
                script_text=script_text,
                output_dir=run_dir / "assets",
                max_images=4,
                seed_salt=run_id,
                pollinations_base_url=settings.pollinations_base_url,
                hf_api_key=settings.hf_api_key,
                hf_image_model=settings.hf_image_model,
            )
        except Exception as e:
            logger.error(f"Image fetch error: {type(e).__name__}: {e}", exc_info=True)
            image_assets = []
        
        logger.info(f"Image fetch complete: {len(image_assets)} assets returned")
        if image_assets:
            for idx, asset in enumerate(image_assets, 1):
                logger.info(f"  Asset #{idx}: {asset.name} (exists={asset.exists()})")
        else:
            logger.warning(f"⚠ No image assets returned from fetch_relevant_images!")
    else:
        # Create assets folder for consistency but skip remote image generation (faster, avoids rate limits)
        (run_dir / "assets").mkdir(parents=True, exist_ok=True)
        image_assets = []
        logger.info("Skipping image fetch (skip_image_fetch=True)")

    audio_path = run_dir / "voiceover.wav"
    synthesize_voiceover(
        script_text=script_text,
        audio_path=audio_path,
        lang=settings.voice_lang,
        edge_voice=settings.edge_voice,
        edge_rate=settings.edge_rate,
        elevenlabs_api_key=settings.elevenlabs_api_key,
        elevenlabs_voice_id=settings.elevenlabs_voice_id,
    )

    top_verdict = verdicts[0].verdict if verdicts else "uncertain"
    top_truth_score = verdicts[0].truth_score if verdicts else 0

    video_path = run_dir / "news_minute.mp4"
    render_news_video(
        script_lines=script_text.splitlines(),
        audio_path=audio_path,
        out_path=video_path,
        image_assets=image_assets,
        top_verdict=top_verdict,
        top_truth_score=top_truth_score,
    )

    reel_path = run_dir / "reel.json"
    total_evidence_count = sum(len(v.evidence) for v in verdicts)
    reel_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": datetime.now().isoformat(),
                "headline": verdicts[0].story.title if verdicts else "No fresh stories",
                "top_verdict": top_verdict,
                "top_truth_score": top_truth_score,
                "top_category": top_category,
                "top_confidence_level": verdicts[0].confidence_level if verdicts else "medium",
                "top_red_flags": verdicts[0].red_flags if verdicts else [],
                "evidence_count": int(total_evidence_count),
                "personalization_bucket": personalization_bucket,
                "video_path": str(video_path).replace("\\", "/"),
                "script_path": str(script_path).replace("\\", "/"),
                "verdicts_path": str(verdicts_path).replace("\\", "/"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return AnchorPackage(
        run_id=run_id,
        script_text=script_text,
        script_path=str(script_path),
        audio_path=str(audio_path),
        video_path=str(video_path),
        verdicts_path=str(verdicts_path),
        reel_path=str(reel_path),
    )
