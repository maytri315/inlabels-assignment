from __future__ import annotations

import argparse
import logging
import time
from apscheduler.schedulers.blocking import BlockingScheduler

from .config import load_settings
from .pipeline import run_anchor_cycle


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def run_once() -> None:
    settings = load_settings()
    package = run_anchor_cycle(settings)
    print("Run complete")
    print(f"Run ID: {package.run_id}")
    print(f"Script: {package.script_path}")
    print(f"Audio : {package.audio_path}")
    print(f"Video : {package.video_path}")
    print(f"Facts : {package.verdicts_path}")
    print(f"Reel  : {package.reel_path}")



def run_hourly() -> None:
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(run_once, "interval", hours=1, max_instances=1, coalesce=True)
    print("Hourly autonomous anchor started. Press Ctrl+C to stop.")
    run_once()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous News/Brand Anchor")
    parser.add_argument("--hourly", action="store_true", help="Run every hour")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    if args.hourly:
        run_hourly()
    else:
        run_once()


if __name__ == "__main__":
    main()
