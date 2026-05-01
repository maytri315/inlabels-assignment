from __future__ import annotations

import asyncio
from pathlib import Path

import requests
from gtts import gTTS
from edge_tts import Communicate



def synthesize_voiceover(
    script_text: str,
    audio_path: Path,
    lang: str = "en-US",
    edge_voice: str = "en-US-AriaNeural",
    edge_rate: str = "+15%",
    elevenlabs_api_key: str = "",
    elevenlabs_voice_id: str = "",
) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    if elevenlabs_api_key and elevenlabs_voice_id:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": script_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        audio_path.write_bytes(response.content)
        return audio_path

    try:
        communicate = Communicate(text=script_text, voice=edge_voice, rate=edge_rate)
        asyncio.run(communicate.save(str(audio_path)))
        return audio_path
    except Exception:
        tts = gTTS(text=script_text, lang=(lang or "en")[:2])
        tts.save(str(audio_path))
        return audio_path
