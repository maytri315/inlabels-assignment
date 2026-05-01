from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class RawStory:
    title: str
    summary: str
    link: str
    source: str
    published_at: datetime


@dataclass
class CrossCheckEvidence:
    title: str
    link: str
    source: str
    snippet: str


@dataclass
class StoryVerdict:
    story: RawStory
    score: float
    verdict: str
    key_claim: str
    reason: str
    roast_line: str = ""
    truth_score: int = 0
    evidence: List[CrossCheckEvidence] = field(default_factory=list)


@dataclass
class AnchorPackage:
    run_id: str
    script_text: str
    script_path: str
    audio_path: str
    video_path: str
    verdicts_path: str
    reel_path: str = ""


@dataclass
class FeedCard:
    run_id: str
    created_at: str
    video_path: str
    script_path: str
    reel_path: str
    top_verdict: str
    top_truth_score: int
    headline: str
    evidence_count: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "video_path": self.video_path,
            "script_path": self.script_path,
            "reel_path": self.reel_path,
            "top_verdict": self.top_verdict,
            "top_truth_score": self.top_truth_score,
            "headline": self.headline,
            "evidence_count": self.evidence_count,
        }
