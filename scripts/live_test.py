# NovelPipeline/scripts/live_test.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from littrans.modules.scraper import run_scraper_blocking, ScraperOptions

run_scraper_blocking(
    urls=["https://novelbin.com/b/system-build-my-own-territory"],
    options=ScraperOptions(novel_name="live_test"),
)
