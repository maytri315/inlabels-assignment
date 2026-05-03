from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict

from .models import StoryVerdict


@dataclass
class BrainConfig:
    groq_api_key: str
    groq_model: str
    roast_style: str


class BrainState(dict):
    pass


def _fallback_reasoning(verdict: StoryVerdict, style: str) -> Dict[str, Any]:
    truth_score = int(max(1, min(100, round(verdict.score * 100))))
    if verdict.verdict == "verified":
        roast = "Receipts check out. This claim survives cross-check mode."
    elif verdict.verdict == "uncertain":
        roast = "Not enough proof yet. Put this claim in the rumor parking lot."
    elif style == "savage":
        roast = "This claim came with hype, not homework. Evidence shreds it on arrival."
    elif style == "blunt":
        roast = "Fake-news energy detected. Evidence says this falls apart fast."
    elif style == "sharp":
        roast = "This headline is all confidence, no evidence. Truth mode wins."
    else:
        roast = "Weak evidence. Verify before sharing."

    return {
        "truth_score": truth_score,
        "reason": verdict.reason,
        "roast_line": roast,
    }


def reason_about_verdict(verdict: StoryVerdict, cfg: BrainConfig) -> Dict[str, Any]:
    if not cfg.groq_api_key:
        return _fallback_reasoning(verdict=verdict, style=cfg.roast_style)

    try:
        from langgraph.graph import END, StateGraph
        from groq import Groq
        from groq import APIStatusError, RateLimitError
    except Exception:
        return _fallback_reasoning(verdict=verdict, style=cfg.roast_style)

    client = Groq(api_key=cfg.groq_api_key)

    evidence_blob = "\n".join(
        [f"- {e.title} | {e.source} | {e.link}" for e in verdict.evidence[:5]]
    )

    prompt = (
        "You are Mockr's Truth Auditor. Return only strict JSON with keys "
        "truth_score (1-100 int), reason (string <= 180 chars), roast_line (string <= 140 chars). "
        "Roast line must criticize claim quality, not protected groups or personal abuse.\n"
        f"Claim: {verdict.key_claim}\n"
        f"Current verdict: {verdict.verdict}\n"
        f"Heuristic score: {verdict.score:.2f}\n"
        f"Style: {cfg.roast_style}\n"
        f"Evidence:\n{evidence_blob if evidence_blob else '- none'}"
    )

    def _is_rate_limited(error: Exception) -> bool:
        if isinstance(error, RateLimitError):
            return True
        if isinstance(error, APIStatusError):
            return getattr(error, "status_code", None) == 429
        return False

    def _retry_delay_seconds(error: Exception, attempt: int) -> float:
        delay = min(8.0, float(2 ** (attempt - 1)))
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if headers:
            retry_after = headers.get("retry-after")
            if retry_after:
                try:
                    delay = min(8.0, max(delay, float(retry_after)))
                except (TypeError, ValueError):
                    pass
        return delay

    def llm_node(state: BrainState) -> BrainState:
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                completion = client.chat.completions.create(
                    model=cfg.groq_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Return strict JSON only. No markdown.",
                        },
                        {
                            "role": "user",
                            "content": state["prompt"],
                        },
                    ],
                    temperature=0.2,
                )
                content = completion.choices[0].message.content or "{}"
                state["raw"] = content
                return state
            except Exception as error:
                last_error = error
                if not _is_rate_limited(error) or attempt == 3:
                    raise
                time.sleep(_retry_delay_seconds(error, attempt))

        if last_error is not None:
            raise last_error

        return state

    def parse_node(state: BrainState) -> BrainState:
        text = state.get("raw", "{}").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            state["parsed"] = _fallback_reasoning(verdict=verdict, style=cfg.roast_style)
            return state

        payload = json.loads(text[start : end + 1])
        truth_score = int(max(1, min(100, int(payload.get("truth_score", round(verdict.score * 100))))))
        reason = str(payload.get("reason", verdict.reason)).strip()[:180]
        roast_line = str(payload.get("roast_line", "Verify before sharing.")).strip()[:140]
        state["parsed"] = {
            "truth_score": truth_score,
            "reason": reason,
            "roast_line": roast_line,
        }
        return state

    graph = StateGraph(BrainState)
    graph.add_node("llm", llm_node)
    graph.add_node("parse", parse_node)
    graph.set_entry_point("llm")
    graph.add_edge("llm", "parse")
    graph.add_edge("parse", END)

    app = graph.compile()
    try:
        final_state = app.invoke({"prompt": prompt})
        return final_state.get("parsed") or _fallback_reasoning(verdict=verdict, style=cfg.roast_style)
    except Exception:
        return _fallback_reasoning(verdict=verdict, style=cfg.roast_style)
