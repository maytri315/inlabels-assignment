from __future__ import annotations

from typing import List

import requests
from duckduckgo_search import DDGS

from .models import CrossCheckEvidence, RawStory, StoryVerdict


GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"



def _extract_key_claim(story: RawStory) -> str:
    text = f"{story.title}. {story.summary}".strip()
    return " ".join(text.split())[:240]



def _domain(url: str) -> str:
    parts = url.split("/")
    return parts[2].lower() if len(parts) > 2 else "unknown"



def _score_evidence(story: RawStory, evidences: List[CrossCheckEvidence]) -> tuple[float, str]:
    if not evidences:
        return 0.1, "No corroborating coverage from indexed sources."

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

    for ev in evidences:
        ev_tokens = set(ev.title.lower().split())
        if len(title_tokens.intersection(ev_tokens)) >= 3:
            overlap_hits += 1
        dom = _domain(ev.link)
        if any(dom.endswith(rd) for rd in reputable_domains):
            reputable_hits += 1

    score = min(1.0, 0.2 + 0.2 * overlap_hits + 0.2 * reputable_hits)
    if score >= 0.75:
        reason = "Claim is strongly corroborated by multiple sources."
    elif score >= 0.45:
        reason = "Claim has partial corroboration but needs caution."
    else:
        reason = "Claim lacks strong corroboration and may be misleading."
    return score, reason



def _verdict_from_score(score: float) -> str:
    if score >= 0.75:
        return "verified"
    if score >= 0.45:
        return "uncertain"
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
    verdicts: List[StoryVerdict] = []
    for story in stories:
        claim = _extract_key_claim(story)
        evidence: List[CrossCheckEvidence] = []
        try:
            evidence = _duckduckgo_search(query=claim, num=5)
        except Exception:
            evidence = []

        if not evidence and api_key and cse_id:
            try:
                evidence = _google_search(api_key=api_key, cse_id=cse_id, query=claim, num=5)
            except Exception:
                evidence = []

        score, reason = _score_evidence(story, evidence)
        verdicts.append(
            StoryVerdict(
                story=story,
                score=score,
                verdict=_verdict_from_score(score),
                key_claim=claim,
                reason=reason,
                evidence=evidence,
            )
        )
    return verdicts
