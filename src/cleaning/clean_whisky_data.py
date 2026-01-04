import re
import numpy as np
import pandas as pd


# ----------------------------
# Config
# ----------------------------
RAW_PATH = "../data/raw/whisky_raw.csv"
OUT_PATH = "../data/processed/whisky_cleaned.csv"

MISSING_TOKENS = {"", "none", "n/a", "na", "nan", "null", "undefined"}

VALID_REGIONS = {"highland", "islay", "speyside", "lowland", "campbeltown", "island"}

BRAND_REPLACEMENTS_CI = {
    "chivas": "Chivas Regal",
    "various distilleries": "Independent/Unknown",
    "undisclosed distillery": "Independent/Unknown",
    "unknown distillery": "Independent/Unknown",
    "secret distillery": "Independent/Unknown",
}

PLACEHOLDER_BRAND = "Independent/Unknown"


def _require_cols(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def main() -> None:
    # ----------------------------
    # Load
    # ----------------------------
    df = pd.read_csv(RAW_PATH)

    # ----------------------------
    # Column names
    # ----------------------------
    df.columns = df.columns.str.strip()

    required_cols = [
        "scraped_at", "product_id", "price_gbp",
        "category", "name", "brand", "variant",
        "unit_price_raw", "region", "promo_label",
        "product_url", "image_url"
    ]
    _require_cols(df, required_cols)

    # ----------------------------
    # Drop status if no variance
    # ----------------------------
    if "status" in df.columns and df["status"].nunique(dropna=False) <= 1:
        df = df.drop(columns=["status"])

    # ----------------------------
    # Enforce schema (safe + consistent types)
    # ----------------------------
    df = df.assign(
        scraped_at=pd.to_datetime(df["scraped_at"], errors="coerce"),
        product_id=pd.to_numeric(df["product_id"], errors="coerce").astype("Int64"),
        price_gbp=pd.to_numeric(df["price_gbp"], errors="coerce"),

        category=df["category"].astype("string"),
        name=df["name"].astype("string"),
        brand=df["brand"].astype("string"),
        variant=df["variant"].astype("string"),
        unit_price_raw=df["unit_price_raw"].astype("string"),
        region=df["region"].astype("string"),
        promo_label=df["promo_label"].astype("string"),
        product_url=df["product_url"].astype("string"),
        image_url=df["image_url"].astype("string"),
    )

    # ----------------------------
    # Deduplicate (ignore scraped_at)
    # ----------------------------
    dedup_cols = [c for c in df.columns if c != "scraped_at"]
    df = df.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    # ----------------------------
    # Standardize missing values in text columns
    # ----------------------------
    text_cols = df.select_dtypes(include="string").columns
    df[text_cols] = df[text_cols].apply(lambda s: s.str.strip())

    for col in text_cols:
        lower = df[col].str.lower()
        df[col] = df[col].where(~lower.isin(MISSING_TOKENS), pd.NA)

    # ----------------------------
    # Region cleaning
    # ----------------------------
    # Make region lowercase for logic
    df["region"] = df["region"].astype("string").str.lower()

    # Blended => region not applicable
    df.loc[df["category"].str.lower() == "blended", "region"] = pd.NA

    # Single malt invalid region labels => NA
    df.loc[
        (df["category"].str.lower() == "single malt") &
        (~df["region"].isin(list(VALID_REGIONS))),
        "region"
    ] = pd.NA

    # Presentation formatting
    df["region"] = df["region"].str.capitalize()

    # ----------------------------
    # Brand standardization
    # ----------------------------
    df["brand"] = (
        df["brand"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    brand_key_tmp = df["brand"].str.lower()
    df["brand"] = brand_key_tmp.map(BRAND_REPLACEMENTS_CI).fillna(df["brand"])

    df["is_brand_placeholder"] = df["brand"].eq(PLACEHOLDER_BRAND)

    # ----------------------------
    # Parse bottle size + ABV from variant
    # ----------------------------
    df["bottle_size_cl"] = (
        df["variant"]
        .str.extract(r"(\d+(?:\.\d+)?)\s*cl", expand=False)
        .astype(float)
    )

    df["bottle_size_l"] = df["bottle_size_cl"] / 100

    df["abv_percent"] = (
        df["variant"]
        .str.extract(r"(\d+(?:\.\d+)?)\s*%", expand=False)
        .astype(float)
    )

    # ----------------------------
    # Parse unit price to GBP per litre (site-reported)
    # ----------------------------
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
        .str.extract(r"(?:per|/)\s*([0-9]+(?:\.[0-9]+)?\s*)?(ml|cl|l|litre|liter)", expand=True)
    )
    qty = pd.to_numeric(basis[0].astype("string").str.strip(), errors="coerce")
    unit = basis[1].astype("string").replace({"liter": "litre"})

    mask_litre = ((unit == "litre") | (unit == "l")) & qty.isna()
    qty.loc[mask_litre] = 1.0

    scale = pd.Series(np.nan, index=df.index, dtype="float64")

    mask_ml = (unit == "ml") & qty.notna()
    scale.loc[mask_ml] = 1000 / qty.loc[mask_ml]

    mask_cl = (unit == "cl") & qty.notna()
    scale.loc[mask_cl] = 100 / qty.loc[mask_cl]

    mask_l = ((unit == "litre") | (unit == "l")) & qty.notna()
    scale.loc[mask_l] = 1.0 / qty.loc[mask_l]

    df["unit_price_gbp_per_litre"] = (df["unit_price_gbp_per_litre"] * scale).round(2)

    # ----------------------------
    # Discount extraction + pre-discount price reconstruction
    # ----------------------------
    df["discount_amount_gbp"] = (
        df["promo_label"]
        .astype("string")
        .str.lower()
        .str.replace(",", "", regex=False)
        .str.extract(r"£\s*(\d+(?:\.\d+)?)", expand=False)
    )
    df["discount_amount_gbp"] = pd.to_numeric(df["discount_amount_gbp"], errors="coerce")

    df["is_discounted"] = df["discount_amount_gbp"].notna()

    # Pre-discount (calculated) price
    df["price_pre_discount_calc_gbp"] = df["price_gbp"] + df["discount_amount_gbp"].fillna(0)

    # ----------------------------
    # Feature engineering
    # ----------------------------
    df["true_price_gbp"] = df["price_pre_discount_calc_gbp"]

    df["true_unit_price_per_l"] = (df["true_price_gbp"] / df["bottle_size_l"]).round(2)

    # UK alcohol units: bottle_size_l * abv_percent (works because abv_percent is %)
    df["alcohol_units"] = df["bottle_size_l"] * df["abv_percent"]

    df["true_price_per_alcohol_unit_gbp"] = (df["true_price_gbp"] / df["alcohol_units"]).round(2)

    df["price_tier"] = pd.cut(
        df["true_price_gbp"],
        bins=[0, 40, 120, float("inf")],
        labels=["Budget", "Premium", "Luxury"],
        right=False
    )

    df["discount_percent"] = (
        (df["true_price_gbp"] - df["price_gbp"]) / df["true_price_gbp"] * 100
    ).round(2)
    df.loc[df["discount_amount_gbp"].isna(), "discount_percent"] = 0

    df["discount_band"] = pd.cut(
        df["discount_percent"],
        bins=[-0.01, 0, 10, 20, 40, float("inf")],
        labels=["No Discount", "Low (≤10%)", "Medium (10–20%)", "High (20–40%)", "Very High (>40%)"]
    )

    df["age_years"] = (
        df["name"]
        .str.extract(r"\b(\d{1,2})\s*(?:year|years|yo)\b", flags=re.IGNORECASE, expand=False)
        .astype("float")
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
        labels=["Small (≤35cl)", "Standard (70cl)", "Large (1L)", "Extra Large (>1L)"]
    )

    df["abv_band"] = pd.cut(
        df["abv_percent"],
        bins=[0, 40, 43, 46, 50, float("inf")],
        labels=["≤40%", "40–43%", "43–46%", "46–50%", "50%+"]
    )

    df["is_cask_strength"] = df["abv_percent"] >= 50

    # Optional: replace inf from divide-by-zero (if bottle_size_l missing)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

    # ----------------------------
    # Save
    # ----------------------------
    df.to_csv(OUT_PATH, index=False)


if __name__ == "__main__":
    main()
