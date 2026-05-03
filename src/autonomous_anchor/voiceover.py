from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import requests
from gtts import gTTS
from edge_tts import Communicate
from moviepy.editor import AudioFileClip


def _to_wav(source_path: Path, target_path: Path) -> Path:
    if source_path.suffix.lower() == ".wav":
        if source_path != target_path:
            target_path.write_bytes(source_path.read_bytes())
        return target_path

    clip = AudioFileClip(str(source_path))
    try:
        clip.write_audiofile(str(target_path), codec="pcm_s16le", verbose=False, logger=None)
    finally:
        clip.close()
    return target_path


def _try_melo_tts(script_text: str, audio_path: Path) -> bool:
    try:
        from melo.api import TTS
    except Exception:
        return False

    try:
        model = TTS(language="EN", device="cpu")
        speaker_ids = model.hps.data.spk2id
        speaker_name = "EN_INDIA" if "EN_INDIA" in speaker_ids else "EN-Default"
        model.tts_to_file(script_text, speaker_ids[speaker_name], str(audio_path), speed=1.0)
        return True
    except Exception:
        return False



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
    wav_path = audio_path.with_suffix(".wav")

    # Priority 1: Eleven Labs (fastest, most natural)
    if elevenlabs_api_key and elevenlabs_voice_id:
        try:
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
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(response.content)
            return _to_wav(temp_path, wav_path)
        except Exception as e:
            import logging
            logging.warning(f"Eleven Labs failed: {e}, falling back to next option")

    # Priority 2: MeloTTS (high quality)
    if _try_melo_tts(script_text, wav_path):
        return wav_path

    # Priority 3: Edge TTS (fast, free)
    try:
        communicate = Communicate(text=script_text, voice=edge_voice, rate=edge_rate)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        asyncio.run(communicate.save(str(temp_path)))
        return _to_wav(temp_path, wav_path)
    except Exception:
        pass

    # Priority 4: gTTS (fallback)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    tts = gTTS(text=script_text, lang=(lang or "en")[:2])
    tts.save(str(temp_path))
    return _to_wav(temp_path, wav_path)
