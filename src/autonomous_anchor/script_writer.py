from __future__ import annotations

from datetime import datetime
from typing import List

from .brain import BrainConfig, reason_about_verdict
from .models import StoryVerdict



def _roast_line(verdict: StoryVerdict, style: str) -> str:
    if verdict.roast_line:
        return verdict.roast_line

    if verdict.verdict == "verified":
        return "This one checks out. Facts are aligned, no drama needed."

    if verdict.verdict == "uncertain":
        return "The evidence is mixed. Treat this like a rumor until stronger proof lands."

    if style == "savage":
        return "Big claim, zero backbone. The facts body this headline before it even reaches the timeline."
    if style == "sharp":
        return "Cute headline. Unfortunately, the evidence did not get the memo. This claim collapses under verification, so treat it as noise, not news."
    if style == "blunt":
        return "Evidence does not support this claim. Treat it as misinformation until credible proof appears."
    return "The claim is weakly supported and should not be treated as reliable."



def build_news_minute_script(
    verdicts: List[StoryVerdict],
    style: str = "sharp",
    groq_api_key: str = "",
    groq_model: str = "llama-3.1-70b-versatile",
) -> str:
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    lines: List[str] = [
        f"News Minute. Timestamp: {now}.",
        "We cross-checked incoming headlines with external sources before speaking.",
    ]

    if not verdicts:
        lines.append("No fresh stories were available in the configured window.")
        lines.append("We will re-check on the next cycle.")
        return "\n".join(lines)

    cfg = BrainConfig(groq_api_key=groq_api_key, groq_model=groq_model, roast_style=style)
    for idx, v in enumerate(verdicts, start=1):
        reasoning = reason_about_verdict(verdict=v, cfg=cfg)
        v.truth_score = int(reasoning.get("truth_score", round(v.score * 100)))
        v.reason = str(reasoning.get("reason", v.reason))
        v.roast_line = str(reasoning.get("roast_line", _roast_line(v, style=style)))

        lines.append(f"Story {idx}: {v.story.title}")
        lines.append(
            f"Verdict: {v.verdict.upper()} with confidence {v.score:.2f}"
            f" and Truth Score {v.truth_score}/100"
            f" based on {len(v.evidence)} supporting sources."
        )
        lines.append(f"Reason: {v.reason}")
        lines.append(_roast_line(v, style=style))

    lines.append("Truth over virality. Verify before you amplify.")
    return "\n".join(lines)
