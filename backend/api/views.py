from __future__ import annotations

import mimetypes
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import uuid

from django.db import OperationalError
from django.http import FileResponse, Http404
from django.http.response import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from autonomous_anchor.config import load_settings
from autonomous_anchor.feed import latest_feed_cards
from autonomous_anchor.models import RawStory
from autonomous_anchor.crosscheck import cross_check_stories
from autonomous_anchor.pipeline import category_folder_name, run_anchor_cycle
from .models import UserPreferences, NewsVerdict


DEFAULT_CATEGORIES = ["general", "entertainment", "tech", "political", "sports", "business", "science"]
DEFAULT_PREFERRED_CATEGORIES = DEFAULT_CATEGORIES
LEGACY_DEFAULT_PREFERRED_CATEGORIES = ["general", "entertainment", "tech", "political"]


def _normalized_categories(values) -> list[str]:
    normalized = []
    seen = set()
    for raw in values or []:
        category = category_folder_name(str(raw or "").strip().lower())
        if not category or category in seen:
            continue
        seen.add(category)
        normalized.append(category)
    return normalized


def frontend_view(request):
    root = Path(__file__).resolve().parents[2]
    index_path = root / "frontend" / "index.html"
    if not index_path.exists():
        raise Http404("Frontend not found")
    return HttpResponse(index_path.read_text(encoding="utf-8"))


@api_view(["GET"])
def health_view(request):
    return Response({"status": "ok", "service": "mockr-backend"})


@api_view(["POST"])
def run_cycle_view(request):
    settings = load_settings()
    roast_style = str(request.data.get("roast_style", "")).strip().lower() if request.data else ""
    if roast_style in {"measured", "sharp", "blunt", "savage"}:
        settings = replace(settings, roast_style=roast_style)

    preferred_categories = None
    preferred_bucket = None
    requested_categories = _normalized_categories(request.data.get("preferred_categories", [])) if request.data else []
    requested_bucket = category_folder_name(str(request.data.get("force_bucket", "")).strip()) if request.data and request.data.get("force_bucket") else ""

    if requested_categories:
        preferred_categories = requested_categories
    if requested_bucket:
        preferred_bucket = requested_bucket

    session_id = str(request.data.get("session_id", "")).strip() if request.data else ""
    if session_id and not preferred_categories:
        try:
            prefs = UserPreferences.objects.get(session_id=session_id)
            preferred_categories = list(prefs.preferred_categories or [])
            normalized = _normalized_categories(preferred_categories)
            if normalized and not preferred_bucket:
                preferred_bucket = normalized[0]
        except (UserPreferences.DoesNotExist, OperationalError):
            preferred_categories = None

    package = run_anchor_cycle(
        settings,
        preferred_categories=preferred_categories,
        force_personalization_bucket=preferred_bucket,
    )
    return Response(
        {
            "run_id": package.run_id,
            "script_path": package.script_path,
            "audio_path": package.audio_path,
            "video_path": package.video_path,
            "verdicts_path": package.verdicts_path,
            "reel_path": package.reel_path,
        }
    )


@api_view(["POST"])
def text_fact_check_view(request):
    settings = load_settings()
    data = request.data if request.data else {}
    text = str(data.get("text", data.get("claim", "")) or "").strip()

    if not text:
        return Response({"error": "text is required"}, status=400)

    title = " ".join(text.split())[:120]
    story = RawStory(
        title=title or "Pasted text",
        summary=text,
        link="https://mockr.local/text-check",
        source="user_submission",
        published_at=datetime.now(timezone.utc),
        category="general",
    )

    verdicts = cross_check_stories(
        stories=[story],
        api_key=settings.google_api_key,
        cse_id=settings.google_cse_id,
    )
    verdict = verdicts[0] if verdicts else None

    evidence = []
    if verdict:
        evidence = [
            {
                "title": ev.title,
                "link": ev.link,
                "source": ev.source,
                "snippet": ev.snippet,
            }
            for ev in verdict.evidence
        ]

    truth_score = int(round((verdict.truth_score if verdict else 0) or 0))
    fake_likelihood = max(0, min(100, 100 - truth_score))

    return Response(
        {
            "checked_text": text,
            "headline": story.title,
            "verdict": verdict.verdict if verdict else "no_data",
            "truth_score": truth_score,
            "fake_likelihood": fake_likelihood,
            "confidence_level": verdict.confidence_level if verdict else "low",
            "reason": verdict.reason if verdict else "No evidence could be gathered for this text.",
            "red_flags": verdict.red_flags if verdict else [],
            "evidence_count": len(evidence),
            "sources": evidence,
        }
    )


@api_view(["GET"])
def feed_view(request):
    settings = load_settings()
    limit = int(request.query_params.get("limit", "20"))
    session_id = request.query_params.get("session_id", "")
    personalized = request.query_params.get("personalized", "0") in {"1", "true", "yes"}
    cards = []

    prefs = None
    if session_id:
        try:
            prefs = UserPreferences.objects.get(session_id=session_id)
            if list(prefs.preferred_categories or []) == LEGACY_DEFAULT_PREFERRED_CATEGORIES:
                prefs.preferred_categories = list(DEFAULT_PREFERRED_CATEGORIES)
                prefs.save(update_fields=["preferred_categories", "updated_at"])
        except (UserPreferences.DoesNotExist, OperationalError):
            prefs = None

    requested_categories = _normalized_categories(
        [part for part in str(request.query_params.get("categories", "")).split(",") if part.strip()]
    )

    categories = []
    if personalized and requested_categories:
        categories = requested_categories
    elif personalized and prefs and prefs.preferred_categories:
        categories = _normalized_categories(prefs.preferred_categories)
    # If personalized but no preferences, categories stays empty to show general root-level content

    cards = latest_feed_cards(
        output_dir=settings.output_dir,
        limit=limit,
        categories=categories,
    )

    base = request.query_params.get("base", "")
    normalized = []
    for card in cards:
        item = card.as_dict()
        # Only apply preference filtering if personalized was requested AND preferences exist with categories
        if personalized and prefs and not _matches_preferences(item, prefs, category_scope=categories):
            continue
        rel = _normalize_output_relative(item["video_path"])
        if rel:
            if base:
                item["video_url"] = _join_base(base, f"api/media/{rel}")
            else:
                item["video_url"] = f"/api/media/{rel}"
        else:
            item["video_url"] = ""
        normalized.append(item)

    return Response({"count": len(normalized), "items": normalized})


def _matches_preferences(item: dict, prefs: UserPreferences, category_scope: list[str] | None = None) -> bool:
    preferred_categories = category_scope if category_scope is not None else _normalized_categories(prefs.preferred_categories)
    category = category_folder_name(str(item.get("top_category", "general") or "general"))
    bucket = category_folder_name(str(item.get("personalization_bucket", "") or ""))
    if preferred_categories and category not in preferred_categories and bucket not in preferred_categories:
        return False

    truth_score = float(item.get("top_truth_score", 0) or 0) / 100.0
    if prefs.filter_by_confidence == "high" and truth_score < 0.8:
        return False
    if prefs.filter_by_confidence == "medium_high" and truth_score < 0.5:
        return False
    if float(prefs.min_confidence_score or 0) > 0 and truth_score < float(prefs.min_confidence_score):
        return False

    red_flags = item.get("top_red_flags", []) or []
    if not prefs.show_red_flags and len(red_flags) > 0:
        return False

    return True


@api_view(["GET"])
def media_view(request, relative_path: str):
    root = Path(load_settings().output_dir).resolve()
    safe_rel = _normalize_output_relative(relative_path)
    target = (root / safe_rel).resolve()
    if root not in target.parents and target != root:
        raise Http404("Invalid path")
    if not target.exists() or not target.is_file():
        raise Http404("File not found")
    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(open(target, "rb"), content_type=content_type)


def _join_base(base: str, path: str) -> str:
    cleaned_base = base.rstrip("/")
    rel = _to_relative(path)
    return f"{cleaned_base}/{rel}"


def _to_relative(path: str) -> str:
    p = Path(path)
    parts = list(p.parts)
    if "output" in parts:
        idx = parts.index("output")
        return "/".join(parts[idx:])
    return str(path).replace("\\", "/")


def _normalize_output_relative(path: str) -> str:
    rel = _to_relative(path)
    if rel.startswith("output/"):
        return rel[len("output/"):]
    if rel == "output":
        return ""
    return rel


# ============================================================================
# PERSONALIZATION ENDPOINTS
# ============================================================================

@api_view(["GET", "POST"])
def user_preferences_view(request):
    """Get or create user preferences based on session."""
    data = request.data if hasattr(request, "data") and request.data else {}

    # Session ID can come from query params or POST body.
    session_id = request.query_params.get("session_id") or data.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    if request.method == "GET":
        try:
            prefs = UserPreferences.objects.get(session_id=session_id)
            return Response({
                "session_id": prefs.session_id,
                "preferred_categories": prefs.preferred_categories,
                "filter_by_confidence": prefs.filter_by_confidence,
                "show_red_flags": prefs.show_red_flags,
                "min_confidence_score": prefs.min_confidence_score,
            })
        except UserPreferences.DoesNotExist:
            try:
                prefs = UserPreferences.objects.create(
                    session_id=session_id,
                    preferred_categories=DEFAULT_CATEGORIES,
                )
                return Response({
                    "session_id": prefs.session_id,
                    "preferred_categories": prefs.preferred_categories,
                    "filter_by_confidence": prefs.filter_by_confidence,
                    "show_red_flags": prefs.show_red_flags,
                    "min_confidence_score": prefs.min_confidence_score,
                })
            except OperationalError:
                return Response(_default_preferences(session_id))
        except OperationalError:
            return Response(_default_preferences(session_id))

    elif request.method == "POST":
        try:
            prefs, _ = UserPreferences.objects.get_or_create(session_id=session_id)

            if "preferred_categories" in data:
                prefs.preferred_categories = data["preferred_categories"]
            if "filter_by_confidence" in data:
                prefs.filter_by_confidence = data["filter_by_confidence"]
            if "show_red_flags" in data:
                prefs.show_red_flags = data["show_red_flags"]
            if "min_confidence_score" in data:
                prefs.min_confidence_score = data["min_confidence_score"]

            prefs.save()

            return Response({
                "session_id": prefs.session_id,
                "preferred_categories": prefs.preferred_categories,
                "filter_by_confidence": prefs.filter_by_confidence,
                "show_red_flags": prefs.show_red_flags,
                "min_confidence_score": prefs.min_confidence_score,
            })
        except OperationalError:
            fallback = _default_preferences(session_id)
            fallback.update(
                {
                    "preferred_categories": data.get("preferred_categories", fallback["preferred_categories"]),
                    "filter_by_confidence": data.get("filter_by_confidence", fallback["filter_by_confidence"]),
                    "show_red_flags": data.get("show_red_flags", fallback["show_red_flags"]),
                    "min_confidence_score": data.get("min_confidence_score", fallback["min_confidence_score"]),
                }
            )
            return Response(fallback)


def _default_preferences(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "preferred_categories": list(DEFAULT_CATEGORIES),
        "filter_by_confidence": "all",
        "show_red_flags": True,
        "min_confidence_score": 0.0,
    }


@api_view(["GET"])
def verdicts_view(request):
    """Get verdicts filtered by user preferences."""
    session_id = request.query_params.get("session_id", "")
    limit = int(request.query_params.get("limit", "20"))
    
    # Get user preferences
    try:
        prefs = UserPreferences.objects.get(session_id=session_id)
    except UserPreferences.DoesNotExist:
        # Default preferences
        prefs = None
    
    # Start with all verdicts
    verdicts = NewsVerdict.objects.all()[:limit]
    
    # Filter by category
    if prefs and prefs.preferred_categories:
        verdicts = verdicts.filter(category__in=prefs.preferred_categories)
    
    # Filter by confidence level
    if prefs:
        if prefs.filter_by_confidence == "high":
            verdicts = verdicts.filter(confidence_level="high")
        elif prefs.filter_by_confidence == "medium_high":
            verdicts = verdicts.filter(confidence_level__in=["medium", "high"])
        
        # Filter by minimum confidence score
        if prefs.min_confidence_score > 0:
            verdicts = verdicts.filter(confidence_score__gte=prefs.min_confidence_score)
    
    # Build response
    results = []
    for v in verdicts:
        result = {
            "id": v.id,
            "headline": v.headline,
            "summary": v.summary,
            "category": v.category,
            "source": v.source,
            "source_link": v.source_link,
            "verdict": v.verdict,
            "confidence_score": v.confidence_score,
            "confidence_level": v.confidence_level,
            "red_flags": v.red_flags if v.red_flags else [],
            "key_claim": v.key_claim,
            "reason": v.reason,
            "evidence_count": v.evidence_count,
        }
        results.append(result)
    
    return Response({
        "count": len(results),
        "items": results,
        "session_id": session_id,
    })


@api_view(["GET"])
def categories_view(request):
    """Get available news categories."""
    categories = {
        "general": "General",
        "entertainment": "Entertainment",
        "tech": "Technology",
        "political": "Political",
        "sports": "Sports",
        "business": "Business",
        "science": "Science",
    }
    return Response({"categories": categories})

