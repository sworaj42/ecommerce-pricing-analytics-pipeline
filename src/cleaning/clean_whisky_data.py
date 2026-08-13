"""
Whisky Pricing Data Cleaner
============================
Transforms a raw scraped product CSV into an analytics-ready dataset:
schema enforcement, deduplication, missing-value standardization,
region/brand normalization, and derived pricing/age/size feature
engineering (price tier, discount band, age band, value metrics).

Usage:
  python clean_whisky_data.py                                  # latest raw CSV -> data/processed/
  python clean_whisky_data.py --input path/to/raw.csv           # explicit input
  python clean_whisky_data.py --input in.csv --output out.csv   # explicit input + output
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.logging_utils import get_logger
from src.utils.paths import PROCESSED_DATA_DIR, RAW_DATA_DIR, ensure_dir, latest_file

logger = get_logger(__name__)


# ─── Config ──────────────────────────────────────────────────
REQUIRED_COLUMNS = [
    "scraped_at", "category", "product_id", "name", "brand", "variant",
    "price_ex_vat_gbp", "unit_price_raw", "region", "promo_label", "status",
    "product_url", "image_url",
    "rating_stars", "review_count",
    "price_inc_vat_gbp", "price_before_discount_gbp",
    "style_body", "style_richness", "style_smoke", "style_sweetness",
    "character_notes",
    "fact_bottler", "fact_country", "fact_region", "fact_cask_type", "fact_colouring",
]

MISSING_TOKENS = {"", "none", "n/a", "na", "nan", "null", "undefined"}
VALID_REGIONS = {"highland", "islay", "speyside", "lowland", "campbeltown", "island"}

BRAND_REPLACEMENTS_CI = {
    "chivas": "Chivas Regal",
    "chivas regal": "Chivas Regal",

    "various distilleries": "Independent/Unknown",
    "undisclosed distillery": "Independent/Unknown",
    "unknown distillery": "Independent/Unknown",
    "secret distillery": "Independent/Unknown",
}

PLACEHOLDER_BRAND = "Independent/Unknown"


# ─── Load ────────────────────────────────────────────────────
def load_raw_data(path: Path) -> pd.DataFrame:
    """Read the raw CSV and validate that all required columns are present."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df


def drop_constant_status(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the `status` column if every row shares the same value (no signal)."""
    if "status" in df.columns and df["status"].nunique(dropna=False) <= 1:
        df = df.drop(columns=["status"])
    return df


# ─── Schema + dedup ──────────────────────────────────────────
def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Cast every column to its target dtype."""
    return df.assign(
        scraped_at=pd.to_datetime(df["scraped_at"], errors="coerce"),
        product_id=pd.to_numeric(df["product_id"], errors="coerce").astype("Int64"),

        price_ex_vat_gbp=pd.to_numeric(df["price_ex_vat_gbp"], errors="coerce"),
        price_inc_vat_gbp=pd.to_numeric(df["price_inc_vat_gbp"], errors="coerce"),
        price_before_discount_gbp=pd.to_numeric(df["price_before_discount_gbp"], errors="coerce"),

        rating_stars=pd.to_numeric(df["rating_stars"], errors="coerce"),
        review_count=pd.to_numeric(df["review_count"], errors="coerce").astype("Int64"),

        style_body=pd.to_numeric(df["style_body"], errors="coerce").astype("Int64"),
        style_richness=pd.to_numeric(df["style_richness"], errors="coerce").astype("Int64"),
        style_smoke=pd.to_numeric(df["style_smoke"], errors="coerce").astype("Int64"),
        style_sweetness=pd.to_numeric(df["style_sweetness"], errors="coerce").astype("Int64"),

        category=df["category"].astype("string"),
        name=df["name"].astype("string"),
        brand=df["brand"].astype("string"),
        variant=df["variant"].astype("string"),
        unit_price_raw=df["unit_price_raw"].astype("string"),
        region=df["region"].astype("string"),
        promo_label=df["promo_label"].astype("string"),
        product_url=df["product_url"].astype("string"),
        image_url=df["image_url"].astype("string"),

        character_notes=df["character_notes"].astype("string"),
        fact_bottler=df["fact_bottler"].astype("string"),
        fact_country=df["fact_country"].astype("string"),
        fact_region=df["fact_region"].astype("string"),
        fact_cask_type=df["fact_cask_type"].astype("string"),
        fact_colouring=df["fact_colouring"].astype("string"),
    )


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact duplicate rows, then keep the most recent snapshot per product."""
    dedup_cols = [c for c in df.columns if c != "scraped_at"]
    df = df.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    return (
        df.sort_values("scraped_at")
          .drop_duplicates(subset=["product_id"], keep="last")
          .reset_index(drop=True)
    )


# ─── Missing values + text normalization ────────────────────
def standardize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace on text columns and coerce known missing-value tokens to NA."""
    text_cols = [
        c for c in df.select_dtypes(include="string").columns
        if c not in {"product_url", "image_url"}
    ]
    df[text_cols] = df[text_cols].apply(lambda s: s.str.strip())

    for col in text_cols:
        df[col] = df[col].where(~df[col].str.lower().isin(MISSING_TOKENS), pd.NA)

    if "character_notes" in df.columns:
        df["character_notes"] = (
            df["character_notes"]
            .str.replace(r"\s*\|\s*", "|", regex=True)
            .str.strip("|")
        )

    return df


def clean_regions(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize region text, drop invalid single-malt regions, and consolidate
    with the `fact_region` field scraped from the product-facts panel."""
    df["region"] = (
        df["region"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace({"islands": "island", "the islands": "island"})
    )

    df.loc[df["category"].str.lower() == "blended", "region"] = pd.NA

    df.loc[
        (df["category"].str.lower() == "single malt") &
        (~df["region"].isin(list(VALID_REGIONS))),
        "region"
    ] = pd.NA

    df["fact_region"] = (
        df["fact_region"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace({"islands": "island", "the islands": "island"})
    )

    df["region"] = df["region"].fillna(df["fact_region"])
    df["region"] = df["region"].str.capitalize()
    return df.drop(columns=["fact_region"])


def standardize_brands(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize brand spelling/casing and flag placeholder ("unknown distillery") brands."""
    df["brand"] = (
        df["brand"]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    brand_key = df["brand"].str.lower()
    df["brand"] = brand_key.map(BRAND_REPLACEMENTS_CI).fillna(df["brand"])
    df["is_brand_placeholder"] = df["brand"].eq(PLACEHOLDER_BRAND)
    return df


# ─── Price parsing ───────────────────────────────────────────
def apply_vat_fallback(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Fill missing `price_inc_vat_gbp` from the ex-VAT price where needed.

    Returns the updated frame and the number of rows filled.
    """
    missing_before = df["price_inc_vat_gbp"].isna().sum()
    price_inc_vat_calc = (df["price_ex_vat_gbp"] * 1.2).round(2)
    df["price_inc_vat_gbp"] = df["price_inc_vat_gbp"].fillna(price_inc_vat_calc)
    filled = missing_before - df["price_inc_vat_gbp"].isna().sum()
    return df, int(filled)


def parse_bottle_size_and_abv(df: pd.DataFrame) -> pd.DataFrame:
    """Extract bottle size (litres/cl) and ABV percentage from the `variant` field."""
    vol_amount = pd.to_numeric(
        df["variant"].str.extract(r"(\d+(?:\.\d+)?)\s*(?:ml|cl|l|litre|liter)", expand=False),
        errors="coerce"
    )
    vol_unit = df["variant"].str.extract(
        r"(\d+(?:\.\d+)?)\s*(ml|cl|l|litre|liter)",
        flags=re.IGNORECASE
    )[1].str.lower()

    df["bottle_size_l"] = pd.NA
    df.loc[vol_unit == "ml", "bottle_size_l"] = vol_amount / 1000
    df.loc[vol_unit == "cl", "bottle_size_l"] = vol_amount / 100
    df.loc[vol_unit.isin(["l", "litre", "liter"]), "bottle_size_l"] = vol_amount
    df["bottle_size_l"] = pd.to_numeric(df["bottle_size_l"], errors="coerce")
    df["bottle_size_cl"] = (df["bottle_size_l"] * 100).round(2)

    df["abv_percent"] = pd.to_numeric(
        df["variant"].str.extract(r"(\d+(?:\.\d+)?)\s*%", expand=False),
        errors="coerce"
    )
    return df


def parse_unit_price(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the scraped unit-price string into GBP per litre."""
    df["unit_price_gbp_per_litre"] = (
        df["unit_price_raw"]
          .astype("string")
          .str.replace("£", "", regex=False)
          .str.replace(",", "", regex=False)
          .str.extract(r"(\d+(?:\.\d+)?)", expand=False)
    )
    df["unit_price_gbp_per_litre"] = pd.to_numeric(df["unit_price_gbp_per_litre"], errors="coerce")

    basis = (
        df["unit_price_raw"]
          .astype("string")
          .str.lower()
          .str.replace(",", "", regex=False)
          .str.extract(r"(?:per|/)\s*([0-9]+(?:\.[0-9]+)?\s*)?(ml|cl|l|litre|liter)", expand=False)
    )
    qty = pd.to_numeric(basis[0].astype("string").str.strip(), errors="coerce")
    unit = basis[1].astype("string").replace({"liter": "litre"})

    mask_litre = ((unit == "litre") | (unit == "l")) & qty.isna()
    qty.loc[mask_litre] = 1.0

    scale = pd.Series(1.0, index=df.index, dtype="float64")

    mask_ml = (unit == "ml") & qty.notna()
    scale.loc[mask_ml] = 1000 / qty.loc[mask_ml]

    mask_cl = (unit == "cl") & qty.notna()
    scale.loc[mask_cl] = 100 / qty.loc[mask_cl]

    mask_l = ((unit == "litre") | (unit == "l")) & qty.notna()
    scale.loc[mask_l] = 1.0 / qty.loc[mask_l]

    df["unit_price_gbp_per_litre"] = (df["unit_price_gbp_per_litre"] * scale).round(2)
    return df


# ─── Feature engineering ─────────────────────────────────────
def engineer_price_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive reference price, price-per-alcohol-unit, price tier, and discount metrics."""
    df["reference_price_gbp"] = df["price_before_discount_gbp"].fillna(df["price_inc_vat_gbp"])

    df["alcohol_units"] = df["bottle_size_l"] * df["abv_percent"]
    df["price_per_alcohol_unit_gbp"] = (df["reference_price_gbp"] / df["alcohol_units"]).round(2)

    df["price_tier"] = pd.cut(
        df["reference_price_gbp"],
        bins=[0, 40, 120, float("inf")],
        labels=["Budget", "Premium", "Luxury"],
        right=False
    )

    df["discount_amount_gbp"] = df["price_before_discount_gbp"] - df["price_inc_vat_gbp"]
    df.loc[df["discount_amount_gbp"] <= 0, "discount_amount_gbp"] = pd.NA

    df["is_discounted"] = df["discount_amount_gbp"].notna()

    df["discount_percent"] = ((df["discount_amount_gbp"] / df["price_before_discount_gbp"]) * 100).round(2)
    df.loc[~df["is_discounted"], "discount_percent"] = 0

    df["discount_band"] = pd.cut(
        df["discount_percent"],
        bins=[-0.01, 0, 10, 20, 40, float("inf")],
        labels=["No Discount", "Low (≤10%)", "Medium (10–20%)", "High (20–40%)", "Very High (>40%)"]
    )
    return df


def engineer_age_size_abv_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive age, bottle size, and ABV bands from the parsed product fields."""
    df["age_years"] = pd.to_numeric(
        df["name"].astype("string").str.extract(
            r"\b(\d{1,2})\s*(?:year(?:s)?(?:\s+old)?|yo)\b",
            flags=re.IGNORECASE,
            expand=False
        ),
        errors="coerce"
    )

    df["is_age_stated"] = df["age_years"].notna()

    df["age_band"] = pd.cut(
        df["age_years"],
        bins=[0, 10, 15, 18, 25, float("inf")],
        labels=["≤10", "11–15", "16–18", "19–25", "25+"]
    )

    df["bottle_size_band"] = pd.cut(
        df["bottle_size_l"],
        bins=[0, 0.35, 0.7, 1.0, float("inf")],
        labels=["Mini/Small (≤35cl)", "Half–Standard (35–70cl)", "Standard–Large (70cl–1L)", "Extra Large (>1L)"]
    )

    df["abv_band"] = pd.cut(
        df["abv_percent"],
        bins=[0, 40, 43, 46, 50, float("inf")],
        labels=["≤40%", "40–43%", "43–46%", "46–50%", "50%+"]
    )

    df["is_cask_strength"] = df["abv_percent"] >= 50
    return df


def sanitize_numeric_infinities(df: pd.DataFrame) -> pd.DataFrame:
    """Replace any +/-inf produced by division (e.g. zero-ABV edge cases) with NaN."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return df


# ─── Orchestration ───────────────────────────────────────────
def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Run the full cleaning + feature-engineering pipeline on a raw dataframe."""
    df = drop_constant_status(df)
    df = enforce_schema(df)
    df = deduplicate(df)
    df = standardize_missing_values(df)
    df = clean_regions(df)
    df = standardize_brands(df)
    df, vat_filled = apply_vat_fallback(df)
    df = parse_bottle_size_and_abv(df)
    df = parse_unit_price(df)
    df = engineer_price_features(df)
    df = engineer_age_size_abv_features(df)
    df = sanitize_numeric_infinities(df)
    return df, vat_filled


def resolve_input_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return latest_file(RAW_DATA_DIR, "whisky_raw*.csv")


def resolve_output_path(explicit: str | None, input_path: Path) -> Path:
    if explicit:
        return Path(explicit)
    date_suffix = re.search(r"(\d{4}-\d{2}-\d{2})", input_path.stem)
    tag = date_suffix.group(1) if date_suffix else date.today().isoformat()
    return ensure_dir(PROCESSED_DATA_DIR) / f"whisky_cleaned_{tag}.csv"


def main(input_path: str | None = None, output_path: str | None = None) -> None:
    in_path = resolve_input_path(input_path)
    out_path = resolve_output_path(output_path, in_path)

    logger.info("Loading raw data: %s", in_path)
    df = load_raw_data(in_path)

    df, vat_filled = clean(df)

    df.to_csv(out_path, index=False)

    logger.info("Saved cleaned dataset: %s", out_path)
    logger.info("Rows: %d", len(df))
    logger.info("Filled price_inc_vat_gbp using VAT fallback: %d", vat_filled)
    logger.info("Discounted products: %d", int(df["is_discounted"].sum()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and enrich raw whisky product data")
    parser.add_argument("--input", help="Path to raw CSV (default: latest file in data/raw/)")
    parser.add_argument("--output", help="Path to write cleaned CSV (default: data/processed/whisky_cleaned_<date>.csv)")
    args = parser.parse_args()

    main(args.input, args.output)
