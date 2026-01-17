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
    "chivas regal": "Chivas Regal",

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
    # Load + column names
    # ----------------------------
    df = pd.read_csv(RAW_PATH)
    df.columns = df.columns.str.strip()

    required_cols = [
        "scraped_at", "category", "product_id", "name", "brand", "variant",
        "price_ex_vat_gbp", "unit_price_raw", "region", "promo_label", "status",
        "product_url", "image_url",
        "rating_stars", "review_count",
        "price_inc_vat_gbp", "price_before_discount_gbp",
        "style_body", "style_richness", "style_smoke", "style_sweetness",
        "character_notes",
        "fact_bottler", "fact_country", "fact_region", "fact_cask_type", "fact_colouring",
    ]
    _require_cols(df, required_cols)

    # ----------------------------
    # Drop status if no variance
    # ----------------------------
    if "status" in df.columns and df["status"].nunique(dropna=False) <= 1:
        df = df.drop(columns=["status"])

    # ----------------------------
    # Enforce schema
    # ----------------------------
    df = df.assign(
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

    # ----------------------------
    # Deduplicate
    # ----------------------------
    dedup_cols = [c for c in df.columns if c != "scraped_at"]
    df = df.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    df = (
        df.sort_values("scraped_at")
          .drop_duplicates(subset=["product_id"], keep="last")
          .reset_index(drop=True)
    )

    # ----------------------------
    # Standardize missing values (text)
    # ----------------------------
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

    # ----------------------------
    # Region cleaning (before consolidation)
    # ----------------------------
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

    # ----------------------------
    # Consolidate region with fact_region
    # ----------------------------
    df["fact_region"] = (
        df["fact_region"]
        .astype("string")
        .str.strip()
        .str.lower()
        .replace({"islands": "island", "the islands": "island"})
    )

    df["region"] = df["region"].fillna(df["fact_region"])
    df["region"] = df["region"].str.capitalize()
    df = df.drop(columns=["fact_region"])

    # ----------------------------
    # Brand standardization
    # ----------------------------
    df["brand"] = (
        df["brand"]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    brand_key_tmp = df["brand"].str.lower()
    df["brand"] = brand_key_tmp.map(BRAND_REPLACEMENTS_CI).fillna(df["brand"])
    df["is_brand_placeholder"] = df["brand"].eq(PLACEHOLDER_BRAND)

    # ----------------------------
    # VAT fallback: fill missing price_inc_vat_gbp from price_ex_vat_gbp
    # ----------------------------
    missing_before = df["price_inc_vat_gbp"].isna().sum()
    df["price_inc_vat_calc_gbp"] = (df["price_ex_vat_gbp"] * 1.2).round(2)
    df["price_inc_vat_gbp"] = df["price_inc_vat_gbp"].fillna(df["price_inc_vat_calc_gbp"])
    filled = missing_before - df["price_inc_vat_gbp"].isna().sum()

    # Keep this calc column or drop it — your choice
    df = df.drop(columns=["price_inc_vat_calc_gbp"])

    # ----------------------------
    # Parse bottle size + ABV from variant (ml/cl/l)
    # ----------------------------
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

    # ----------------------------
    # Parse unit price to GBP per litre
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

    # ----------------------------
    # Feature engineering: prices + discounts
    # ----------------------------
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

    # ----------------------------
    # Feature engineering: age/size/abv
    # ----------------------------
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

    # ----------------------------
    # Safety: replace inf/-inf in numeric cols
    # ----------------------------
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

    # ----------------------------
    # Save
    # ----------------------------
    df.to_csv(OUT_PATH, index=False)

    # Lightweight terminal validation (minimal, useful)
    print(f"Saved cleaned dataset: {OUT_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Filled price_inc_vat_gbp using VAT fallback: {filled}")
    print("Discounted products:", int(df["is_discounted"].sum()))


if __name__ == "__main__":
    main()
