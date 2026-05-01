from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)


if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS


W, H = 1080, 1920
SAFE_X = 56

FONT_PATHS = [
    "Syne-Bold.ttf",
    "Oswald-Bold.ttf",
    "BebasNeue-Regular.ttf",
    "arial.ttf",
    "DejaVuSans-Bold.ttf",
]

BODY_FONT_PATHS = [
    "Inter-Regular.ttf",
    "NotoSans-Regular.ttf",
    "DejaVuSans.ttf",
    "arial.ttf",
]


def _load_font(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


_VERDICT_STYLES = {
    "verified": ((47, 208, 131), (47, 208, 131, 190), "✓ VERIFIED"),
    "uncertain": ((255, 184, 48), (255, 184, 48, 190), "? UNCERTAIN"),
    "likely_fake": ((255, 95, 86), (255, 95, 86, 190), "✗ LIKELY FAKE"),
    "no_data": ((180, 180, 200), (180, 180, 200, 160), "• NO DATA"),
}


def _verdict_meta(verdict: str) -> tuple[tuple[int, int, int], tuple[int, int, int, int], str]:
    return _VERDICT_STYLES.get(verdict, _VERDICT_STYLES["no_data"])


def _dark_bg_clip(duration: float) -> ImageClip:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(6 + t * 8)
        g = int(9 + t * 12)
        b = int(16 + t * 22)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, 4, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return ImageClip(arr).set_duration(duration)


def _vignette_overlay(duration: float) -> ImageClip:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(120):
        alpha = int((i / 120) ** 2 * 175)
        draw.rectangle([i, i, W - i, H - i], outline=(0, 0, 0, alpha))
    return ImageClip(np.array(img)).set_duration(duration)


def _slideshow_layer(image_assets: List[Path], duration: float) -> ImageClip:
    if not image_assets:
        return _dark_bg_clip(duration)

    each = max(3.0, duration / max(1, len(image_assets)))
    clips = []
    for asset in image_assets:
        try:
            base = (
                ImageClip(str(asset))
                .resize(height=H)
                .set_position("center")
                .set_duration(each)
                .crossfadein(0.35)
            )
            dim = ColorClip(size=(W, H), color=(0, 0, 0)).set_opacity(0.42).set_duration(each)
            clips.append(CompositeVideoClip([base, dim]).set_duration(each))
        except Exception:
            clips.append(_dark_bg_clip(each))

    return concatenate_videoclips(clips, method="compose").set_duration(duration)


def _text_image(
    text: str,
    size: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int, int],
    line_spacing_extra: int = 8,
    shadow: bool = False,
) -> np.ndarray:
    width, height = size
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_chars = max(14, int(width / max(8, font.size * 0.52)))
    lines: List[str] = []
    for para in (text.splitlines() or [text]):
        lines.extend(textwrap.wrap(para, width=max_chars) or [""])

    y = 0
    for line in lines:
        if y >= height:
            break
        bbox = draw.textbbox((0, 0), line or " ", font=font)
        line_height = max(1, bbox[3] - bbox[1])
        if shadow:
            draw.text((3, y + 3), line, font=font, fill=(0, 0, 0, 120))
        draw.text((0, y), line, font=font, fill=color)
        y += line_height + line_spacing_extra

    return np.array(img)


def _scrolling_caption_clip(script_lines: List[str], duration: float) -> ImageClip:
    caption_lines = []
    for raw_line in script_lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("News Minute"):
            continue
        caption_lines.append(line)

    if not caption_lines:
        caption_lines = ["Truth over virality.", "Verify before you amplify."]

    caption_text = "\n".join(caption_lines)
    width = W - SAFE_X * 2
    height = max(420, min(1180, 170 + len(caption_lines) * 82))
    font = _load_font(BODY_FONT_PATHS, 34)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1],
        radius=26,
        fill=(5, 9, 16, 190),
        outline=(255, 255, 255, 40),
        width=1,
    )

    y = 22
    for line in caption_text.splitlines():
        wrapped = textwrap.wrap(line, width=30) or [""]
        for chunk in wrapped:
            draw.text((22, y), chunk, font=font, fill=(244, 247, 255, 228))
            bbox = draw.textbbox((22, y), chunk, font=font)
            y += (bbox[3] - bbox[1]) + 12
        y += 4

    clip = ImageClip(np.array(img)).set_duration(duration)
    travel = max(260, height + 200)
    start_y = H - 230
    end_y = H - 230 - travel
    return clip.set_position(lambda t: (SAFE_X, start_y - (start_y - end_y) * (t / max(duration, 0.1))))


def _top_bar_clip(duration: float) -> ImageClip:
    img = Image.new("RGBA", (W, 108), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 108], fill=(8, 10, 17, 214))

    title_font = _load_font(FONT_PATHS, 46)
    label_font = _load_font(BODY_FONT_PATHS, 22)

    draw.text((SAFE_X, 18), "MOCKR", font=title_font, fill=(47, 208, 131, 255))
    draw.text((SAFE_X + 146, 30), "REALITY CHECK", font=label_font, fill=(255, 255, 255, 170))

    live_x = W - SAFE_X - 68
    draw.ellipse([live_x, 42, live_x + 14, 56], fill=(255, 95, 86, 255))
    draw.text((live_x + 22, 24), "LIVE", font=label_font, fill=(255, 95, 86, 255))

    return ImageClip(np.array(img)).set_duration(duration).set_position((0, 0))


def _score_bar_clip(score: int, verdict: str, duration: float) -> ImageClip:
    rgb, _, _ = _verdict_meta(verdict)
    bw, bh = W - SAFE_X * 2, 16
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=8, fill=(255, 255, 255, 35))
    fill_w = int(max(0, min(1.0, score / 100)) * bw)
    if fill_w > 0:
        draw.rounded_rectangle([0, 0, fill_w - 1, bh - 1], radius=8, fill=(*rgb, 230))

    return ImageClip(np.array(img)).set_duration(duration).set_position((SAFE_X, 1765))


def _verdict_badge_clip(verdict: str, score: int, duration: float) -> ImageClip:
    rgb, _, label = _verdict_meta(verdict)
    bw, bh = 520, 74
    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [0, 0, bw - 1, bh - 1],
        radius=37,
        fill=(rgb[0], rgb[1], rgb[2], 36),
        outline=(rgb[0], rgb[1], rgb[2], 175),
        width=2,
    )

    font = _load_font(FONT_PATHS, 30)
    draw.text((22, 20), label, font=font, fill=(*rgb, 255))
    score_font = _load_font(BODY_FONT_PATHS, 24)
    draw.text((bw - 96, 22), f"{score}/100", font=score_font, fill=(255, 255, 255, 215))

    return ImageClip(np.array(img)).set_duration(duration).set_position((SAFE_X, 1680))


def _body_text_clip(script_lines: List[str], score: int, verdict: str, duration: float) -> ImageClip:
    rgb, _, _ = _verdict_meta(verdict)
    bw = W - SAFE_X * 2
    bh = 1550

    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    story_line = next((l for l in script_lines if l.startswith("Story")), "")
    headline = story_line.replace("Story 1:", "").strip() if story_line else ""
    reason_line = next((l for l in script_lines if l.startswith("Reason:")), "")
    reason_text = reason_line.replace("Reason:", "").strip() if reason_line else ""

    headline_font = _load_font(FONT_PATHS, 66)
    score_font = _load_font(FONT_PATHS, 122)
    body_font = _load_font(BODY_FONT_PATHS, 38)
    label_font = _load_font(BODY_FONT_PATHS, 30)

    y = 0
    draw.text((0, y), f"{score}", font=score_font, fill=(*rgb, 230))
    draw.text((78, y + 68), "/100", font=body_font, fill=(255, 255, 255, 120))
    y += 132

    draw.line([(0, y), (bw, y)], fill=(*rgb, 80), width=2)
    y += 22

    if headline:
        for hl in textwrap.wrap(headline, width=22)[:4]:
            if y >= bh - 80:
                break
            draw.text((0, y), hl, font=headline_font, fill=(255, 255, 255, 245))
            bbox = draw.textbbox((0, y), hl, font=headline_font)
            y += (bbox[3] - bbox[1]) + 10
        y += 18

    if reason_text:
        draw.line([(0, y), (bw, y)], fill=(255, 255, 255, 30), width=1)
        y += 18
        draw.text((0, y), "WHY", font=label_font, fill=(*rgb, 210))
        y += 40
        for rl in textwrap.wrap(reason_text, width=32)[:4]:
            if y >= bh - 60:
                break
            draw.text((0, y), rl, font=body_font, fill=(225, 232, 248, 210))
            bbox = draw.textbbox((0, y), rl, font=body_font)
            y += (bbox[3] - bbox[1]) + 8

    return ImageClip(np.array(img)).set_duration(duration).set_position((SAFE_X, 108))


def _story_context(script_lines: List[str]) -> tuple[str, str, str]:
    story_line = next((l for l in script_lines if l.startswith("Story")), "")
    headline = story_line.split(":", 1)[1].strip() if ":" in story_line else ""

    reason_line = next((l for l in script_lines if l.startswith("Reason:")), "")
    reason = reason_line.replace("Reason:", "", 1).strip() if reason_line else ""

    roast = ""
    for line in script_lines:
        text = line.strip()
        if not text:
            continue
        if text.startswith(("News Minute", "We cross-checked", "Story", "Verdict:", "Reason:")):
            continue
        if text.startswith("Truth over virality"):
            continue
        roast = text

    return headline, reason, roast


def _panel_clip(
    *,
    title: str,
    body: str,
    accent_rgb: tuple[int, int, int],
    duration: float,
    start: float,
    width: int,
    height: int,
    position: tuple[int, int],
) -> ImageClip:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1],
        radius=28,
        fill=(8, 12, 20, 168),
        outline=(accent_rgb[0], accent_rgb[1], accent_rgb[2], 160),
        width=2,
    )

    title_font = _load_font(FONT_PATHS, 34)
    body_font = _load_font(BODY_FONT_PATHS, 48)

    draw.text((34, 26), title, font=title_font, fill=(*accent_rgb, 245))
    draw.line([(34, 78), (width - 34, 78)], fill=(*accent_rgb, 120), width=2)

    y = 98
    for line in textwrap.wrap(body, width=28)[:4]:
        draw.text((34, y), line, font=body_font, fill=(240, 247, 255, 245))
        bbox = draw.textbbox((34, y), line, font=body_font)
        y += (bbox[3] - bbox[1]) + 8

    return (
        ImageClip(np.array(img))
        .set_start(start)
        .set_duration(duration)
        .set_position(position)
        .crossfadein(0.22)
        .crossfadeout(0.22)
    )


def _phased_text_clips(script_lines: List[str], score: int, verdict: str, duration: float) -> List[ImageClip]:
    rgb, _, label = _verdict_meta(verdict)
    headline, reason, roast = _story_context(script_lines)

    intro = f"{label} | Truth Score {score}/100"
    headline_text = headline or "Breaking story update from the latest news cycle."
    reason_text = reason or "Evidence is still developing; verify independently before sharing."
    roast_text = roast or "Truth over virality. Verify before you amplify."

    # Short, overlapping phases create a more polished editorial rhythm.
    p1 = min(2.4, max(1.8, duration * 0.18))
    p2 = min(3.4, max(2.4, duration * 0.24))
    p3 = min(3.8, max(2.6, duration * 0.26))
    p4 = min(3.2, max(2.2, duration * 0.2))

    t1 = 0.45
    t2 = t1 + p1 * 0.8
    t3 = t2 + p2 * 0.84
    t4 = t3 + p3 * 0.84

    width = W - SAFE_X * 2
    return [
        _panel_clip(
            title="REALITY CHECK",
            body=intro,
            accent_rgb=rgb,
            duration=p1,
            start=t1,
            width=width,
            height=280,
            position=(SAFE_X, 330),
        ),
        _panel_clip(
            title="HEADLINE",
            body=headline_text,
            accent_rgb=rgb,
            duration=p2,
            start=t2,
            width=width,
            height=410,
            position=(SAFE_X, 640),
        ),
        _panel_clip(
            title="WHAT WE FOUND",
            body=reason_text,
            accent_rgb=rgb,
            duration=p3,
            start=t3,
            width=width,
            height=430,
            position=(SAFE_X, 880),
        ),
        _panel_clip(
            title="ANCHOR TAKE",
            body=roast_text,
            accent_rgb=rgb,
            duration=p4,
            start=t4,
            width=width,
            height=340,
            position=(SAFE_X, 1410),
        ),
    ]


def _bottom_scrim(duration: float) -> ImageClip:
    img = Image.new("RGBA", (W, 640), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(640):
        alpha = int((y / 640) ** 0.65 * 220)
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return ImageClip(np.array(img)).set_duration(duration).set_position((0, H - 640))


def _top_scrim(duration: float) -> ImageClip:
    img = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(260):
        alpha = int(((260 - y) / 260) ** 0.7 * 140)
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return ImageClip(np.array(img)).set_duration(duration).set_position((0, 0))


def render_news_video(
    script_lines: List[str],
    audio_path: Path,
    out_path: Path,
    image_assets: Optional[List[Path]] = None,
    top_verdict: str = "uncertain",
    top_truth_score: int = 50,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_audio = out_path.parent / f"{out_path.stem}.temp-audio.m4a"

    audio_clip = AudioFileClip(str(audio_path))
    duration = max(10, int(audio_clip.duration) + 1)

    verdict = top_verdict or "uncertain"
    score = int(max(0, min(100, top_truth_score)))

    try:
        bg = _slideshow_layer(image_assets or [], duration=duration)
        phased_text_layers = _phased_text_clips(script_lines, score, verdict, duration)
        layers = [
            bg,
            _top_scrim(duration),
            _bottom_scrim(duration),
            _vignette_overlay(duration),
            _top_bar_clip(duration),
            _verdict_badge_clip(verdict, score, duration),
            _score_bar_clip(score, verdict, duration),
            _scrolling_caption_clip(script_lines, duration),
            *phased_text_layers,
        ]

        video = CompositeVideoClip(layers, size=(W, H)).set_audio(audio_clip)
        video.write_videofile(
            str(out_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(temp_audio),
            remove_temp=False,
            logger=None,
            preset="fast",
        )
        video.close()
    finally:
        audio_clip.close()
        try:
            if temp_audio.exists():
                temp_audio.unlink()
        except Exception:
            pass

    return out_path