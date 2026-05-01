from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser

from .models import RawStory



def _to_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _story_key(title: str, link: str) -> str:
    clean_link = (link or "").split("?", 1)[0].strip().lower()
    if clean_link:
        return clean_link
    return " ".join((title or "").lower().split())



def fetch_recent_stories(feed_url: str, lookback_hours: int, max_stories: int) -> List[RawStory]:
    parsed = feedparser.parse(feed_url)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    stories: List[RawStory] = []
    seen: set[str] = set()
    for entry in parsed.entries:
        published_at = _to_dt(getattr(entry, "published", None))
        if published_at < cutoff:
            continue

        title = getattr(entry, "title", "Untitled story").strip()
        link = getattr(entry, "link", "").strip()
        key = _story_key(title=title, link=link)
        if key in seen:
            continue
        seen.add(key)

        stories.append(
            RawStory(
                title=title,
                summary=getattr(entry, "summary", "").strip(),
                link=link,
                source=(getattr(getattr(entry, "source", None), "title", "Unknown")).strip(),
                published_at=published_at,
            )
        )

    stories.sort(key=lambda s: s.published_at, reverse=True)
    return stories[:max_stories]
