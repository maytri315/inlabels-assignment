# Mockr API Integration Guide: Eleven Labs & Hugging Face Priority Setup

## Overview
Updated Mockr to **prioritize Eleven Labs (voice) and Hugging Face (images)** for faster reel generation (2-3 min reels reduced significantly).

---

## Voice Generation Pipeline (Priority Order)

### 1. **Eleven Labs** ⚡ (PRIMARY - Fastest & Most Natural)
- Ultra-fast, professional quality voice generation
- Supports 100+ realistic voices and languages
- Set via environment variables:
  ```
  ELEVENLABS_API_KEY=your_api_key_here
  ELEVENLABS_VOICE_ID=your_voice_id_here
  ```

### 2. **MeloTTS** (Fallback - High Quality)
- Open-source, runs locally on CPU
- High-quality neutral voice
- Automatic fallback if Eleven Labs fails

### 3. **Edge TTS** (Fallback - Free)
- Microsoft's free text-to-speech
- No API key required
- Fallback if previous options fail

### 4. **gTTS** (Fallback - Last Resort)
- Google's free TTS
- Backup if all else fails

---

## Image Generation Pipeline (Priority Order)

### 1. **Hugging Face SDXL** 🎨 (PRIMARY - Fastest & Varied)
- Stable Diffusion XL from Hugging Face Inference API
- Wide variety of styles (editorial, documentary, cinematic)
- Set via environment variables:
  ```
  HF_API_KEY=your_huggingface_api_key
  HF_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0
  ```

### 2. **Pollinations.ai** (Fallback - Alternative AI)
- Fast image generation service
- Fallback if Hugging Face fails/times out
- No API key required (but rate-limited)

### 3. **Wikimedia Commons** (Fallback - Real Images)
- Real, free image database
- Better accuracy for specific topics
- Automatic fallback search

### 4. **Placeholder Images** (Last Resort)
- Generated with headline text
- Fallback if all services fail

---

## Environment Setup

### Create `.env` file in project root:

```bash
# Google API (for fact-checking)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_cse_id

# Groq API (for script generation)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-70b-versatile

# NEWS FEED
NEWS_FEED_URL=https://news.google.com/rss/search?q=Lucknow&hl=en-IN&gl=IN&ceid=IN:en
OUTPUT_DIR=./output
MAX_STORIES=4
LOOKBACK_HOURS=4

# VOICE GENERATION (Eleven Labs Priority)
ELEVENLABS_API_KEY=sk-your_elevenlabs_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Example voice ID
VOICE_LANG=en-US

# Edge TTS Fallback
EDGE_TTS_VOICE=en-US-AriaNeural
EDGE_TTS_RATE=+15%

# IMAGE GENERATION (Hugging Face Priority)
HF_API_KEY=hf_your_huggingface_api_key_here
HF_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0

# Pollinations Fallback (Optional - auto rate-limited)
POLLINATIONS_BASE_URL=https://image.pollinations.ai

# Generation Style
ROAST_STYLE=sharp  # Options: measured, sharp, blunt, savage
```

---

## Getting API Keys

### 1. **Eleven Labs** (Voice)
- Go to: https://elevenlabs.io/
- Sign up for free account (free tier: 10,000 characters/month)
- Get API key from: Settings → Account → API Key
- Choose a voice ID from: https://elevenlabs.io/docs/api/get-voices
- Popular voice IDs:
  - `21m00Tcm4TlvDq8ikWAM` - Rachel (professional female)
  - `EXAVITQu4vr4xnSDxMaL` - Bella (engaging female)
  - `TxGEqnHWrfWFTfGW9XjX` - James (professional male)

### 2. **Hugging Face** (Image Generation)
- Go to: https://huggingface.co/
- Sign up for free account
- Get API key from: Settings → Access Tokens → New Token (read-only fine)
- Enable serverless inference:
  - Go to: https://huggingface.co/spaces/new?template=default
  - Browse models: https://huggingface.co/models?library=diffusers
- Popular SDXL models:
  - `stabilityai/stable-diffusion-xl-base-1.0` (recommended - balanced)
  - `stabilityai/stable-diffusion-3-medium` (newer, better quality)

### 3. **Google API** (Fact-Checking)
- Go to: https://console.cloud.google.com/
- Create project → Enable Custom Search API
- Create API key and Custom Search Engine ID
- Config: https://programmablesearchengine.google.com/

### 4. **Groq API** (Script Generation)
- Go to: https://groq.com/
- Sign up and get API key
- Free tier: 10K requests/day

---

## Performance Improvements

### Before Changes
- Voice: MeloTTS → Eleven Labs (Melo takes time)
- Images: Wikimedia → Pollinations (Pollinations: 2-3 min per image)
- **Total: ~2-3 min per reel**

### After Changes ✅
- Voice: Eleven Labs (0.5-1 sec) → MeloTTS (fallback)
- Images: Hugging Face (1-2 min total) → Pollinations (fallback)
- **Expected: ~1-2 min per reel**

---

## Quick Test

### Test Voice Generation
```bash
python -c "
from src.autonomous_anchor.voiceover import synthesize_voiceover
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
audio = synthesize_voiceover(
    'Test voice synthesis with Eleven Labs',
    Path('test_audio.wav'),
    elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
    elevenlabs_voice_id=os.getenv('ELEVENLABS_VOICE_ID'),
)
print(f'✓ Audio created: {audio}')
"
```

### Test Image Generation
```bash
python -c "
from src.autonomous_anchor.visual_assets import _hf_sdxl_image
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
image_bytes = _hf_sdxl_image(
    'Breaking news announcement in modern news studio',
    hf_api_key=os.getenv('HF_API_KEY'),
)
if image_bytes:
    Path('test_image.png').write_bytes(image_bytes)
    print(f'✓ Image created: test_image.png')
else:
    print('✗ Image generation failed')
"
```

---

## Troubleshooting

### Voice Takes Too Long
- ✅ Ensure `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are set in `.env`
- Check logs for fallback reason
- MeloTTS CPU inference ~10-20 sec is normal

### Images Take Too Long
- ✅ Ensure `HF_API_KEY` is set and has serverless inference enabled
- Check logs for "HF Inference returned 404" (need to enable endpoint)
- Pollinations fallback will try if HF fails

### "HF Inference returned 404"
- Problem: Hugging Face account doesn't have serverless inference enabled
- Solution:
  1. Go to https://huggingface.co/settings/billing/subscription
  2. Ensure you have **Inference Endpoints** access or **Pro subscription**
  3. For free users: Enable via https://huggingface.co/spaces/

### API Rate Limiting
- Eleven Labs: 10,000 chars/month free (upgrade for more)
- Hugging Face: Free tier has rate limits
- Pollinations: Auto-retries with exponential backoff
- Wikimedia: Free unlimited (but slower)

---

## Code Changes Summary

### `voiceover.py` (Priority Updated)
```
OLD: MeloTTS → Eleven Labs → Edge TTS → gTTS
NEW: Eleven Labs → MeloTTS → Edge TTS → gTTS ⚡
```

### `visual_assets.py` (Priority Updated)
```
OLD: Wikimedia → Pollinations → Placeholder
NEW: Hugging Face → Pollinations → Wikimedia → Placeholder ⚡
```

Both now prioritize the fastest services first!

---

## Next Steps

1. **Get API Keys**:
   - Eleven Labs: https://elevenlabs.io/
   - Hugging Face: https://huggingface.co/

2. **Update `.env` file** with your keys

3. **Test generation**:
   ```bash
   cd backend
   python manage.py runserver
   # Open http://localhost:8000
   # Click "Run" to generate a reel
   ```

4. **Monitor Performance**:
   - Check logs for timing information
   - Expected: 1-2 min per reel

---

## API Cost Estimates

### Eleven Labs (Voice)
- Free: 10,000 characters/month (~4-5 reels)
- Pro: $99/month for unlimited

### Hugging Face (Images)
- Free: Rate-limited but no cost
- Pro: $9/month for priority inference

### Combined Estimate
- **Free tier**: ~$0/month (limited to 4-5 reels/month)
- **Basic paid**: ~$50-100/month for production use

---

## Fallback Chain Logic

If any service fails, system automatically tries next option:

```
Voice: ElevenLabs
  ↓ (timeout/error)
MeloTTS
  ↓ (missing/error)  
Edge TTS
  ↓ (failure)
gTTS (always works)

Images: Hugging Face
  ↓ (timeout/error)
Pollinations
  ↓ (timeout/error)
Wikimedia
  ↓ (not found)
Placeholder (always works)
```

All services have retry logic with exponential backoff!
