from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Set

from .config import Settings
from .crosscheck import cross_check_stories
from .ingest import fetch_recent_stories
from .models import AnchorPackage
from .script_writer import build_news_minute_script
from .video_maker import render_news_video
from .visual_assets import fetch_relevant_images
from .voiceover import synthesize_voiceover



def _story_key(title: str, link: str) -> str:
    clean_link = (link or "").split("?", 1)[0].strip().lower()
    if clean_link:
        return clean_link
    return " ".join((title or "").lower().split())


def _recent_story_keys(output_dir: Path, max_runs: int = 24) -> Set[str]:
    if not output_dir.exists():
        return set()

    keys: Set[str] = set()
    run_dirs = sorted([p for p in output_dir.iterdir() if p.is_dir()], reverse=True)
    for run_dir in run_dirs[:max_runs]:
        verdicts_path = run_dir / "verdicts.json"
        if not verdicts_path.exists():
            continue
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


def run_anchor_cycle(settings: Settings) -> AnchorPackage:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = Path(settings.output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    candidate_stories = fetch_recent_stories(
        feed_url=settings.news_feed_url,
        lookback_hours=settings.lookback_hours,
        max_stories=max(settings.max_stories * 6, settings.max_stories + 10),
    )
    stories = _pick_stories(
        stories=candidate_stories,
        max_stories=settings.max_stories,
        blocked_keys=_recent_story_keys(Path(settings.output_dir), max_runs=24),
    )

    verdicts = cross_check_stories(
        stories=stories,
        api_key=settings.google_api_key,
        cse_id=settings.google_cse_id,
    )

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
                    "published_at": v.story.published_at.isoformat(),
                    "verdict": v.verdict,
                    "score": v.score,
                    "truth_score": v.truth_score,
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

    image_assets = fetch_relevant_images(
        verdicts=verdicts,
        output_dir=run_dir / "assets",
        max_images=4,
        seed_salt=run_id,
        pollinations_base_url=settings.pollinations_base_url,
    )

    audio_path = run_dir / "voiceover.mp3"
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
    reel_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "created_at": datetime.now().isoformat(),
                "headline": verdicts[0].story.title if verdicts else "No fresh stories",
                "top_verdict": top_verdict,
                "top_truth_score": top_truth_score,
                "evidence_count": len(verdicts[0].evidence) if verdicts else 0,
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
