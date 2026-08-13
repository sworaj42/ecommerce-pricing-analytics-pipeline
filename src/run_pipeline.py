"""
Pipeline Orchestrator
======================
Runs the scrape -> clean stages in sequence. Each stage can also be run
standalone via its own module (see src/scraping and src/cleaning).

Usage:
  python src/run_pipeline.py                 # scrape, then clean the result
  python src/run_pipeline.py --skip-scrape    # clean the latest raw CSV only
  python src/run_pipeline.py --headless       # scrape with no visible browser window
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cleaning.clean_whisky_data import main as clean_main
from src.scraping.scrape_whisky_exchange import scrape_whisky_exchange
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def run(skip_scrape: bool = False, headless: bool = False, test_mode: bool = False) -> None:
    if not skip_scrape:
        logger.info("Stage 1/2: scraping thewhiskyexchange.com")
        scrape_whisky_exchange(headless=headless, test_mode=test_mode)
    else:
        logger.info("Stage 1/2: skipped (--skip-scrape)")

    logger.info("Stage 2/2: cleaning raw data")
    clean_main()

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the whisky pricing pipeline end to end")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping and clean the latest existing raw CSV")
    parser.add_argument("--headless", action="store_true", help="Run the scraper without a visible browser window")
    parser.add_argument("--test", action="store_true", help="Scraper test mode: 1 page, 2 enrichments")
    args = parser.parse_args()

    run(skip_scrape=args.skip_scrape, headless=args.headless, test_mode=args.test)
