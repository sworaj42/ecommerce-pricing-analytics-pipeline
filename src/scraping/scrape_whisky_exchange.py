import csv
import random
import time
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from curl_cffi import requests


# -------------------------
# Configuration
# -------------------------

CATEGORIES: Dict[str, str] = {
    "Single Malt": "https://www.thewhiskyexchange.com/c/40/single-malt-scotch-whisky",
    "Blended": "https://www.thewhiskyexchange.com/c/304/blended-scotch-whisky",
}

PAGES_PER_CATEGORY = 15
REQUEST_TIMEOUT = 30
MIN_DELAY_SEC = 2.0
MAX_DELAY_SEC = 4.0
IMPERSONATE_BROWSER = "chrome110"


# -------------------------
# Path helpers
# -------------------------

def project_root() -> Path:
    # src/scraping/scrape_whisky_exchange.py → project root
    return Path(__file__).resolve().parents[2]


def raw_data_path() -> Path:
    return project_root() / "data" / "raw" / "whisky_raw.csv"


# -------------------------
# Scraping helpers
# -------------------------

def fetch_page(url: str) -> str:
    response = requests.get(
        url,
        impersonate=IMPERSONATE_BROWSER,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def parse_products(html: str, category: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.find_all("li", class_="product-grid__item")

    rows: List[dict] = []

    for item in items:
        try:
            name = item.find("p", class_="product-card__name").get_text(strip=True)
            meta = item.find("p", class_="product-card__meta").get_text(strip=True)
            price = item.find("p", class_="product-card__price").get_text(strip=True)
            link = item.find("a", href=True)["href"]

            rows.append(
                {
                    "category": category,
                    "raw_name": name,
                    "raw_meta": meta,
                    "raw_price": price,
                    "product_url": f"https://www.thewhiskyexchange.com{link}",
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception:
            # Skip malformed product cards
            continue

    return rows


# -------------------------
# Main pipeline
# -------------------------

def scrape_whisky_exchange() -> int:
    all_rows: List[dict] = []

    for category, base_url in CATEGORIES.items():
        print(f"Scraping category: {category}")

        for page in range(1, PAGES_PER_CATEGORY + 1):
            page_url = f"{base_url}?pg={page}"
            print(f"  Fetching page {page}")

            try:
                html = fetch_page(page_url)
                rows = parse_products(html, category)

                if not rows:
                    print("  No products found. Ending category.")
                    break

                all_rows.extend(rows)

                time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))

            except Exception as exc:
                print(f"  Error on page {page}: {exc}")
                break

    output_path = raw_data_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not all_rows:
        print("No data collected.")
        return 0

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} records to {output_path}")
    return len(all_rows)


if __name__ == "__main__":
    scrape_whisky_exchange()
