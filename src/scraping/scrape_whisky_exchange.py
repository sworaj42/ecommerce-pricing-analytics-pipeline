import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup
from curl_cffi import requests


# Configuration
CATEGORIES: Dict[str, str] = {
    "Single Malt": "https://www.thewhiskyexchange.com/c/40/single-malt-scotch-whisky",
    "Blended": "https://www.thewhiskyexchange.com/c/304/blended-scotch-whisky",
}

TARGET_PER_CATEGORY = 600
MAX_PAGES_PER_CATEGORY = 60  

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
        except Exception:
            wait = (2 ** attempt) + random.uniform(1, 2)
            time.sleep(wait)

    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")


# For price extraction
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


# For rating extraction
def extract_rating_and_reviews(product_html: str) -> tuple[str, str]:
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


# For extracting price before discount
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


# Product style extraction
def extract_style_scores(product_html: str) -> dict:
    soup = BeautifulSoup(product_html, "html.parser")
    out = {}

    details = soup.find("details", id="Style")
    if not details:
        return out

    ul = details.find("ul", class_=re.compile(r"flavour-profile__list--style"))
    if not ul:
        return out

    for li in ul.find_all("li", class_=re.compile(r"flavour-profile__item--style")):
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


# Product character extraction
def extract_character_notes(product_html: str) -> str:
    soup = BeautifulSoup(product_html, "html.parser")

    details = soup.find("details", id="Character")
    if not details:
        return ""

    ul = details.find("ul", class_=re.compile(r"flavour-profile__list--character"))
    if not ul:
        return ""

    labels = []
    for tag in ul.find_all("span", class_="flavour-profile__label"):
        txt = tag.get_text(strip=True)
        if txt:
            labels.append(txt)

    return "|".join(labels)


# Products facts extraction
def extract_product_facts(product_html: str) -> dict:
    soup = BeautifulSoup(product_html, "html.parser")
    out: dict = {}

    details = soup.find("details", id="ProductFacts")
    if not details:
        return out

    ul = details.find("ul", class_="product-facts")
    if not ul:
        return out

    for li in ul.find_all("li", class_="product-facts__item"):
        k = li.find("h3", class_="product-facts__type")
        v = li.find("p", class_="product-facts__data")
        if not k or not v:
            continue

        key = re.sub(r"[^a-z0-9]+", "_", k.get_text(strip=True).lower()).strip("_")
        val = v.get_text(" ", strip=True)

        if key and val:
            out[key] = val

    return out


def extract_product_metadata(product_html: str) -> dict:
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


# Extraction Logic
def parse_products(html: str, category: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[dict] = []

    # Extract JSON metadata "var items = [...]"
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

    # Extract HTML card data (url, image, status, unit price)
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
                    "status": status_text,
                }

    # Merge
    for item in json_items:
        p_id = str(item.get("item_id"))
        card = card_map.get(p_id, {})

        product_url = card.get("url", "")
        if not product_url:
            product_url = f"https://www.thewhiskyexchange.com/p/{p_id}"

        rows.append(
            {
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "category": category,
                "product_id": p_id,
                "name": item.get("item_name"),
                "brand": item.get("item_brand"),
                "variant": item.get("item_variant"),
                "price_ex_vat_gbp": item.get("price"),
                "unit_price_raw": card.get("unit_price").get_text(strip=True) if card.get("unit_price") else "",
                "region": item.get("item_category3") or "N/A",
                "promo_label": item.get("item_category5") or "",
                "status": card.get("status", "Current"),
                "product_url": product_url,
                "image_url": card.get("image", ""),
                "rating_stars": "",
                "review_count": "",
                "price_inc_vat_gbp": "",
                "price_before_discount_gbp": "",
                "style_body": "",
                "style_richness": "",
                "style_smoke": "",
                "style_sweetness": "",
                "character_notes": "",
                "fact_bottler": "",
                "fact_country": "",
                "fact_region": "",
                "fact_cask_type": "",
                "fact_colouring": "",
            }
        )

    return rows


def scrape_whisky_exchange():
    all_data: List[dict] = []

    for cat_name, base_url in CATEGORIES.items():
        print(f"\n>>> Scraping: {cat_name} (target {TARGET_PER_CATEGORY})")

        seen_ids = set()
        category_rows: List[dict] = []

        for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
            if len(category_rows) >= TARGET_PER_CATEGORY:
                break

            url = f"{base_url}?pg={page}"
            print(f"    Fetching Page {page}... ({len(category_rows)}/{TARGET_PER_CATEGORY})")

            try:
                html = fetch_page(url)
                page_rows = parse_products(html, cat_name)
                if not page_rows:
                    print("    No products found on this page. Stopping category.")
                    break

                # Deduplicate per category + stop at target
                added = 0
                for r in page_rows:
                    pid = r.get("product_id", "")
                    if not pid or pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    category_rows.append(r)
                    added += 1
                    if len(category_rows) >= TARGET_PER_CATEGORY:
                        break

                print(f"    Added {added} new products (total {len(category_rows)}/{TARGET_PER_CATEGORY})")

                time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))

            except Exception as e:
                print(f"    Error on page {page}: {e}")
                break

        if len(category_rows) < TARGET_PER_CATEGORY:
            print(f"    Warning: only collected {len(category_rows)} products for {cat_name}.")

        all_data.extend(category_rows)

    print("\n>>> Enriching products (rating, reviews, display price, style, character, facts) ...")

    cache: dict[str, dict] = {}

    unique_urls = []
    seen_urls = set()
    for row in all_data:
        u = row.get("product_url", "")
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique_urls.append(u)

    total = len(unique_urls)
    print(f"    Unique product pages to enrich: {total}")

    # Enrich by URL (cache), then assign back to rows
    for idx, url in enumerate(unique_urls, start=1):
        # Find a representative row for nicer printing (name/id)
        sample_row = next((r for r in all_data if r.get("product_url") == url), {})
        pid = sample_row.get("product_id", "")
        name = (sample_row.get("name") or "").strip()

        line = f"    [{idx:>4}/{total}] Enriching ID={pid} | {name[:60]}"
        print(line)

        try:
            html = fetch_page(url)
            cache[url] = extract_product_metadata(html)
            time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))
        except Exception:
            cache[url] = {
                "rating_stars": "",
                "review_count": "",
                "price_inc_vat_gbp": "",
                "price_before_discount_gbp": "",
                "style_body": "",
                "style_richness": "",
                "style_smoke": "",
                "style_sweetness": "",
                "character_notes": "",
                "fact_bottler": "",
                "fact_country": "",
                "fact_region": "",
                "fact_cask_type": "",
                "fact_colouring": "",
            }
            print("         -> failed, stored blanks")

    # Assign to every row
    for row in all_data:
        url = row.get("product_url", "")
        if not url:
            continue
        meta = cache.get(url, {})

        row["rating_stars"] = meta.get("rating_stars", "")
        row["review_count"] = meta.get("review_count", "")
        row["price_inc_vat_gbp"] = meta.get("price_inc_vat_gbp", "")
        row["price_before_discount_gbp"] = meta.get("price_before_discount_gbp", "")

        row["style_body"] = meta.get("style_body", "")
        row["style_richness"] = meta.get("style_richness", "")
        row["style_smoke"] = meta.get("style_smoke", "")
        row["style_sweetness"] = meta.get("style_sweetness", "")

        row["character_notes"] = meta.get("character_notes", "")

        row["fact_bottler"] = meta.get("fact_bottler", "")
        row["fact_country"] = meta.get("fact_country", "")
        row["fact_region"] = meta.get("fact_region", "")
        row["fact_cask_type"] = meta.get("fact_cask_type", "")
        row["fact_colouring"] = meta.get("fact_colouring", "")

    if all_data:
        output = raw_data_path()
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_data[0].keys())
            writer.writeheader()
            writer.writerows(all_data)

        # Summary print
        cat_counts = {}
        for r in all_data:
            cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1

        print("\n>>> Done.")
        for k, v in cat_counts.items():
            print(f"    {k}: {v}")
        print(f"\nSuccess! Saved {len(all_data)} products to: {output}")


if __name__ == "__main__":
    scrape_whisky_exchange()
x