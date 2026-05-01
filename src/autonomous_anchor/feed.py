from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .models import FeedCard


def latest_feed_cards(output_dir: str, limit: int = 20) -> List[FeedCard]:
    root = Path(output_dir)
    if not root.exists():
        return []

    cards: List[FeedCard] = []
    run_dirs = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    for run_dir in run_dirs:
        reel_file = run_dir / "reel.json"
        try:
            if reel_file.exists():
                payload = json.loads(reel_file.read_text(encoding="utf-8"))
            else:
                payload = _payload_from_run_dir(run_dir)
            if not payload.get("video_path"):
                continue
            cards.append(
                FeedCard(
                    run_id=payload.get("run_id", run_dir.name),
                    created_at=payload.get("created_at", ""),
                    video_path=payload.get("video_path", ""),
                    script_path=payload.get("script_path", ""),
                    reel_path=str(reel_file).replace("\\", "/"),
                    top_verdict=payload.get("top_verdict", "no_data"),
                    top_truth_score=int(payload.get("top_truth_score", 0)),
                    headline=payload.get("headline", "No headline"),
                    evidence_count=int(payload.get("evidence_count", 0)),
                )
            )
        except Exception:
            continue

        if len(cards) >= limit:
            break

    return cards


def _payload_from_run_dir(run_dir: Path) -> dict:
    verdicts_file = run_dir / "verdicts.json"
    video_file = run_dir / "news_minute.mp4"
    script_file = run_dir / "script.txt"
    if not verdicts_file.exists() or not video_file.exists():
        return {}

    payload: dict = {
        "run_id": run_dir.name,
        "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(),
        "video_path": str(video_file).replace("\\", "/"),
        "script_path": str(script_file).replace("\\", "/") if script_file.exists() else "",
    }

    try:
        verdicts = json.loads(verdicts_file.read_text(encoding="utf-8"))
        top = verdicts[0] if verdicts else {}
        payload.update(
            {
                "headline": top.get("title", "No headline"),
                "top_verdict": top.get("verdict", "no_data"),
                "top_truth_score": int(top.get("truth_score", 0)),
                "evidence_count": len(top.get("evidence", [])),
            }
        )
    except Exception:
        payload.update(
            {
                "headline": "No headline",
                "top_verdict": "no_data",
                "top_truth_score": 0,
                "evidence_count": 0,
            }
        )

    return payload
