# Quick .env Configuration Template

Copy this template and fill in your API keys:

```env
# =====================================
# CORE CONFIGURATION
# =====================================

# Google API (for fact-checking via Google Search)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# Groq API (for AI script generation)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile

# =====================================
# NEWS & OUTPUT SETTINGS
# =====================================

NEWS_FEED_URL=https://news.google.com/rss/search?q=Lucknow&hl=en-IN&gl=IN&ceid=IN:en
OUTPUT_DIR=./output
MAX_STORIES=4
LOOKBACK_HOURS=4
ROAST_STYLE=sharp

# =====================================
# VOICE GENERATION (PRIORITY: 1st)
# =====================================

# Eleven Labs (FASTEST - Recommended)
# Get API Key: https://elevenlabs.io/ → Settings → API Key
# Get Voice ID: https://elevenlabs.io/docs/api/get-voices
ELEVENLABS_API_KEY=sk_your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# Voice Settings
VOICE_LANG=en-US

# Edge TTS (FALLBACK if Eleven Labs fails)
EDGE_TTS_VOICE=en-US-AriaNeural
EDGE_TTS_RATE=+15%

# =====================================
# IMAGE GENERATION (PRIORITY: 1st)
# =====================================

# Hugging Face (FASTEST - Recommended)
# Get API Key: https://huggingface.co/ → Settings → Access Tokens
# Model: stabilityai/stable-diffusion-xl-base-1.0 (recommended)
HF_API_KEY=hf_your_huggingface_api_key_here
HF_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0

# Pollinations (FALLBACK if Hugging Face fails)
POLLINATIONS_BASE_URL=https://image.pollinations.ai
```

## Quick Setup Steps:

### 1. Eleven Labs (Voice)
```bash
# Visit: https://elevenlabs.io/
# 1. Sign up (free tier: 10,000 chars/month)
# 2. Go to Settings → Account → API Key
# 3. Copy your API key into ELEVENLABS_API_KEY
# 4. Visit https://elevenlabs.io/docs/api/get-voices
# 5. Choose a voice, copy its Voice ID into ELEVENLABS_VOICE_ID
```

### 2. Hugging Face (Images)
```bash
# Visit: https://huggingface.co/
# 1. Sign up (free)
# 2. Go to Settings → Access Tokens → New Token
# 3. Create a token with "read" scope
# 4. Copy into HF_API_KEY
# 5. (Optional) Enable serverless inference for better reliability
```

### 3. Google API (Fact-checking)
```bash
# Visit: https://console.cloud.google.com/
# 1. Create a new project
# 2. Enable "Custom Search API"
# 3. Create an API Key (Credentials)
# 4. Create a Custom Search Engine: https://programmablesearchengine.google.com/
# 5. Copy API Key → GOOGLE_API_KEY
# 6. Copy Search Engine ID → GOOGLE_CSE_ID
```

### 4. Groq API (Script Generation)
```bash
# Visit: https://console.groq.com/
# 1. Sign up (free: 10K requests/day)
# 2. Go to API Keys
# 3. Create a new API key
# 4. Copy into GROQ_API_KEY
```

## Voice ID Reference

Popular Eleven Labs voice IDs:
- `21m00Tcm4TlvDq8ikWAM` - Rachel (professional female)
- `EXAVITQu4vr4xnSDxMaL` - Bella (engaging female)
- `TxGEqnHWrfWFTfGW9XjX` - James (professional male)
- `pNInz6obpgDQGcFmaJgB` - Callum (British male)
- `nPczCjzI2devNBz1zQrb` - Josh (casual male)

Full list: https://elevenlabs.io/docs/api/get-voices

## Model Reference

Hugging Face image models:
- `stabilityai/stable-diffusion-xl-base-1.0` - ⭐ Recommended (balanced)
- `stabilityai/stable-diffusion-3-medium` - Newer, better quality
- `runwayml/stable-diffusion-v1-5` - Lightweight, faster

## Environment File Location

Save as: `.env` in the project root (same directory as README.md)

Example path:
```
C:\Users\Maytri Shah\OneDrive\Desktop\New folder\Mockr\.env
```

## Verify Setup

After setting up .env, test with:

```bash
# Windows PowerShell
cd "C:\Users\Maytri Shah\OneDrive\Desktop\New folder\Mockr"

# Test
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('✓ ELEVENLABS_API_KEY:', bool(os.getenv('ELEVENLABS_API_KEY')))"
```

## Performance Expectations

With this setup:
- **Voice generation**: 0.5-1 second (Eleven Labs)
- **Image generation**: 1-2 minutes per reel (Hugging Face)
- **Total reel time**: 2-3 minutes (vs 5-10 before)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Eleven Labs timeout" | Check API key, or switch to fallback |
| "HF returned 404" | Enable serverless inference on HF |
| "Rate limited" | Wait or upgrade API tier |
| "No images" | Check HF_API_KEY or try Pollinations |
