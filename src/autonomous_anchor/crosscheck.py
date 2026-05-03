from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

import requests
from duckduckgo_search import DDGS
import re
from zoneinfo import ZoneInfo

from tutorial import settings

from .models import CrossCheckEvidence, RawStory, StoryVerdict

from django.conf import settings

# Line 19 must look like this:
SERPER_API_KEY = settings.SERPER_API_KEY # Now safely loaded from .env
SERPER_ENDPOINT = "https://google.serper.dev/search"

GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# Category keywords for automatic classification
CATEGORY_KEYWORDS = {
    "entertainment": ["movie", "actor", "actress", "film", "music", "celebrity", "tv show", "concert", "award"],
    "tech": ["software", "hardware", "ai", "tech", "startup", "app", "programming", "algorithm", "data"],
    "political": ["election", "politician", "congress", "parliament", "minister", "political", "government", "policy"],
    "sports": ["sports", "match", "player", "cricket", "football", "tennis", "olympic", "tournament", "goal"],
    "business": ["company", "business", "startup", "market", "profit", "ipo", "investment", "stock", "entrepreneur"],
    "science": ["research", "science", "study", "discovery", "covid", "vaccine", "medical", "doctor", "hospital"],
}

# Red flag keywords that should raise concerns
RED_FLAG_KEYWORDS = {
    "fir": ["fir", "criminal case", "police case", "case filed"],
    "arrest": ["arrested", "arrest warrant", "detention", "custody"],
    "unverified": ["unconfirmed", "alleged", "rumor", "claim without evidence", "anonymous source"],
    "contradiction": ["contradicts", "denies", "refutes", "denied", "contrary to"],
}

# Primary source keywords (court/legal/official documents)
PRIMARY_SOURCE_KEYWORDS = {
    "fir", "court", "verdict", "judgement", "official statement", "press release",
    "government announcement", "minister", "chief minister", "police report", "affidavit"
}

FACT_CHECK_HINTS = {
    "snopes.com",
    "politifact.com",
    "factcheck.org",
    "fullfact.org",
    "reuters.com",
    "pib.gov.in",
}

LEGAL_HINTS = {
    "indiankanoon.org",
    "sci.gov.in",
    "ecourts.gov.in",
    "districts.ecourts.gov.in",
    "judis.nic.in",
    "hcservices.ecourts.gov.in",
}

OFFICIAL_HINTS = {
    ".gov.in",
    ".nic.in",
    "pib.gov.in",
    "mha.gov.in",
    "mea.gov.in",
    "india.gov.in",
}

FACT_CHECK_TEXT_HINTS = {
    "snopes",
    "politifact",
    "fact check",
    "fact-check",
    "debunk",
    "myth",
    "false claim",
    "hoax",
}

MAINSTREAM_HINTS = {
    "apnews.com",
    "bbc.com",
    "thehindu.com",
    "indianexpress.com",
    "ndtv.com",
    "timesofindia.indiatimes.com",
    "timesofindia.com",
    "hindustantimes.com",
    "washingtonpost.com",
    "nytimes.com",
    "cnn.com",
    "cnbc.com",
    "theguardian.com",
}

SOCIAL_HINTS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "youtube.com",
    "reddit.com",
    "threads.net",
    "telegram.org",
}

BLOG_HINTS = {
    "medium.com",
    "substack.com",
    "wordpress.com",
    "blogspot.com",
}

SOURCE_TYPE_WEIGHTS = {
    "fact_check": 2.0,
    "legal": 1.8,
    "official": 1.5,
    "mainstream": 1.0,
    "blog": 0.2,
    "social": 0.2,
    "other": 0.5,
}

SOURCE_BASE_QUALITY = {
    "fact_check": 0.95,
    "legal": 0.92,
    "official": 0.88,
    "mainstream": 0.72,
    "blog": 0.35,
    "social": 0.20,
    "other": 0.50,
}

SENSATIONALISM_CUES = {
    "shocking",
    "explosive",
    "bombshell",
    "urgent",
    "viral",
    "unprecedented",
    "disaster",
    "catastrophe",
    "outrage",
    "scandal",
    "secret",
    "exposed",
    "fake",
    "hoax",
    "massive",
    "worst",
    "insane",
    "devastating",
    "panicked",
    "fear",
    "angry",
    "breaking",
}

RELATION_GROUPS = {
    "acquisition": {"acquired", "acquire", "bought", "purchase", "takeover", "take over", "purchased"},
    "ownership": {"subsidiary", "owned by", "part of", "parent company", "under the umbrella of"},
    "merger": {"merged", "merger", "combine", "combines with", "fusion"},
    "law": {"arrested", "detained", "charged", "convicted", "raided", "investigated", "indicted"},
    "denial": {"denied", "denies", "refuted", "rejects", "dismissed", "no evidence"},
    "confirmation": {"confirmed", "verifies", "verified", "announced", "stated", "said", "reports"},
    "appointment": {"appointed", "named", "selected", "elected", "hired"},
    "resignation": {"resigned", "stepped down", "quit", "left office"},
}

RELATION_CONTRADICTIONS = {
    "acquisition": {"ownership", "merger"},
    "ownership": {"acquisition", "merger"},
    "merger": {"acquisition", "ownership"},
    "law": {"denial"},
    "denial": {"confirmation", "law"},
    "confirmation": {"denial"},
    "appointment": {"resignation"},
    "resignation": {"appointment"},
}

TRIPLET_RELATION_HINTS = {
    "acquired": "acquired",
    "acquire": "acquired",
    "bought": "acquired",
    "purchased": "acquired",
    "subsidiary": "subsidiary of",
    "owned by": "owned by",
    "parent company": "parent of",
    "merged": "merged with",
    "appointed": "appointed",
    "resigned": "resigned",
    "denied": "denied",
    "confirmed": "confirmed",
    "arrested": "arrested",
    "charged": "charged",
}

# Corruption/scam history keywords for deep checks
CORRUPTION_KEYWORDS = {
    "fir", "scam", "fraud", "corruption", "bribery", "embezzlement",
    "criminal record", "arrest", "conviction", "guilty", "charges filed"
}


class FuzzyTruthLevel(Enum):
    """Fuzzy truth levels for semantic clarity"""
    DEFINITELY_FALSE = 0.0
    PROBABLY_FALSE = 0.25
    UNCERTAIN = 0.5
    PROBABLY_TRUE = 0.75
    DEFINITELY_TRUE = 1.0


@dataclass
class PillarScore:
    """Individual pillar score in HFIS"""
    pillar_name: str
    score: float  # 0.0 to 1.0
    reasoning: str
    overrides_others: bool = False  # If True, this pillar overrides other pillars


@dataclass
class HFISResult:
    """Hierarchical Fuzzy Inference System result"""
    evidence_pillar: PillarScore
    narrative_pillar: PillarScore
    history_pillar: PillarScore
    final_score: float
    override_applied: bool
    deep_check_performed: bool
    historical_context: str


def _infer_category(story: RawStory) -> str:
    """Infer news category from title and summary."""
    text = f"{story.title} {story.summary}".lower()
    
    category_scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            category_scores[category] = score
    
    if category_scores:
        return max(category_scores, key=category_scores.get)
    return "general"


def _detect_red_flags(story: RawStory, evidences: List[CrossCheckEvidence]) -> List[str]:
    """Detect potential red flags in the story."""
    flags: List[str] = []
    text = f"{story.title} {story.summary}".lower()
    
    # Check story text for red flag keywords
    for flag_type, keywords in RED_FLAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            flags.append(flag_type)
    
    # Check if evidence contradicts the claim
    if evidences:
        contradiction_count = 0
        for ev in evidences:
            if any(word in ev.snippet.lower() for word in ["denies", "refutes", "contradicts", "no evidence"]):
                contradiction_count += 1
        if contradiction_count >= len(evidences) * 0.3:  # If 30%+ of evidence contradicts
            flags.append("contradicting_evidence")
    
    # Check if no evidence found (potential misinformation)
    if not evidences:
        flags.append("no_independent_verification")
    
    return flags


def _extract_key_claim(story: RawStory) -> str:
    text = f"{story.title}. {story.summary}".strip()
    return " ".join(text.split())[:240]


def _domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else "unknown"


def _classify_source_type(evidence: CrossCheckEvidence) -> str:
    domain = _domain(evidence.link)
    text = f"{evidence.title} {evidence.snippet}".lower()

    if any(hint in text for hint in FACT_CHECK_TEXT_HINTS):
        return "fact_check"

    if any(domain.endswith(hint) or hint in domain for hint in FACT_CHECK_HINTS):
        return "fact_check"

    if any(domain.endswith(hint) or hint in domain for hint in LEGAL_HINTS):
        return "legal"

    if any(domain.endswith(hint) or hint in domain for hint in SOCIAL_HINTS):
        return "social"

    if any(domain.endswith(hint) or hint in domain for hint in BLOG_HINTS):
        return "blog"

    if any(domain.endswith(ext) for ext in (".gov", ".edu")) or any(hint in domain for hint in ("edu.", "ac.in")) or any(hint in domain for hint in OFFICIAL_HINTS):
        return "official"

    if any(domain.endswith(hint) or hint in domain for hint in MAINSTREAM_HINTS):
        return "mainstream"

    if any(hint in text for hint in ("official statement", "press release", "government", "ministry")):
        return "official"

    return "other"


def _source_quality_score(evidence: CrossCheckEvidence) -> Tuple[float, str]:
    source_type = _classify_source_type(evidence)
    domain = _domain(evidence.link)
    text = f"{evidence.title} {evidence.snippet}".lower()

    score = SOURCE_BASE_QUALITY.get(source_type, 0.5)
    bonuses: List[str] = []

    if source_type == "legal":
        if any(hint in domain for hint in ("indiankanoon.org", "ecourts.gov.in", "sci.gov.in", "judis.nic.in")):
            score += 0.08
            bonuses.append("legal_registry")
        if any(term in text for term in ("order", "judgment", "judgement", "case", "petition", "writ")):
            score += 0.05
            bonuses.append("legal_document")
    elif source_type == "fact_check":
        if any(hint in domain for hint in ("pib.gov.in", "reuters.com", "factcheck.org", "snopes.com", "politifact.com")):
            score += 0.05
            bonuses.append("trusted_fact_check")
    elif source_type == "official":
        if any(hint in domain for hint in ("gov.in", "nic.in", "pib.gov.in", "india.gov.in")):
            score += 0.05
            bonuses.append("official_domain")
        if any(term in text for term in ("press release", "official statement", "notification", "circular")):
            score += 0.04
            bonuses.append("official_document")
    elif source_type == "mainstream":
        if any(hint in domain for hint in ("reuters.com", "apnews.com", "bbc.com", "thehindu.com", "indianexpress.com")):
            score += 0.04
            bonuses.append("wire_or_established_newsroom")

    if any(term in text for term in ("fact check", "debunk", "denies", "refutes", "verified")):
        score += 0.02
        bonuses.append("verification_language")

    return max(0.0, min(1.0, score)), "+".join(bonuses) if bonuses else source_type


def _dedupe_evidences(evidences: List[CrossCheckEvidence]) -> List[CrossCheckEvidence]:
    seen = set()
    deduped: List[CrossCheckEvidence] = []
    for evidence in evidences:
        key = (_domain(evidence.link), evidence.title.strip().lower(), evidence.link.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(evidence)
    return deduped


def _build_search_queries(query: str, story: Optional[RawStory] = None) -> List[str]:
    lower_query = query.lower()
    queries = [query]

    legal_terms = ("fir", "court", "judgment", "judgement", "arrest", "case", "charge", "petition")
    official_terms = ("government", "minister", "department", "policy", "press release", "official")
    misinformation_terms = ("fake", "hoax", "debunk", "rumor", "unverified", "false")

    if any(term in lower_query for term in legal_terms):
        queries.extend([
            f'site:indiankanoon.org {query}',
            f'site:ecourts.gov.in {query}',
            f'site:sci.gov.in {query}',
        ])

    if any(term in lower_query for term in official_terms):
        queries.extend([
            f'site:pib.gov.in {query}',
            f'site:gov.in {query}',
            f'site:nic.in {query}',
        ])

    if any(term in lower_query for term in misinformation_terms):
        queries.extend([
            f'site:factcheck.pib.gov.in {query}',
            f'site:reuters.com {query}',
            f'site:apnews.com {query}',
        ])

    if story and story.category in {"political", "business", "science"}:
        queries.append(f'site:reuters.com {query}')

    deduped: List[str] = []
    seen = set()
    for item in queries:
        normalized = " ".join(item.split())
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[:6]


def _local_date_check(story: RawStory) -> Optional[Tuple[bool, List[CrossCheckEvidence]]]:
    """
    Quick local checks for simple temporal/date assertions.
    Returns (matched: bool, evidence_list) when the text includes a date or 'today'.
    Returns None when no simple local check applies.
    """
    text = f"{story.title} {story.summary}".lower()
    if "today" not in text and not re.search(r"\b\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", text):
        return None

    # Try to extract explicit day/month like '3rd may' or '3 may'
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)", text)
    now_kolkata = datetime.now(ZoneInfo("Asia/Kolkata"))

    def _format_local_date(value: datetime) -> str:
        # %-d is not supported on Windows; build a cross-platform day-month-year string.
        return f"{value.day} {value.strftime('%B %Y')}"

    if m:
        day = int(m.group(1))
        month_str = m.group(2)[:3].lower()
        month_map = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        month = month_map.get(month_str, None)
        snippet = f"Local system date in Asia/Kolkata is {_format_local_date(now_kolkata)}"
        ev = CrossCheckEvidence(title="Local system time", link="", source="local", snippet=snippet)
        matched = (month == now_kolkata.month and day == now_kolkata.day)
        return matched, [ev]

    # If the text simply uses the word 'today', return the local date as supporting evidence (match assumed True)
    if "today" in text:
        snippet = f"Local system date in Asia/Kolkata is {_format_local_date(now_kolkata)}"
        ev = CrossCheckEvidence(title="Local system time", link="", source="local", snippet=snippet)
        return True, [ev]

    return None


def _collect_evidence(query: str, api_key: str, cse_id: str, story: Optional[RawStory] = None, num: int = 5) -> List[CrossCheckEvidence]:
    batches: List[List[CrossCheckEvidence]] = []

    try:
        batches.append(_duckduckgo_search(query=query, num=num))
    except Exception:
        pass

    if api_key and cse_id:
        try:
            batches.append(_google_search(api_key=api_key, cse_id=cse_id, query=query, num=num))
        except Exception:
            pass

    for query_variant in _build_search_queries(query, story=story):
        if query_variant == query:
            continue
        try:
            batches.append(_duckduckgo_search(query=query_variant, num=max(3, num - 2)))
        except Exception:
            pass

        if api_key and cse_id:
            try:
                batches.append(_google_search(api_key=api_key, cse_id=cse_id, query=query_variant, num=max(3, num - 2)))
            except Exception:
                pass

    merged: List[CrossCheckEvidence] = []
    for batch in batches:
        merged.extend(batch)

    deduped = _dedupe_evidences(merged)
    ranked = sorted(
        deduped,
        key=lambda ev: (_source_quality_score(ev)[0], len(ev.snippet or ""), len(ev.title or "")),
        reverse=True,
    )
    return ranked[: max(1, num)]


def _verification_depth_metrics(evidences: List[CrossCheckEvidence]) -> Tuple[float, str]:
    if not evidences:
        return 0.0, "Verification depth is zero because no evidence was found."

    counts = Counter(_classify_source_type(ev) for ev in evidences)
    weighted_total = sum(SOURCE_TYPE_WEIGHTS.get(source_type, 0.5) * count for source_type, count in counts.items())
    quality_scores = [_source_quality_score(ev)[0] for ev in evidences]
    quality_score = sum(quality_scores) / max(1, len(quality_scores))
    diversity_bonus = min(0.15, 0.04 * max(0, len(counts) - 1))
    count_factor = min(1.0, len(evidences) / 5.0)
    weighted_depth = min(1.0, weighted_total / max(1.0, len(evidences) * 2.0))
    depth_score = max(0.0, min(1.0, (0.45 * weighted_depth) + (0.40 * quality_score) + (0.15 * count_factor) + diversity_bonus))

    mix_bits = ", ".join(f"{source_type}:{count}" for source_type, count in sorted(counts.items()))
    reasoning = f"Verification depth {depth_score:.2f} from source mix [{mix_bits}] and avg source quality {quality_score:.2f}."
    return depth_score, reasoning


def _stylometric_sensationalism_metrics(story: RawStory) -> Tuple[float, str]:
    text = f"{story.title} {story.summary}"
    lower_text = text.lower()

    cue_hits = sum(1 for cue in SENSATIONALISM_CUES if cue in lower_text)
    exclamations = text.count("!")
    questions = text.count("?")
    all_caps_tokens = sum(1 for token in story.title.split() if len(token) > 3 and token.isupper())
    uppercase_ratio = 0.0
    alphabetic_chars = [char for char in story.title if char.isalpha()]
    if alphabetic_chars:
        uppercase_ratio = sum(1 for char in alphabetic_chars if char.isupper()) / len(alphabetic_chars)

    score = min(
        1.0,
        (cue_hits * 0.14)
        + (exclamations * 0.08)
        + (questions * 0.04)
        + (all_caps_tokens * 0.10)
        + (0.20 if uppercase_ratio >= 0.45 else 0.0),
    )

    if score >= 0.7:
        level = "high"
    elif score >= 0.4:
        level = "moderate"
    else:
        level = "low"

    reasoning = (
        f"Sensationalism {level} at {score:.2f} from {cue_hits} cue hits, {exclamations} exclamation marks, "
        f"{questions} question marks, and {all_caps_tokens} all-caps tokens."
    )
    return score, reasoning


def _relation_group(text: str) -> Optional[str]:
    lower_text = text.lower()
    for group, keywords in RELATION_GROUPS.items():
        if any(keyword in lower_text for keyword in keywords):
            return group
    return None


def _semantic_consistency_metrics(story: RawStory, evidences: List[CrossCheckEvidence]) -> Tuple[float, str]:
    claim_text = f"{story.title} {story.summary}"
    claim_group = _relation_group(claim_text)

    if not evidences:
        return 0.5, "Semantic consistency is neutral because no evidence could be compared against the claim triplet."

    support_hits = 0
    contradiction_hits = 0
    evidence_groups: List[str] = []

    for evidence in evidences:
        evidence_text = f"{evidence.title} {evidence.snippet}"
        evidence_group = _relation_group(evidence_text)
        if evidence_group:
            evidence_groups.append(evidence_group)

        if claim_group and evidence_group == claim_group:
            support_hits += 1
        elif claim_group and evidence_group and evidence_group in RELATION_CONTRADICTIONS.get(claim_group, set()):
            contradiction_hits += 1
        elif claim_group in {"acquisition", "ownership", "merger"} and any(term in evidence_text.lower() for term in ("subsidiary", "owned by", "part of")):
            contradiction_hits += 1
        elif claim_group == "denial" and any(term in evidence_text.lower() for term in ("confirmed", "verified", "announced")):
            contradiction_hits += 1

    score = 0.55
    score += min(0.20, support_hits * 0.08)
    score -= min(0.35, contradiction_hits * 0.15)

    if claim_group and claim_group in evidence_groups:
        score += 0.08

    score = max(0.0, min(1.0, score))
    if score >= 0.75:
        level = "strong"
    elif score >= 0.45:
        level = "mixed"
    else:
        level = "contradictory"

    reasoning = (
        f"Semantic consistency is {level} at {score:.2f}; claim relation group={claim_group or 'none'}, "
        f"support hits={support_hits}, contradiction hits={contradiction_hits}."
    )
    return score, reasoning


def _extract_claim_triplets(text: str) -> List[Tuple[str, str, str]]:
    clean_text = " ".join(text.split())
    lower_text = clean_text.lower()
    triplets: List[Tuple[str, str, str]] = []

    for hint, relation in TRIPLET_RELATION_HINTS.items():
        if hint not in lower_text:
            continue

        index = lower_text.find(hint)
        left = clean_text[:index].strip(" ,.-:;()[]{}")
        right = clean_text[index + len(hint):].strip(" ,.-:;()[]{}")
        subject = left.split()[-3:] if left else []
        obj = right.split()[:4] if right else []
        subject_text = " ".join(subject).strip() or "unknown"
        object_text = " ".join(obj).strip() or "unknown"
        triplets.append((subject_text, relation, object_text))

    if not triplets and clean_text:
        words = clean_text.split()
        if len(words) >= 3:
            triplets.append((words[0], "related_to", " ".join(words[1:4])))

    return triplets[:4]


def _triplet_consistency_metrics(story: RawStory, evidences: List[CrossCheckEvidence]) -> Tuple[float, str]:
    story_triplets = _extract_claim_triplets(f"{story.title}. {story.summary}")
    if not story_triplets:
        return 0.5, "Triplet consistency is neutral because no claim triplets could be extracted."

    evidence_text = " ".join(f"{ev.title} {ev.snippet}" for ev in evidences)
    evidence_triplets = _extract_claim_triplets(evidence_text)

    matches = 0
    contradictions = 0

    for _, relation, _ in story_triplets:
        if any(relation in evidence_relation for _, evidence_relation, _ in evidence_triplets):
            matches += 1
        elif any(
            relation in RELATION_CONTRADICTIONS.get(evidence_relation, set())
            for _, evidence_relation, _ in evidence_triplets
        ):
            contradictions += 1

    score = 0.55 + min(0.25, matches * 0.10) - min(0.30, contradictions * 0.15)
    score = max(0.0, min(1.0, score))

    if score >= 0.75:
        level = "consistent"
    elif score >= 0.45:
        level = "mixed"
    else:
        level = "contradictory"

    reasoning = (
        f"Triplet consistency is {level} at {score:.2f}; extracted {len(story_triplets)} claim triplets, "
        f"matches={matches}, contradictions={contradictions}."
    )
    return score, reasoning


def _temporal_consistency_metrics(story: RawStory, evidences: List[CrossCheckEvidence]) -> Tuple[float, str]:
    if not evidences:
        return 0.35, "Temporal consistency is weak because there are no corroborating sources to establish a cascade."

    fact_check_hits = 0
    mainstream_hits = 0
    social_hits = 0
    blog_hits = 0

    for evidence in evidences:
        source_type = _classify_source_type(evidence)
        if source_type == "fact_check":
            fact_check_hits += 1
        elif source_type == "mainstream":
            mainstream_hits += 1
        elif source_type == "social":
            social_hits += 1
        elif source_type == "blog":
            blog_hits += 1

    age_hours = max(0.0, (datetime.now(timezone.utc) - story.published_at.astimezone(timezone.utc)).total_seconds() / 3600.0)
    recent_story = age_hours <= 24.0

    score = 0.45
    score += min(0.25, mainstream_hits * 0.10)
    score += min(0.30, fact_check_hits * 0.20)
    score -= min(0.25, social_hits * 0.08)
    score -= min(0.15, blog_hits * 0.05)

    if recent_story and social_hits > mainstream_hits and fact_check_hits == 0:
        score -= 0.15

    score = max(0.0, min(1.0, score))

    if fact_check_hits:
        level = "fact_checked"
    elif mainstream_hits >= max(1, social_hits):
        level = "cascade_like"
    elif social_hits > mainstream_hits:
        level = "social_first"
    else:
        level = "mixed"

    reasoning = (
        f"Temporal consistency is {level} at {score:.2f}; age={age_hours:.1f}h, fact-check hits={fact_check_hits}, "
        f"mainstream hits={mainstream_hits}, social hits={social_hits}, blog hits={blog_hits}."
    )
    return score, reasoning


# ============================================================================
# HIERARCHICAL FUZZY INFERENCE SYSTEM (HFIS) - Three Pillars of Truth
# ============================================================================

def _evaluate_pillar_a_evidence_weight(
    story: RawStory,
    evidences: List[CrossCheckEvidence]
) -> PillarScore:
    """
    PILLAR A: EVIDENCE WEIGHT
    
    Primary Source Rule: If an FIR exists, Evidence Weight = 1.0, 
    regardless of what the majority says.
    
    Evaluates:
    - Existence of FIR, Court Case ID
    - Direct Quotes from Officials
    - Primary source credibility
    """
    text = f"{story.title} {story.summary}".lower()
    
    # Check for critical primary sources
    has_fir = any(kw in text for kw in ["fir", "criminal case", "police case", "case filed"])
    has_court = any(kw in text for kw in ["court", "verdict", "judgement"])
    has_official = any(kw in text for kw in ["official statement", "press release", "minister", "government"])
    
    primary_source_in_evidence = False
    primary_quote_count = 0
    legal_hits = 0
    official_hits = 0
    quality_scores: List[float] = []
    source_mix = Counter()
    
    for ev in evidences:
        ev_text = f"{ev.title} {ev.snippet}".lower()
        source_type = _classify_source_type(ev)
        source_mix[source_type] += 1
        quality_score, _ = _source_quality_score(ev)
        quality_scores.append(quality_score)

        if source_type == "legal":
            legal_hits += 1
        if source_type == "official":
            official_hits += 1

        if any(kw in ev_text for kw in PRIMARY_SOURCE_KEYWORDS):
            primary_source_in_evidence = True
        if any(kw in ev_text for kw in ["said", "stated", "announced", "declared"]):
            primary_quote_count += 1
    
    # Calculate Evidence Weight score
    evidence_weight = 0.0
    reasoning = ""
    
    if has_fir:
        evidence_weight = 1.0
        reasoning = "CRITICAL: FIR/Criminal case detected. Evidence Weight = 1.0 (OVERRIDES majority)."
        return PillarScore(
            pillar_name="Evidence Weight (Pillar A)",
            score=evidence_weight,
            reasoning=reasoning,
            overrides_others=True
        )
    
    if has_court and primary_source_in_evidence:
        evidence_weight = 0.95
        reasoning = "Court case with primary source evidence. Very high credibility."
        return PillarScore(
            pillar_name="Evidence Weight (Pillar A)",
            score=evidence_weight,
            reasoning=reasoning,
            overrides_others=True
        )
    
    avg_quality = sum(quality_scores) / max(1, len(quality_scores)) if quality_scores else 0.0
    unique_domains = len({_domain(ev.link) for ev in evidences})
    diversity_bonus = min(0.08, 0.02 * max(0, unique_domains - 1))

    if has_official or primary_quote_count >= 2 or legal_hits >= 1:
        evidence_weight = min(0.95, 0.84 + (0.10 * avg_quality) + diversity_bonus)
        reasoning = "Official, legal, or quoted primary evidence found."
    elif primary_source_in_evidence:
        evidence_weight = min(0.90, 0.72 + (0.12 * avg_quality) + diversity_bonus)
        reasoning = "Primary source evidence available."
    elif len(evidences) >= 3:
        evidence_weight = min(0.85, 0.55 + (0.25 * avg_quality) + diversity_bonus)
        reasoning = "Adequate independent verification available."
    elif len(evidences) >= 1:
        evidence_weight = min(0.65, 0.35 + (0.25 * avg_quality) + diversity_bonus)
        reasoning = "Limited but some independent evidence available."
    else:
        evidence_weight = 0.1
        reasoning = "No independent verification available."

    if official_hits >= 2:
        evidence_weight = min(0.97, evidence_weight + 0.05)
    if legal_hits >= 2:
        evidence_weight = min(0.98, evidence_weight + 0.06)
    if source_mix.get("social", 0) >= max(2, len(evidences) // 2):
        evidence_weight = max(0.0, evidence_weight - 0.15)

    reasoning = (
        f"{reasoning} Avg source quality {avg_quality:.2f}; mix [{', '.join(f'{k}:{v}' for k, v in sorted(source_mix.items())) or 'none'}]."
    )
    
    return PillarScore(
        pillar_name="Evidence Weight (Pillar A)",
        score=evidence_weight,
        reasoning=reasoning,
        overrides_others=False
    )


def _evaluate_pillar_b_narrative_diversity(
    story: RawStory,
    evidences: List[CrossCheckEvidence]
) -> PillarScore:
    """
    PILLAR B: NARRATIVE DIVERSITY
    
    Propaganda Filter: If many sources say the same thing with zero evidence,
    mark as "High Narrative, Low Substance."
    
    Evaluates:
    - Are all news sites using identical wording? (indicates copy-paste/propaganda)
    - Are sources independent?
    - Is there substantive evidence or just repetition?
    """
    if not evidences:
        return PillarScore(
            pillar_name="Narrative Diversity (Pillar B)",
            score=0.2,
            reasoning="No evidence to assess narrative diversity. Likely propaganda.",
            overrides_others=False
        )
    
    story_tokens = set(story.title.lower().split())
    
    # Calculate how many sources are essentially repeating the same narrative
    token_overlaps = []
    unique_domains = set()
    source_types = Counter()
    
    for ev in evidences:
        unique_domains.add(_domain(ev.link))
        source_types[_classify_source_type(ev)] += 1
        ev_tokens = set(ev.title.lower().split())
        overlap_ratio = len(story_tokens.intersection(ev_tokens)) / max(len(story_tokens), 1)
        token_overlaps.append(overlap_ratio)
    
    avg_overlap = sum(token_overlaps) / len(token_overlaps) if token_overlaps else 0
    
    # Check for substantive differences in evidence
    has_varied_content = len(unique_domains) >= len(evidences) * 0.7  # 70%+ unique domains
    source_type_diversity = len(source_types) / 6.0
    domain_diversity = min(1.0, len(unique_domains) / max(1, len(evidences)))
    
    # Assess narrative diversity
    diversity_score = 0.0
    reasoning = ""
    
    if avg_overlap > 0.8 and not has_varied_content:
        diversity_score = 0.1
        reasoning = "PROPAGANDA SIGNAL: High narrative overlap with few independent sources. Likely copy-paste propaganda."
    elif avg_overlap > 0.7:
        diversity_score = 0.3
        reasoning = "Significant narrative overlap detected. Sources may be echoing each other rather than independently verifying."
    elif avg_overlap > 0.5 and has_varied_content:
        diversity_score = 0.58 + (0.12 * domain_diversity)
        reasoning = "Moderate narrative overlap. Multiple independent sources corroborating key points."
    elif has_varied_content:
        diversity_score = 0.82 + (0.10 * source_type_diversity)
        reasoning = "High narrative diversity. Independent sources with varied perspectives and evidence."
    else:
        diversity_score = 0.42 + (0.10 * domain_diversity) + (0.08 * source_type_diversity)
        reasoning = "Mixed narrative signals. Some overlaps but reasonable diversity."

    if source_types.get("social", 0) >= max(2, len(evidences) // 2):
        diversity_score = max(0.0, diversity_score - 0.18)
        reasoning = "Social-heavy evidence lowers narrative diversity."
    if source_types.get("fact_check", 0) >= 1 or source_types.get("legal", 0) >= 1:
        diversity_score = min(1.0, diversity_score + 0.05)
    
    return PillarScore(
        pillar_name="Narrative Diversity (Pillar B)",
        score=diversity_score,
        reasoning=reasoning,
        overrides_others=False
    )


def _evaluate_pillar_c_entity_history(
    story: RawStory,
    historical_context: Optional[Dict[str, str]] = None
) -> PillarScore:
    """
    PILLAR C: ENTITY HISTORY
    
    Contextual Probability: A scam report is 2x more likely to be true 
    if the department/person has a history of corruption.
    
    Evaluates:
    - Past criminal record of the person
    - Previous scams in that specific department/location
    - Historical context from deep check
    """
    text = f"{story.title} {story.summary}".lower()
    
    history_score = 0.5  # Default neutral
    reasoning = ""
    
    # Without historical context, use weak signals
    if not historical_context:
        # Extract entities (person, department names) - basic approach
        has_negative_history_keywords = any(
            kw in text for kw in ["again", "another", "repeat", "still", "continues to"]
        )
        
        if has_negative_history_keywords:
            history_score = 0.65
            reasoning = "Linguistic signals suggest repeat behavior. Historical context needed for confirmation."
        else:
            history_score = 0.5
            reasoning = "No explicit historical references. Contextual probability remains neutral."
    else:
        # With historical context from deep check
        person_history = historical_context.get("person_history", "").lower()
        department_history = historical_context.get("department_history", "").lower()
        previous_cases = historical_context.get("previous_cases", 0)
        
        corruption_found_person = any(kw in person_history for kw in CORRUPTION_KEYWORDS)
        corruption_found_dept = any(kw in department_history for kw in CORRUPTION_KEYWORDS)
        
        if corruption_found_person and corruption_found_dept:
            history_score = 0.95
            reasoning = f"STRONG CONTEXTUAL PROBABILITY: Both person and department have corruption history. Likelihood boosted 2-3x. ({previous_cases} previous cases found)"
        elif corruption_found_person:
            history_score = 0.85
            reasoning = f"Person has known history of corruption/legal issues. Contextual probability boosted 2x."
        elif corruption_found_dept:
            history_score = 0.80
            reasoning = f"Department has documented history of corruption. Likelihood boosted 2x."
        elif previous_cases > 0:
            history_score = 0.70
            reasoning = f"Previous related cases found ({previous_cases}). Contextual probability moderate boost."
        else:
            history_score = 0.55
            reasoning = "Historical search performed but no significant corruption history found."
    
    return PillarScore(
        pillar_name="Entity History (Pillar C)",
        score=history_score,
        reasoning=reasoning,
        overrides_others=False
    )


def _perform_deep_check(
    story: RawStory,
    evidences: List[CrossCheckEvidence],
    api_key: str,
    cse_id: str
) -> Tuple[bool, Dict[str, str]]:
    """
    DEEP CHECK FUNCTION
    
    Triggers when story is controversial or confidence is borderline.
    Performs secondary searches to build historical context.
    
    Returns: (deep_check_performed, historical_context_dict)
    """
    # Extract key entities and potential person/department names
    text = f"{story.title} {story.summary}".lower()
    
    # Detect if story is potentially controversial
    controversial_keywords = ["denies", "claims", "alleged", "fake", "scam", "fraud"]
    is_controversial = any(kw in text for kw in controversial_keywords)
    
    # Also trigger deep check if there are conflicting signals in evidence
    has_conflicting_signals = False
    if evidences:
        affirming = sum(1 for ev in evidences if any(kw in ev.snippet.lower() for kw in ["confirms", "verifies", "true"]))
        denying = sum(1 for ev in evidences if any(kw in ev.snippet.lower() for kw in ["denies", "false", "fake"]))
        has_conflicting_signals = affirming > 0 and denying > 0
    
    if not (is_controversial or has_conflicting_signals):
        return False, {}
    
    # Perform historical queries
    historical_context = {
        "person_history": "",
        "department_history": "",
        "previous_cases": 0
    }
    
    try:
        # Extract potential person/entity names (simple heuristic)
        # Look for capitalized words that might be names
        words = story.title.split()
        potential_entities = [w.strip("()[]") for w in words if len(w) > 2 and w[0].isupper()]
        
        if potential_entities:
            entity_name = " ".join(potential_entities[:2])  # Take first 2 words as entity
            
            # Historical search for person: "FIR against [Name]" or "[Name] criminal case"
            history_query = f'"{entity_name}" FIR criminal case Lucknow'
            history_results = _collect_evidence(history_query, api_key, cse_id, story=story, num=3)
            
            if history_results:
                historical_context["person_history"] = " ".join(
                    [f"{ev.title} {ev.snippet}" for ev in history_results[:2]]
                )
                historical_context["previous_cases"] = len(history_results)
            
            # Search for department history if applicable
            if "department" in text:
                dept_query = f'Lucknow department corruption scam history'
                dept_results = _collect_evidence(dept_query, api_key, cse_id, story=story, num=3)
                if dept_results:
                    historical_context["department_history"] = " ".join(
                        [f"{ev.title} {ev.snippet}" for ev in dept_results[:2]]
                    )
    except Exception:
        pass  # Deep check is best-effort
    
    return True, historical_context


def _aggregate_hfis_pillars(
    pillar_a: PillarScore,
    pillar_b: PillarScore,
    pillar_c: PillarScore
) -> HFISResult:
    """
    Aggregate the three pillars into final HFIS score.
    
    Logic:
    - If Evidence Pillar has override flag, it dominates the final score
    - Otherwise, weighted average with consideration for all three
    - Adjust based on pillar conflicts
    """
    override_applied = False
    final_score = 0.0
    
    if pillar_a.overrides_others:
        # Evidence Pillar override: use its score
        final_score = pillar_a.score
        override_applied = True
    else:
        # Weighted aggregation: 40% Evidence + 35% Narrative + 25% History
        # If narrative indicates propaganda despite high evidence, reduce weight
        if pillar_b.score < 0.3:  # Propaganda detected
            final_score = (0.60 * pillar_a.score + 0.20 * pillar_b.score + 0.20 * pillar_c.score)
        else:
            final_score = (0.40 * pillar_a.score + 0.35 * pillar_b.score + 0.25 * pillar_c.score)
    
    return HFISResult(
        evidence_pillar=pillar_a,
        narrative_pillar=pillar_b,
        history_pillar=pillar_c,
        final_score=min(1.0, final_score),
        override_applied=override_applied,
        deep_check_performed=False,
        historical_context=""
    )



def _score_evidence(story: RawStory, evidences: List[CrossCheckEvidence]) -> tuple[float, str, float]:
    """
    LEGACY FUNCTION - kept for backward compatibility
    
    Calculate evidence score using fuzzy logic.
    Returns: (score, reason, confidence_level)
    
    NOTE: This is superseded by HFIS but maintained for compatibility.
    """
    if not evidences:
        return 0.1, "No corroborating coverage from indexed sources.", 0.2

    title_tokens = set(story.title.lower().split())
    overlap_hits = 0
    reputable_hits = 0
    reputable_domains = {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "thehindu.com",
        "indianexpress.com",
        "ndtv.com",
        "timesofindia.indiatimes.com",
    }

    # Fuzzy scoring with weights (not just binary)
    for ev in evidences:
        ev_tokens = set(ev.title.lower().split())
        overlap_ratio = len(title_tokens.intersection(ev_tokens)) / max(len(title_tokens), 1)
        
        # Weighted overlap (0-1 scale instead of binary)
        if overlap_ratio >= 0.6:
            overlap_hits += 1.0  # Full weight
        elif overlap_ratio >= 0.3:
            overlap_hits += 0.5  # Partial weight
        
        dom = _domain(ev.link)
        if any(dom.endswith(rd) for rd in reputable_domains):
            reputable_hits += 1.0
        elif dom and not dom.startswith("unknown"):
            reputable_hits += 0.3  # Partial weight for unverified but indexed sources

    # Fuzzy logic calculation with weighted components
    # Base: 0.15, Overlap: 0.35 (weight), Reputable: 0.35 (weight), Evidence count: 0.15
    evidence_count_score = min(1.0, len(evidences) / 5.0)  # Up to 5 evidences = 1.0
    overlap_score = min(1.0, overlap_hits / len(evidences))
    reputable_score = min(1.0, reputable_hits / len(evidences))
    
    # Weighted fuzzy score
    fuzzy_score = (
        0.15 * 0.5 +  # Base confidence
        0.35 * overlap_score +  # 35% weight for title overlap
        0.35 * reputable_score +  # 35% weight for reputable sources
        0.15 * evidence_count_score  # 15% weight for evidence count
    )
    
    score = min(1.0, fuzzy_score)
    
    # Determine confidence level
    if score >= 0.7:
        confidence = "high"
        reason = "Claim is strongly corroborated by multiple sources (>70% confidence)."
    elif score >= 0.5:
        confidence = "medium"
        reason = "Claim has reasonable corroboration but some uncertainty remains."
    else:
        confidence = "low"
        reason = "Claim lacks strong corroboration and may be misleading."
    
    return score, reason, score  # Return score as both score and confidence_level


def _verdict_from_hfis(
    hfis_result: HFISResult,
    red_flags: List[str]
) -> Tuple[str, str]:
    """
    Determine verdict using HFIS-based reasoning.
    
    Returns: (verdict_string, detailed_reasoning)
    """
    score = hfis_result.final_score
    
    # Critical flags that should downgrade verdict
    critical_flags = {"arrest", "fir", "contradicting_evidence"}
    has_critical_flags = any(flag in red_flags for flag in critical_flags)
    
    # Override logic: if Evidence Pillar was override and it's high confidence
    if hfis_result.override_applied and hfis_result.evidence_pillar.score >= 0.85:
        return "verified", f"Override by Evidence Pillar: {hfis_result.evidence_pillar.reasoning}"
    
    # If FIR exists despite majority saying otherwise, mark as uncertain/investigate
    if "fir" in red_flags and score >= 0.7:
        return "uncertain", "FIR/Criminal case detected - requires human verification despite high corroboration score."
    
    # Standard verdict logic with HFIS score
    if score >= 0.75:
        if has_critical_flags:
            return "uncertain", "High corroboration but critical flags detected. Requires investigation."
        return "verified", "High confidence HFIS score with no critical warnings."
    elif score >= 0.55:
        return "uncertain", "Moderate HFIS score. Evidence and narrative signals mixed."
    else:
        return "likely_fake", "Low HFIS score. Insufficient corroboration or propaganda signals detected."


def _verdict_from_score(score: float, red_flags: List[str]) -> str:
    """
    LEGACY FUNCTION - kept for backward compatibility
    
    Determine verdict using fuzzy logic with 70% threshold.
    Takes into account red flags that might override the score.
    """
    # If there are critical red flags, downgrade verdict
    critical_flags = {"arrest", "fir", "contradicting_evidence"}
    has_critical_flags = any(flag in red_flags for flag in critical_flags)
    
    if score >= 0.7:
        # 70% or higher = verified
        if has_critical_flags:
            return "uncertain"  # Downgrade if critical flags exist
        return "verified"
    elif score >= 0.5:
        return "uncertain"
    else:
        return "likely_fake"



def _google_search(api_key: str, cse_id: str, query: str, num: int = 5) -> List[CrossCheckEvidence]:
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": max(1, min(10, num)),
        "safe": "active",
    }
    response = requests.get(GOOGLE_SEARCH_ENDPOINT, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()

    results = []
    for item in payload.get("items", []):
        results.append(
            CrossCheckEvidence(
                title=item.get("title", "Untitled result"),
                link=item.get("link", ""),
                source=_domain(item.get("link", "")),
                snippet=item.get("snippet", ""),
            )
        )
    return results


def _duckduckgo_search(query: str, num: int = 5) -> List[CrossCheckEvidence]:
    results: List[CrossCheckEvidence] = []
    with DDGS() as ddgs:
        rows = ddgs.text(query, region="in-en", safesearch="moderate", max_results=max(1, min(10, num)))
        for row in rows:
            url = row.get("href") or ""
            results.append(
                CrossCheckEvidence(
                    title=(row.get("title") or "Untitled result").strip(),
                    link=url,
                    source=_domain(url),
                    snippet=(row.get("body") or "").strip(),
                )
            )
    return results


def cross_check_stories(stories: List[RawStory], api_key: str, cse_id: str) -> List[StoryVerdict]:
    """
    Cross-check stories using Hierarchical Fuzzy Inference System (HFIS).
    
    Implements three-pillar verification:
    1. Evidence Weight (Pillar A) - Primary sources override majority
    2. Narrative Diversity (Pillar B) - Propaganda detection
    3. Entity History (Pillar C) - Contextual probability boost
    """
    verdicts: List[StoryVerdict] = []
    
    for story in stories:
        claim = _extract_key_claim(story)

        # Quick local checks: short-circuit obvious temporal/date claims using system time (Asia/Kolkata timezone)
        local_result = _local_date_check(story)
        if local_result is not None:
            matched, local_evidence = local_result
            evidence = local_evidence
            local_override = bool(matched)
        else:
            evidence = _collect_evidence(claim, api_key, cse_id, story=story, num=5)
            local_override = False

        # Detect red flags
        red_flags = _detect_red_flags(story, evidence)
        category = _infer_category(story)
        
        # HFIS PROCESSING - Three Pillars
        # Pillar A: Evidence Weight
        if local_override:
            pillar_a = PillarScore(
                pillar_name="Evidence Weight (Pillar A)",
                score=1.0,
                reasoning="Local system time check matched the claim (override).",
                overrides_others=True,
            )
        else:
            pillar_a = _evaluate_pillar_a_evidence_weight(story, evidence)
        
        # Pillar B: Narrative Diversity
        pillar_b = _evaluate_pillar_b_narrative_diversity(story, evidence)
        
        # Pillar C: Entity History (with optional deep check)
        historical_context = None
        deep_check_performed = False
        
        # Trigger deep check if controversial or conflicting signals
        try:
            deep_check_performed, historical_context = _perform_deep_check(
                story, evidence, api_key, cse_id
            )
        except Exception:
            historical_context = None
            deep_check_performed = False
        
        pillar_c = _evaluate_pillar_c_entity_history(story, historical_context)
        
        # Aggregate pillars into final HFIS score
        hfis_result = _aggregate_hfis_pillars(pillar_a, pillar_b, pillar_c)
        hfis_result.deep_check_performed = deep_check_performed
        hfis_result.historical_context = historical_context.get("person_history", "") if historical_context else ""

        verification_depth_score, verification_depth_reason = _verification_depth_metrics(evidence)
        semantic_score, semantic_reason = _semantic_consistency_metrics(story, evidence)
        triplet_score, triplet_reason = _triplet_consistency_metrics(story, evidence)
        temporal_score, temporal_reason = _temporal_consistency_metrics(story, evidence)
        sensationalism_score, sensationalism_reason = _stylometric_sensationalism_metrics(story)

        depth_factor = 0.75 + (0.25 * verification_depth_score)
        semantic_factor = 0.85 + (0.15 * semantic_score)
        triplet_factor = 0.80 + (0.20 * triplet_score)
        temporal_factor = 0.80 + (0.20 * temporal_score)
        sensationalism_factor = 1.0 - (0.35 * sensationalism_score)

        base_score = hfis_result.final_score
        adjusted_score = max(
            0.0,
            min(
                1.0,
                base_score
                * depth_factor
                * semantic_factor
                * triplet_factor
                * temporal_factor
                * sensationalism_factor,
            ),
        )
        hfis_result.final_score = adjusted_score

        if verification_depth_score < 0.35 and "low_verification_depth" not in red_flags:
            red_flags.append("low_verification_depth")
        if sensationalism_score >= 0.65 and "sensationalism" not in red_flags:
            red_flags.append("sensationalism")
        if semantic_score < 0.35 and "semantic_contradiction" not in red_flags:
            red_flags.append("semantic_contradiction")
        if triplet_score < 0.35 and "triplet_contradiction" not in red_flags:
            red_flags.append("triplet_contradiction")
        if temporal_score < 0.40 and "temporal_risk" not in red_flags:
            red_flags.append("temporal_risk")
        
        # Determine verdict using HFIS
        verdict, verdict_reason = _verdict_from_hfis(hfis_result, red_flags)
        
        # Determine confidence level
        if hfis_result.override_applied:
            confidence_level = "high"
        elif hfis_result.final_score >= 0.75:
            confidence_level = "high"
        elif hfis_result.final_score >= 0.55:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        # Generate detailed reasoning combining all pillars
        detailed_reason = (
            f"\n[Pillar A - Evidence Weight: {hfis_result.evidence_pillar.score:.2f}] "
            f"{hfis_result.evidence_pillar.reasoning}"
            f"\n[Pillar B - Narrative Diversity: {hfis_result.narrative_pillar.score:.2f}] "
            f"{hfis_result.narrative_pillar.reasoning}"
            f"\n[Pillar C - Entity History: {hfis_result.history_pillar.score:.2f}] "
            f"{hfis_result.history_pillar.reasoning}"
            f"\n[HFIS Final Score: {hfis_result.final_score:.2f}]"
            f"\n[Verification Depth: {verification_depth_score:.2f}] {verification_depth_reason}"
            f"\n[Semantic Consistency: {semantic_score:.2f}] {semantic_reason}"
            f"\n[Triplet Consistency: {triplet_score:.2f}] {triplet_reason}"
            f"\n[Temporal Consistency: {temporal_score:.2f}] {temporal_reason}"
            f"\n[Sensationalism Risk: {sensationalism_score:.2f}] {sensationalism_reason}"
            f"\n[Score Adjustment: base {base_score:.2f} x depth {depth_factor:.2f} x semantic {semantic_factor:.2f} x triplet {triplet_factor:.2f} x temporal {temporal_factor:.2f} x sensationalism {sensationalism_factor:.2f}]"
        )
        
        if hfis_result.override_applied:
            detailed_reason += "\n[OVERRIDE APPLIED - Evidence Pillar dominates]"
        
        if deep_check_performed:
            detailed_reason += f"\n[Deep Check Performed - Historical context analyzed]"
        
        verdicts.append(
            StoryVerdict(
                story=story,
                score=hfis_result.final_score,
                verdict=verdict,
                key_claim=claim,
                reason=verdict_reason + detailed_reason,
                evidence=evidence,
                confidence_level=confidence_level,
                red_flags=red_flags,
                fuzzy_score=hfis_result.final_score,
            )
        )
    
    return verdicts
