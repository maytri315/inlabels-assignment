# Quick Setup Checklist ✅

Complete this checklist to enable fast reel generation with Eleven Labs + Hugging Face.

---

## Step 1: Get Eleven Labs API Key (5 min)

- [ ] Visit https://elevenlabs.io/
- [ ] Sign up for free account
- [ ] Go to **Settings** → **Account** → copy **API Key**
- [ ] Go to https://elevenlabs.io/docs/api/get-voices
- [ ] Choose a voice (e.g., `21m00Tcm4TlvDq8ikWAM` for Rachel)
- [ ] Note down: 
  - API Key: `sk_...`
  - Voice ID: `21m00Tcm...`

**Time: 5 minutes | Cost: Free (10K chars/month)**

---

## Step 2: Get Hugging Face API Key (5 min)

- [ ] Visit https://huggingface.co/
- [ ] Sign up for free account
- [ ] Go to **Settings** → **Access Tokens**
- [ ] Click **New Token**
- [ ] Name it "mockr-images"
- [ ] Select scope: **Read**
- [ ] Copy the token (starts with `hf_`)
- [ ] Note down: API Key: `hf_...`

**Optional but recommended:**
- [ ] Enable serverless inference:
  - Go to https://huggingface.co/settings/billing/subscription
  - Check if you have "Inference Endpoints" access
  - (If not available, free tier will still work with rate limiting)

**Time: 5 minutes | Cost: Free**

---

## Step 3: Create .env File (2 min)

In the Mockr project root directory, create a file named `.env`:

```
📁 C:\Users\Maytri Shah\OneDrive\Desktop\New folder\Mockr
   📄 .env  ← Create this file
```

**Contents** (copy & paste, replace YOUR_KEYS):

```env
# Google API (for fact-checking)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# Groq API (for script generation)
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile

# News feed settings
NEWS_FEED_URL=https://news.google.com/rss/search?q=Lucknow&hl=en-IN&gl=IN&ceid=IN:en
OUTPUT_DIR=./output
MAX_STORIES=4
LOOKBACK_HOURS=4
ROAST_STYLE=sharp

# 🎤 VOICE (Eleven Labs - Primary)
ELEVENLABS_API_KEY=sk_your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
VOICE_LANG=en-US

# 🎤 VOICE (Edge TTS - Fallback)
EDGE_TTS_VOICE=en-US-AriaNeural
EDGE_TTS_RATE=+15%

# 🎨 IMAGES (Hugging Face - Primary)
HF_API_KEY=hf_your_huggingface_api_key_here
HF_IMAGE_MODEL=stabilityai/stable-diffusion-xl-base-1.0

# 🎨 IMAGES (Pollinations - Fallback)
POLLINATIONS_BASE_URL=https://image.pollinations.ai
```

**Important:**
- Save in project root (same level as `README.md`)
- Do NOT share this file (contains API keys!)
- Add to `.gitignore` to prevent accidents

**Time: 2 minutes**

---

## Step 4: Verify Setup (3 min)

Open PowerShell in the Mockr directory and run:

```powershell
cd "C:\Users\Maytri Shah\OneDrive\Desktop\New folder\Mockr"

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Check if keys are loaded
python -c "
from autonomous_anchor.config import load_settings
s = load_settings()
print('✓ Configuration loaded')
print('  Eleven Labs API Key:', 'YES' if s.elevenlabs_api_key else 'NO')
print('  Eleven Labs Voice ID:', 'YES' if s.elevenlabs_voice_id else 'NO')
print('  HF API Key:', 'YES' if s.hf_api_key else 'NO')
print('  HF Model:', s.hf_image_model)
"
```

**Expected Output:**
```
✓ Configuration loaded
  Eleven Labs API Key: YES
  Eleven Labs Voice ID: YES
  HF API Key: YES
  HF Model: stabilityai/stable-diffusion-xl-base-1.0
```

If any shows "NO", check your .env file.

**Time: 3 minutes**

---

## Step 5: Test Voice Generation (1 min)

```powershell
python -c "
from src.autonomous_anchor.voiceover import synthesize_voiceover
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
start = datetime.now()
print('Testing Eleven Labs voice generation...')
audio = synthesize_voiceover(
    'Testing Eleven Labs voice synthesis with high quality audio',
    Path('test_audio.wav'),
    elevenlabs_api_key=os.getenv('ELEVENLABS_API_KEY'),
    elevenlabs_voice_id=os.getenv('ELEVENLABS_VOICE_ID'),
)
duration = (datetime.now() - start).total_seconds()
print(f'✓ Voice generated in {duration:.1f} seconds')
print(f'✓ File: {audio}')
print(f'✓ Size: {audio.stat().st_size} bytes')
"
```

**Expected:**
- Completes in <3 seconds
- Creates `test_audio.wav` file
- File size > 50KB

**Time: 1 minute (varies by API response time)**

---

## Step 6: Test Image Generation (2 min)

```powershell
python -c "
from src.autonomous_anchor.visual_assets import _hf_sdxl_image
from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
start = datetime.now()
print('Testing Hugging Face SDXL image generation...')
image_bytes = _hf_sdxl_image(
    'Breaking news announcement with professional graphics and bold text',
    hf_api_key=os.getenv('HF_API_KEY'),
)
duration = (datetime.now() - start).total_seconds()
if image_bytes:
    Path('test_image.png').write_bytes(image_bytes)
    print(f'✓ Image generated in {duration:.1f} seconds')
    print(f'✓ File: test_image.png')
    print(f'✓ Size: {len(image_bytes)} bytes')
else:
    print('✗ Image generation failed')
    print('  Check: HF_API_KEY in .env')
    print('  Check: Serverless inference enabled on HF')
"
```

**Expected:**
- Completes in 30-90 seconds
- Creates `test_image.png` file
- File size > 100KB

**If you get 404 error:**
- This means HF account doesn't have serverless inference
- System will use Pollinations fallback (automatic)
- Or upgrade to HF Pro tier

**Time: 2 minutes (varies by API)**

---

## Step 7: Run First Reel (3 min)

```powershell
# Start Django server
cd backend
python manage.py runserver
```

Then in browser:
- Go to: http://localhost:8000
- Click **"Run"** button
- Watch progress and timing
- Should complete in 2-3 minutes

Check console output for timing:
```
[fetch_relevant_images] Trying Hugging Face SDXL for 'term'
[fetch_relevant_images] ✓ Saved HuggingFace SDXL image
```

**Time: 3-5 minutes**

---

## Troubleshooting

### Voice Says "Edge TTS" or "gTTS"
**Problem:** Eleven Labs not working
**Solution:**
- [ ] Check `ELEVENLABS_API_KEY` in .env (starts with `sk_`)
- [ ] Check `ELEVENLABS_VOICE_ID` in .env
- [ ] Verify API key is correct at https://elevenlabs.io/
- [ ] Check API usage hasn't exceeded free tier (10K chars/month)

### Images Say "Pollinations" or "Wikimedia"
**Problem:** Hugging Face not working
**Solution:**
- [ ] Check `HF_API_KEY` in .env (starts with `hf_`)
- [ ] Verify token is correct at https://huggingface.co/settings/access-tokens
- [ ] Check for "404" error in logs:
  - If 404: Enable serverless inference on HF account
  - If timeout: HF is rate limiting, will retry automatically

### .env File Not Loading
**Problem:** Changes to .env not taking effect
**Solution:**
- [ ] Restart Django server (`Ctrl+C` then run again)
- [ ] Or restart Python terminal
- [ ] Make sure .env is in project root (not in src/ or backend/)

### API Rate Limited
**Problem:** "Rate limited" errors
**Solution:**
- [ ] Eleven Labs: Free tier = 10K chars/month (upgrade to Pro)
- [ ] Hugging Face: Free tier has limits (upgrade to Pro or wait)
- [ ] Both will auto-retry with exponential backoff

---

## Performance Expectations

After setup:

| Component | Time | Status |
|-----------|------|--------|
| Voice (Eleven Labs) | 0.5-1 sec | ⚡ Fast |
| Images (Hugging Face) | 1-2 min | ⚡ Fast |
| Video Render | 10-20 sec | ⚡ Normal |
| **Total Reel** | **2-3 min** | ✅ 5x faster |

---

## Common Questions

**Q: Can I use free tier?**
- Yes! Eleven Labs (10K chars/month) + Hugging Face (free but rate-limited)
- ~4-5 reels per month at free tier

**Q: What if APIs fail?**
- System gracefully falls back to other services
- Reel will still generate, just slower
- All services have retry logic

**Q: Is my API key safe in .env?**
- .env is in `.gitignore` (not shared)
- Never commit .env to git
- Safe for local development

**Q: Can I switch back to Pollinations?**
- Yes! Just remove HF_API_KEY from .env
- System will automatically use Pollinations

**Q: How do I know which service was used?**
- Check logs in console output
- Look for "Eleven Labs" or "Hugging Face" in logs
- File sizes differ (HF images smaller than Pollinations)

---

## ✅ Checklist Complete!

Once you've completed all steps:

- [ ] Step 1: Got Eleven Labs API key
- [ ] Step 2: Got Hugging Face API key
- [ ] Step 3: Created .env file with keys
- [ ] Step 4: Verified configuration loads
- [ ] Step 5: Tested voice generation
- [ ] Step 6: Tested image generation
- [ ] Step 7: Generated first reel successfully

**You're done! 🎉**

Next reels should generate in 2-3 minutes instead of 5-15 minutes.

---

## Support

Need help?

1. Check logs in `output/[category]/[timestamp]/` directory
2. Look for error messages indicating which service failed
3. Verify API keys are correct in .env
4. Check API quotas on Eleven Labs and Hugging Face

The system is designed to always succeed (fallbacks on every provider)!
