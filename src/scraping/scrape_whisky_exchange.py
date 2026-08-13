"""
Whisky Exchange Scraper — v2 (May 2026)
========================================
Upgraded from curl_cffi to SeleniumBase UC (Undetected Chrome) mode
to bypass Cloudflare's updated anti-bot protection post-rebrand.

Changes from v1:
  - fetch_page() now uses SeleniumBase UC mode instead of curl_cffi
  - Browser session is reused across requests (faster, fewer fingerprint checks)
  - Added warm-up: visits homepage first to build a legitimate session
  - All extraction logic (BeautifulSoup, JSON-LD, flavour profiles) is unchanged
  - Added --headless flag (default: visible browser for debugging)
  - Added --test flag to scrape just 1 page + 2 products for quick validation

Requirements:
  pip install seleniumbase beautifulsoup4 lxml

Usage:
  python scrape_whisky_exchange_v2.py              # full scrape, visible browser
  python scrape_whisky_exchange_v2.py --headless    # full scrape, no browser window
  python scrape_whisky_exchange_v2.py --test        # quick test: 1 page, 2 enrichments
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from seleniumbase import SB

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.paths import RAW_DATA_DIR, ensure_dir  # noqa: E402

# ─── Configuration ───────────────────────────────────────────
CATEGORIES: dict[str, str] = {
    "Single Malt": "https://www.thewhiskyexchange.com/c/40/single-malt-scotch-whisky",
    "Blended": "https://www.thewhiskyexchange.com/c/304/blended-scotch-whisky",
}

TARGET_PER_CATEGORY = 600
MAX_PAGES_PER_CATEGORY = 60

MIN_DELAY_SEC = 2.0
MAX_DELAY_SEC = 4.0

HOMEPAGE_URL = "https://www.thewhiskyexchange.com/"


# ─── Path Helpers ────────────────────────────────────────────
def raw_data_path() -> Path:
    """Dated output path, e.g. data/raw/whisky_raw_2026-01-16.csv."""
    return ensure_dir(RAW_DATA_DIR) / f"whisky_raw_{date.today().isoformat()}.csv"


# ─── Browser Helpers ─────────────────────────────────────────
def polite_delay(min_sec: float = MIN_DELAY_SEC, max_sec: float = MAX_DELAY_SEC):
    """Random delay between requests to be polite."""
    time.sleep(random.uniform(min_sec, max_sec))


def get_page_source(sb, url: str, retries: int = 3) -> str:
    """
    Navigate to a URL using the SeleniumBase UC driver and return page source.
    Retries on failure with exponential backoff.
    """
    for attempt in range(retries):
        try:
            sb.uc_open_with_reconnect(url, reconnect_time=4)

            # If Cloudflare throws a challenge, click it
            try:
                sb.uc_gui_click_captcha()
            except Exception:
                pass  # No captcha present — that's fine

            # Wait for page content to load
            sb.sleep(2)

            # Verify we got a real page (not a block page)
            source = sb.get_page_source()
            if source and len(source) > 5000:
                return source

            # If page is too short, might be a challenge page — retry
            if attempt < retries - 1:
                wait = (2 ** attempt) + random.uniform(1, 2)
                print(f"      Short response, retrying in {wait:.1f}s...")
                time.sleep(wait)

        except Exception as e:
            if attempt < retries - 1:
                wait = (2 ** attempt) + random.uniform(1, 2)
                print(f"      Error: {e}, retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to fetch {url} after {retries} retries: {e}")

    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")


def warm_up_session(sb):
    """
    Visit the homepage first to build a legitimate browsing session.
    Cloudflare is less suspicious of scrapers that start at the homepage.
    """
    print(">>> Warming up session (visiting homepage)...")
    try:
        sb.uc_open_with_reconnect(HOMEPAGE_URL, reconnect_time=5)
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass
        sb.sleep(3)
        print("    Homepage loaded successfully.")
    except Exception as e:
        print(f"    Warning: Homepage warm-up failed ({e}), continuing anyway...")


# ─── Extraction Logic (unchanged from v1) ────────────────────
def extract_display_price_inc_vat(product_html: str) -> str:
    soup = BeautifulSoup(product_html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if not isinstance(obj, dict):
                continue
            offers = obj.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                if price is not None:
                    return str(price).strip()
            if isinstance(offers, list):
                for offer in offers:
                    if isinstance(offer, dict) and offer.get("price") is not None:
                        return str(offer.get("price")).strip()
    return ""


def extract_rating_and_reviews(product_html: str) -> tuple:
    soup = BeautifulSoup(product_html, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        objs = data if isinstance(data, list) else [data]
        for obj in objs:
            if not isinstance(obj, dict):
                continue
            agg = obj.get("aggregateRating")
            if isinstance(agg, dict):
                rating = str(agg.get("ratingValue", "")).strip()
                count = str(agg.get("reviewCount", "")).strip()
                return rating, count
    return "", ""


def extract_price_before_discount(product_html: str) -> str:
    soup = BeautifulSoup(product_html, "html.parser")
    was_tag = soup.find("span", class_="product-offer__price")
    if not was_tag:
        return ""
    text = was_tag.get_text(" ", strip=True)
    m = re.search(r"Was\s*£\s*(\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if not m:
        return ""
    return m.group(1)


def extract_style_scores(product_html: str) -> dict:
    soup = BeautifulSoup(product_html, "html.parser")
    out = {}

    # Try the original selectors first
    details = soup.find("details", id="Style")
    if not details:
        # Fallback: search for flavour profile sections by class pattern
        details = soup.find(class_=re.compile(r"flavour-profile.*style", re.I))
    if not details:
        return out

    ul = details.find("ul", class_=re.compile(r"flavour-profile__list"))
    if not ul:
        return out

    for li in ul.find_all("li", class_=re.compile(r"flavour-profile__item")):
        label_tag = li.find("span", class_="flavour-profile__label")
        if not label_tag:
            continue
        label = label_tag.get_text(strip=True).lower().replace(" ", "_")

        score = ""
        score_tag = li.find("span", class_="flavour-profile__content")
        if score_tag:
            score = score_tag.get_text(strip=True)
        else:
            gauge = li.find(class_=re.compile(r"flavour-profile__gauge"))
            if gauge and gauge.get("data-text"):
                score = gauge.get("data-text").strip()

        if score:
            out[label] = score
    return out


def extract_character_notes(product_html: str) -> str:
    soup = BeautifulSoup(product_html, "html.parser")

    details = soup.find("details", id="Character")
    if not details:
        details = soup.find(class_=re.compile(r"flavour-profile.*character", re.I))
    if not details:
        return ""

    ul = details.find("ul", class_=re.compile(r"flavour-profile__list"))
    if not ul:
        return ""

    labels = []
    for tag in ul.find_all("span", class_="flavour-profile__label"):
        txt = tag.get_text(strip=True)
        if txt:
            labels.append(txt)
    return "|".join(labels)


def extract_product_facts(product_html: str) -> dict:
    soup = BeautifulSoup(product_html, "html.parser")
    out: dict = {}

    details = soup.find("details", id="ProductFacts")
    if not details:
        details = soup.find(class_=re.compile(r"product-facts", re.I))
    if not details:
        return out

    ul = details.find("ul", class_="product-facts")
    if not ul:
        # Fallback: look for any list within the facts section
        ul = details.find("ul")
    if not ul:
        return out

    for li in ul.find_all("li"):
        k = li.find("h3") or li.find(class_=re.compile(r"type|key|label", re.I))
        v = li.find("p") or li.find(class_=re.compile(r"data|value", re.I))
        if not k or not v:
            continue

        key = re.sub(r"[^a-z0-9]+", "_", k.get_text(strip=True).lower()).strip("_")
        val = v.get_text(" ", strip=True)

        if key and val:
            out[key] = val
    return out


def extract_product_metadata(product_html: str) -> dict:
    """Extract all enrichment fields from a product detail page."""
    rating, review_count = extract_rating_and_reviews(product_html)
    price_inc_vat = extract_display_price_inc_vat(product_html)
    price_before_discount = extract_price_before_discount(product_html)

    style = extract_style_scores(product_html)
    character = extract_character_notes(product_html)
    facts = extract_product_facts(product_html)

    return {
        "rating_stars": rating,
        "review_count": review_count,
        "price_inc_vat_gbp": price_inc_vat,
        "price_before_discount_gbp": price_before_discount,
        "style_body": style.get("body", ""),
        "style_richness": style.get("richness", ""),
        "style_smoke": style.get("smoke", ""),
        "style_sweetness": style.get("sweetness", ""),
        "character_notes": character,
        "fact_bottler": facts.get("bottler", ""),
        "fact_country": facts.get("country", ""),
        "fact_region": facts.get("region", ""),
        "fact_cask_type": facts.get("cask_type", ""),
        "fact_colouring": facts.get("colouring", ""),
    }


EMPTY_METADATA = {
    "rating_stars": "", "review_count": "",
    "price_inc_vat_gbp": "", "price_before_discount_gbp": "",
    "style_body": "", "style_richness": "", "style_smoke": "", "style_sweetness": "",
    "character_notes": "",
    "fact_bottler": "", "fact_country": "", "fact_region": "",
    "fact_cask_type": "", "fact_colouring": "",
}


# ─── Listing Page Parser ─────────────────────────────────────
def parse_products(html: str, category: str) -> list[dict]:
    """Parse a category listing page and extract product rows."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []

    # Extract JSON metadata from "var items = [...]"
    json_items = []
    for script in soup.find_all("script"):
        if script.string and "var items =" in script.string:
            match = re.search(r"var items\s*=\s*(\[.*?\]);", script.string, re.DOTALL)
            if match:
                try:
                    json_items = json.loads(match.group(1))
                    break
                except json.JSONDecodeError:
                    continue

    # If the old "var items" approach doesn't work (post-rebrand),
    # try extracting from JSON-LD structured data
    if not json_items:
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("@type") == "ItemList":
                for item in data.get("itemListElement", []):
                    product = item.get("item", {})
                    if product:
                        json_items.append({
                            "item_id": product.get("sku", ""),
                            "item_name": product.get("name", ""),
                            "item_brand": product.get("brand", {}).get("name", "") if isinstance(product.get("brand"), dict) else "",
                            "item_variant": "",
                            "price": product.get("offers", {}).get("price", "") if isinstance(product.get("offers"), dict) else "",
                            "item_category3": "",
                            "item_category5": "",
                            "_url": product.get("url", ""),
                        })

    # Extract HTML card data (url, image, status, unit price)
    card_map = {}
    # Try the original selectors first, then fallback patterns
    cards = soup.find_all("li", class_="product-grid__item")
    if not cards:
        # Fallback: look for product card containers with different class names
        cards = soup.find_all("li", class_=re.compile(r"product.*item|product-card", re.I))
    if not cards:
        # Last resort: find all product card links
        cards = soup.find_all("div", class_=re.compile(r"product-card|product-grid", re.I))

    for card in cards:
        link_tag = card.find("a", href=re.compile(r"/p/\d+/"))
        if not link_tag:
            link_tag = card.find("a", class_=re.compile(r"product"))
        if link_tag:
            href = link_tag.get("href", "")
            id_match = re.search(r"/p/(\d+)/", href)
            if id_match:
                p_id = id_match.group(1)
                img_tag = card.find("img")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""

                status_text = "In Stock"
                badge = card.find(class_=re.compile(r"status|badge|stock", re.I))
                if badge:
                    status_text = badge.get_text(strip=True)

                unit_price_tag = card.find(class_=re.compile(r"unit.price", re.I))

                card_map[p_id] = {
                    "url": f"https://www.thewhiskyexchange.com{href}" if href.startswith("/") else href,
                    "image": img_url,
                    "unit_price_tag": unit_price_tag,
                    "status": status_text,
                }

    # Merge JSON items with HTML card data
    for item in json_items:
        p_id = str(item.get("item_id", "")).strip()
        if not p_id:
            # Try to extract from URL
            url_val = item.get("_url", "")
            m = re.search(r"/p/(\d+)/", url_val)
            if m:
                p_id = m.group(1)

        card = card_map.get(p_id, {})

        product_url = card.get("url", "") or item.get("_url", "")
        if not product_url and p_id:
            product_url = f"https://www.thewhiskyexchange.com/p/{p_id}"
        if product_url and not product_url.startswith("http"):
            product_url = f"https://www.thewhiskyexchange.com{product_url}"

        unit_price_text = ""
        upt = card.get("unit_price_tag")
        if upt:
            try:
                unit_price_text = upt.get_text(strip=True)
            except Exception:
                pass

        rows.append({
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "product_id": p_id,
            "name": item.get("item_name", ""),
            "brand": item.get("item_brand", ""),
            "variant": item.get("item_variant", ""),
            "price_ex_vat_gbp": item.get("price", ""),
            "unit_price_raw": unit_price_text,
            "region": item.get("item_category3") or "N/A",
            "promo_label": item.get("item_category5") or "",
            "status": card.get("status", "Current"),
            "product_url": product_url,
            "image_url": card.get("image", ""),
            **EMPTY_METADATA,
        })

    # If neither JSON approach worked, fall back to pure HTML scraping
    if not rows and card_map:
        print("    Falling back to pure HTML card extraction...")
        for p_id, card in card_map.items():
            # Extract name from the link text
            name = ""
            name_tag = None
            # Re-find the card in the soup to get the name
            for c in cards:
                a = c.find("a", href=re.compile(rf"/p/{p_id}/"))
                if a:
                    name_tag = c.find(class_=re.compile(r"product.*name|title", re.I))
                    if not name_tag:
                        name_tag = c.find("h2") or c.find("h3") or c.find("p", class_=re.compile(r"name|title"))
                    break
            if name_tag:
                name = name_tag.get_text(strip=True)

            price_tag = None
            for c in cards:
                a = c.find("a", href=re.compile(rf"/p/{p_id}/"))
                if a:
                    price_tag = c.find(class_=re.compile(r"price(?!.*unit)", re.I))
                    break
            price_text = ""
            if price_tag:
                m = re.search(r"£\s*(\d+(?:\.\d+)?)", price_tag.get_text())
                if m:
                    price_text = m.group(1)

            rows.append({
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "category": "",
                "product_id": p_id,
                "name": name,
                "brand": "",
                "variant": "",
                "price_ex_vat_gbp": price_text,
                "unit_price_raw": "",
                "region": "N/A",
                "promo_label": "",
                "status": card.get("status", "Current"),
                "product_url": card.get("url", ""),
                "image_url": card.get("image", ""),
                **EMPTY_METADATA,
            })

    return rows


# ─── Main Scraper ────────────────────────────────────────────
def scrape_whisky_exchange(headless: bool = False, test_mode: bool = False):
    """
    Main scraping function.

    Args:
        headless: If True, run Chrome without a visible window.
        test_mode: If True, scrape only 1 page + enrich 2 products (for validation).
    """
    target = 2 if test_mode else TARGET_PER_CATEGORY
    max_pages = 1 if test_mode else MAX_PAGES_PER_CATEGORY
    max_enrichments = 2 if test_mode else None  # None = enrich all

    all_data: list[dict] = []

    # SeleniumBase UC mode — the key upgrade from v1
    with SB(uc=True, headless=headless, chromium_arg="--disable-blink-features=AutomationControlled") as sb:

        # Warm up: visit homepage to establish a legitimate session
        warm_up_session(sb)
        polite_delay(2, 4)

        # ── Phase 1: Scrape listing pages ──
        for cat_name, base_url in CATEGORIES.items():
            print(f"\n>>> Scraping: {cat_name} (target {target})")

            seen_ids = set()
            category_rows: list[dict] = []

            for page in range(1, max_pages + 1):
                if len(category_rows) >= target:
                    break

                url = f"{base_url}?pg={page}"
                print(f"    Fetching Page {page}... ({len(category_rows)}/{target})")

                try:
                    html = get_page_source(sb, url)
                    page_rows = parse_products(html, cat_name)

                    if not page_rows:
                        print("    No products found on this page. Stopping category.")
                        # Debug: save the HTML for inspection
                        debug_path = ensure_dir(RAW_DATA_DIR) / f"debug_{cat_name.replace(' ', '_')}_p{page}.html"
                        with open(debug_path, "w", encoding="utf-8") as f:
                            f.write(html[:50000])
                        print(f"    Saved debug HTML to: {debug_path}")
                        break

                    added = 0
                    for r in page_rows:
                        pid = r.get("product_id", "")
                        if not pid or pid in seen_ids:
                            continue
                        seen_ids.add(pid)
                        category_rows.append(r)
                        added += 1
                        if len(category_rows) >= target:
                            break

                    print(f"    Added {added} new products (total {len(category_rows)}/{target})")
                    polite_delay()

                except Exception as e:
                    print(f"    Error on page {page}: {e}")
                    break

            if len(category_rows) < target:
                print(f"    Warning: only collected {len(category_rows)} products for {cat_name}.")

            all_data.extend(category_rows)

        # ── Phase 2: Enrich product detail pages ──
        print("\n>>> Enriching products (rating, reviews, price, style, character, facts) ...")

        cache: dict = {}
        unique_urls = []
        seen_urls = set()
        for row in all_data:
            u = row.get("product_url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                unique_urls.append(u)

        if max_enrichments is not None:
            unique_urls = unique_urls[:max_enrichments]

        total = len(unique_urls)
        print(f"    Unique product pages to enrich: {total}")

        for idx, url in enumerate(unique_urls, start=1):
            sample_row = next((r for r in all_data if r.get("product_url") == url), {})
            pid = sample_row.get("product_id", "")
            name = (sample_row.get("name") or "").strip()

            print(f"    [{idx:>4}/{total}] Enriching ID={pid} | {name[:60]}")

            try:
                html = get_page_source(sb, url)
                cache[url] = extract_product_metadata(html)
                polite_delay()
            except Exception as e:
                print(f"         -> failed: {e}")
                cache[url] = dict(EMPTY_METADATA)

    # ── Phase 3: Merge enrichment data + save ──
    for row in all_data:
        url = row.get("product_url", "")
        if not url:
            continue
        meta = cache.get(url, {})
        for key in EMPTY_METADATA:
            if key in meta:
                row[key] = meta[key]

    if all_data:
        output = raw_data_path()
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            writer.writeheader()
            writer.writerows(all_data)

        cat_counts = {}
        for r in all_data:
            cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1

        print("\n>>> Done.")
        for k, v in cat_counts.items():
            print(f"    {k}: {v}")
        print(f"\nSaved {len(all_data)} products to: {output}")
    else:
        print("\n>>> No data collected. Check the debug HTML files for clues.")


# ─── Entry Point ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Whisky Exchange Scraper v2 (SeleniumBase UC)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode (no visible window)")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: scrape 1 page + enrich 2 products only")
    args = parser.parse_args()

    if args.test:
        print("=" * 60)
        print("  TEST MODE: 1 page per category, 2 enrichments only")
        print("=" * 60)

    scrape_whisky_exchange(headless=args.headless, test_mode=args.test)