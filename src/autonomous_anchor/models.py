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
    category: str = "general"  # general, entertainment, tech, political, sports, business, science


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
    confidence_level: str = "medium"  # low, medium, high
    red_flags: List[str] = field(default_factory=list)  # e.g., ["unverified_source", "criminal_record", "no_evidence"]
    fuzzy_score: float = 0.0  # detailed fuzzy logic score


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
    top_category: str = "general"
    top_confidence_level: str = "medium"
    top_red_flags: List[str] = field(default_factory=list)
    personalization_bucket: str = ""

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
            "top_category": self.top_category,
            "top_confidence_level": self.top_confidence_level,
            "top_red_flags": self.top_red_flags,
            "personalization_bucket": self.personalization_bucket,
        }
