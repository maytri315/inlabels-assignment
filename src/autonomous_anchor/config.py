from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    google_cse_id: str
    groq_api_key: str
    groq_model: str
    news_feed_url: str
    output_dir: str
    max_stories: int
    lookback_hours: int
    roast_style: str
    voice_lang: str
    edge_voice: str
    edge_rate: str
    pollinations_base_url: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    hf_api_key: str
    hf_image_model: str



def load_settings() -> Settings:
    default_output_dir = str(Path(__file__).resolve().parents[2] / "output")
    return Settings(
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        google_cse_id=os.getenv("GOOGLE_CSE_ID", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
        news_feed_url=os.getenv(
            "NEWS_FEED_URL",
            "https://news.google.com/rss/search?q=Lucknow&hl=en-IN&gl=IN&ceid=IN:en",
        ),
        output_dir=os.getenv("OUTPUT_DIR", default_output_dir),
        max_stories=int(os.getenv("MAX_STORIES", "4")),
        lookback_hours=int(os.getenv("LOOKBACK_HOURS", "4")),
        roast_style=os.getenv("ROAST_STYLE", "sharp"),
        voice_lang=os.getenv("VOICE_LANG", "en-US"),
        edge_voice=os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural"),
        edge_rate=os.getenv("EDGE_TTS_RATE", "+15%"),
        pollinations_base_url=os.getenv("POLLINATIONS_BASE_URL", "https://image.pollinations.ai"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
        hf_api_key=os.getenv("HF_API_KEY", ""),
        hf_image_model=os.getenv("HF_IMAGE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0"),
    )
