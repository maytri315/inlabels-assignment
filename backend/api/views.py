from __future__ import annotations

import mimetypes
from dataclasses import replace
from pathlib import Path

from django.http import FileResponse, Http404
from django.http.response import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from autonomous_anchor.config import load_settings
from autonomous_anchor.feed import latest_feed_cards
from autonomous_anchor.pipeline import run_anchor_cycle


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
    package = run_anchor_cycle(settings)
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


@api_view(["GET"])
def feed_view(request):
    settings = load_settings()
    limit = int(request.query_params.get("limit", "20"))
    cards = latest_feed_cards(output_dir=settings.output_dir, limit=limit)

    base = request.query_params.get("base", "")
    normalized = []
    for card in cards:
        item = card.as_dict()
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
