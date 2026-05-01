import traceback
from autonomous_anchor.config import load_settings
from autonomous_anchor.pipeline import run_anchor_cycle

s = load_settings()
print('OUTPUT_DIR=', s.output_dir)
print('FEED=', s.news_feed_url)
try:
    p = run_anchor_cycle(s)
    print('OK', p.video_path)
except Exception:
    traceback.print_exc()
