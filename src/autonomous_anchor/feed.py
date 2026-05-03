from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import FeedCard
from .pipeline import category_folder_name


def _run_dirs_from_root(scan_root: Path, recursive: bool) -> List[Path]:
    if recursive:
        reel_dirs = set(p.parent for p in scan_root.rglob("reel.json"))
        verdict_dirs = set(p.parent for p in scan_root.rglob("verdicts.json"))
    else:
        reel_dirs = set(p.parent for p in scan_root.glob("*/reel.json"))
        verdict_dirs = set(p.parent for p in scan_root.glob("*/verdicts.json"))

    return sorted(
        list(reel_dirs | verdict_dirs),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _read_cards_from_root(scan_root: Path, root: Path, recursive: bool = True) -> List[FeedCard]:
    cards: List[FeedCard] = []
    # Find directories with either reel.json or verdicts.json (fallback for videos without reel.json)
    run_dirs = _run_dirs_from_root(scan_root=scan_root, recursive=recursive)
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
                    top_category=payload.get("top_category", "general"),
                    top_confidence_level=payload.get("top_confidence_level", "medium"),
                    top_red_flags=payload.get("top_red_flags", []),
                    personalization_bucket=payload.get("personalization_bucket", run_dir.parent.name if run_dir.parent != root else ""),
                )
            )
        except Exception:
            continue
    return cards


def _round_robin_category_cards(category_cards: Dict[str, List[FeedCard]], ordered_categories: List[str], limit: int) -> List[FeedCard]:
    merged: List[FeedCard] = []
    indexes = {cat: 0 for cat in ordered_categories}

    while len(merged) < limit:
        appended_in_cycle = False
        for cat in ordered_categories:
            entries = category_cards.get(cat, [])
            idx = indexes.get(cat, 0)
            if idx < len(entries):
                merged.append(entries[idx])
                indexes[cat] = idx + 1
                appended_in_cycle = True
                if len(merged) >= limit:
                    break
        if not appended_in_cycle:
            break

    return merged


def _category_scan_roots(root: Path, category: str) -> List[Path]:
    canonical = category_folder_name(category)
    candidates = [root / canonical]
    if canonical == "technology":
        candidates.append(root / "tech")

    scan_roots = []
    for candidate in candidates:
        if candidate.exists() and candidate not in scan_roots:
            scan_roots.append(candidate)
    return scan_roots


def _dedupe_and_sort_cards(cards: List[FeedCard]) -> List[FeedCard]:
    deduped: List[FeedCard] = []
    seen = set()
    for card in cards:
        key = card.reel_path or card.run_id
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)

    deduped.sort(key=lambda card: card.created_at or "", reverse=True)
    return deduped


def latest_feed_cards(output_dir: str, limit: int = 20, categories: Optional[List[str]] = None) -> List[FeedCard]:
    root = Path(output_dir)
    if not root.exists():
        return []

    if categories is None:
        categories = ["general"]

    if categories:
        ordered_categories = []
        seen = set()
        for cat in categories:
            normalized = category_folder_name(cat)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered_categories.append(normalized)

        category_cards: Dict[str, List[FeedCard]] = {}
        for cat in ordered_categories:
            cards: List[FeedCard] = []
            for scan_root in _category_scan_roots(root, cat):
                cards.extend(_read_cards_from_root(scan_root=scan_root, root=root))
            category_cards[cat] = _dedupe_and_sort_cards(cards)

        return _round_robin_category_cards(category_cards, ordered_categories, limit)

    return _read_cards_from_root(scan_root=root, root=root)[:limit]


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
        "personalization_bucket": run_dir.parent.name,
    }

    try:
        verdicts = json.loads(verdicts_file.read_text(encoding="utf-8"))
        top = verdicts[0] if verdicts else {}
        total_evidence_count = sum(len((row or {}).get("evidence", []) or []) for row in verdicts)
        payload.update(
            {
                "headline": top.get("title", "No headline"),
                "top_verdict": top.get("verdict", "no_data"),
                "top_truth_score": int(top.get("truth_score", 0)),
                "evidence_count": int(total_evidence_count),
                "top_category": top.get("category", "general"),
                "top_confidence_level": top.get("confidence_level", "medium"),
                "top_red_flags": top.get("red_flags", []) or [],
            }
        )
    except Exception:
        payload.update(
            {
                "headline": "No headline",
                "top_verdict": "no_data",
                "top_truth_score": 0,
                "evidence_count": 0,
                "top_category": "general",
                "top_confidence_level": "medium",
                "top_red_flags": [],
            }
        )

    return payload
