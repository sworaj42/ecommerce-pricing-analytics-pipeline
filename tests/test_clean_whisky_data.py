import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cleaning.clean_whisky_data import (
    apply_vat_fallback,
    clean_regions,
    engineer_age_size_abv_features,
    engineer_price_features,
    parse_bottle_size_and_abv,
    parse_unit_price,
    standardize_brands,
    standardize_missing_values,
)


def test_standardize_missing_values_coerces_known_tokens_to_na():
    df = pd.DataFrame({
        "brand": pd.array([" Macallan ", "n/a", "NONE", ""], dtype="string"),
    })
    out = standardize_missing_values(df)
    assert out["brand"].tolist()[0] == "Macallan"
    assert out["brand"].isna().sum() == 3


def test_standardize_brands_normalizes_known_variants_and_flags_placeholders():
    df = pd.DataFrame({
        "brand": pd.array(["chivas", " Chivas Regal ", "Unknown Distillery", "Macallan"], dtype="string"),
    })
    out = standardize_brands(df)
    assert out["brand"].tolist() == ["Chivas Regal", "Chivas Regal", "Independent/Unknown", "Macallan"]
    assert out["is_brand_placeholder"].tolist() == [False, False, True, False]


def test_clean_regions_drops_invalid_single_malt_regions_and_blended_regions():
    # fact_region is assumed already NA-normalized, since clean_regions runs
    # after standardize_missing_values in the real pipeline.
    df = pd.DataFrame({
        "category": pd.array(["Single Malt", "Single Malt", "Blended"], dtype="string"),
        "region": pd.array(["Islay", "Not A Real Region", "Highland"], dtype="string"),
        "fact_region": pd.array([pd.NA, pd.NA, pd.NA], dtype="string"),
    })
    out = clean_regions(df)
    assert out["region"].iloc[0] == "Islay"
    assert out["region"].isna().tolist() == [False, True, True]


def test_clean_regions_falls_back_to_fact_region_when_region_missing():
    df = pd.DataFrame({
        "category": pd.array(["Single Malt"], dtype="string"),
        "region": pd.array([pd.NA], dtype="string"),
        "fact_region": pd.array(["speyside"], dtype="string"),
    })
    out = clean_regions(df)
    assert out["region"].tolist() == ["Speyside"]


def test_apply_vat_fallback_fills_only_missing_values():
    df = pd.DataFrame({
        "price_ex_vat_gbp": [100.0, 50.0],
        "price_inc_vat_gbp": [None, 60.0],
    })
    out, filled = apply_vat_fallback(df)
    assert filled == 1
    assert out["price_inc_vat_gbp"].tolist() == [120.0, 60.0]


def test_parse_bottle_size_and_abv_extracts_from_variant():
    # Unit letters are matched lowercase-only, mirroring how the site formats variants.
    df = pd.DataFrame({
        "variant": pd.array(["70cl / 40%", "1l / 43%", "500ml / 46%"], dtype="string"),
    })
    out = parse_bottle_size_and_abv(df)
    assert out["bottle_size_cl"].tolist() == [70.0, 100.0, 50.0]
    assert out["abv_percent"].tolist() == [40.0, 43.0, 46.0]


def test_parse_unit_price_normalizes_to_gbp_per_litre():
    df = pd.DataFrame({
        "unit_price_raw": pd.array(["£50.00/ltr", "£25.00 per 70cl"], dtype="string"),
    })
    out = parse_unit_price(df)
    assert out["unit_price_gbp_per_litre"].tolist() == [50.0, round(25.0 / 70 * 100, 2)]


def test_engineer_price_features_computes_tier_and_discount_band():
    df = pd.DataFrame({
        "price_before_discount_gbp": [100.0, 200.0],
        "price_inc_vat_gbp": [90.0, 200.0],
        "bottle_size_l": [0.7, 0.7],
        "abv_percent": [40.0, 40.0],
    })
    out = engineer_price_features(df)
    assert out["is_discounted"].tolist() == [True, False]
    # reference price is 100 (Premium: 40-120) and 200 (Luxury: 120+)
    assert out["price_tier"].tolist() == ["Premium", "Luxury"]
    assert out["discount_percent"].tolist()[0] == 10.0


def test_engineer_age_size_abv_features_parses_age_from_name():
    df = pd.DataFrame({
        "name": pd.array(["Glenfiddich 12 Year Old", "Ardbeg 10YO", "No Age Statement"], dtype="string"),
        "bottle_size_l": [0.7, 0.7, 0.7],
        "abv_percent": [40.0, 46.0, 51.0],
    })
    out = engineer_age_size_abv_features(df)
    assert out["age_years"].iloc[0] == 12
    assert out["age_years"].iloc[1] == 10
    assert out["age_years"].isna().tolist() == [False, False, True]
    assert out["is_age_stated"].tolist() == [True, True, False]
    assert out["is_cask_strength"].tolist() == [False, False, True]
