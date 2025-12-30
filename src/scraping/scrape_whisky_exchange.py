import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests


# Configuration
CATEGORIES: Dict[str, str] = {
    "Single Malt": "https://www.thewhiskyexchange.com/c/40/single-malt-scotch-whisky",
    "Blended": "https://www.thewhiskyexchange.com/c/304/blended-scotch-whisky",
}

PAGES_PER_CATEGORY = 15
REQUEST_TIMEOUT = 30
MIN_DELAY_SEC = 2.5
MAX_DELAY_SEC = 5.0
IMPERSONATE_BROWSER = "chrome110"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# Path Helpers 
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def raw_data_path() -> Path:
    path = project_root() / "data" / "raw" / "whisky_raw.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

# Network Logic
def fetch_page(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                impersonate=IMPERSONATE_BROWSER,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Referer": "https://www.google.com/",
                },
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            wait = (2 ** attempt) + random.uniform(1, 2)
            time.sleep(wait)
    
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")

# Extraction Logic
def parse_products(html: str, category: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[dict] = []

    # 1. Extract JSON Metadata
    json_items = []
    for script in soup.find_all("script"):
        if script.string and "var items =" in script.string:
            match = re.search(r"var items\s*=\s*(\[.*?\]);", script.string, re.DOTALL)
            if match:
                try:
                    json_items = json.loads(match.group(1))
                    break
                except json.JSONDecodeError: continue

    # 2. Extract HTML Card Data (URLs and WORKING Images)
    card_map = {}
    cards = soup.find_all("li", class_="product-grid__item")
    for card in cards:
        link_tag = card.find("a", class_="product-card")
        if link_tag:
            href = link_tag.get("href", "")
            id_match = re.search(r"/p/(\d+)/", href)
            if id_match:
                p_id = id_match.group(1)
                img_tag = card.find("img", class_="product-card__image")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""

                status_text = "In Stock"
                badge = card.find("p", class_=re.compile("product-card__status"))
                if badge:
                    status_text = badge.get_text(strip=True)

                card_map[p_id] = {
                    "url": f"https://www.thewhiskyexchange.com{href}",
                    "image": img_url,
                    "unit_price": card.find("p", class_="product-card__unit-price"),
                    "status": status_text
                }

    # 3. Merge Data
    for item in json_items:
        p_id = str(item.get("item_id"))
        card = card_map.get(p_id, {})
        
        rows.append({
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "product_id": p_id,
            "name": item.get("item_name"),
            "brand": item.get("item_brand"),
            "variant": item.get("item_variant"),
            "price_gbp": item.get("price"),
            "unit_price_raw": card.get("unit_price").get_text(strip=True) if card.get("unit_price") else "",
            "region": item.get("item_category3") or "N/A",
            "promo_label": item.get("item_category5") or "", # FIXED: Added Promo Label extraction
            "status": card.get("status", "Current"),
            "product_url": card.get("url", f"https://www.thewhiskyexchange.com/p/{p_id}/"),
            "image_url": card.get("image", ""), # FIXED: Pulls correct image URL
        })

    return rows

# Main Execution
def scrape_whisky_exchange():
    all_data = []
    
    for cat_name, base_url in CATEGORIES.items():
        print(f"\n>>> Scraping: {cat_name}")
        for page in range(1, PAGES_PER_CATEGORY + 1):
            url = f"{base_url}?pg={page}"
            print(f"    Fetching Page {page}...")
            
            try:
                html = fetch_page(url)
                page_rows = parse_products(html, cat_name)
                
                if not page_rows:
                    break
                
                all_data.extend(page_rows)
                time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))
                
            except Exception as e:
                print(f"    Error on page {page}: {e}")
                break

    if all_data:
        output = raw_data_path()
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            writer.writeheader()
            writer.writerows(all_data)
        print(f"\nSuccess! Saved {len(all_data)} products to: {output}")

if __name__ == "__main__":
    scrape_whisky_exchange()