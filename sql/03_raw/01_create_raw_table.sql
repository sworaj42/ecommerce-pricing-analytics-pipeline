-- 01_create_raw_table.sql 

USE WAREHOUSE WH_WHISKY;
USE DATABASE WHISKY_DWH;
USE SCHEMA RAW;

DROP TABLE IF EXISTS WHISKY_PRODUCTS_RAW;

CREATE TABLE WHISKY_PRODUCTS_RAW (

  -- Metadata
  scraped_at VARCHAR,

  -- Identifiers & classification
  category VARCHAR,
  product_id VARCHAR,
  name VARCHAR,
  brand VARCHAR,
  region VARCHAR,
  is_brand_placeholder VARCHAR,

  -- URLs
  product_url VARCHAR,
  image_url VARCHAR,

  -- Pricing (raw values, still VARCHAR by design)
  price_ex_vat_gbp VARCHAR,
  price_inc_vat_gbp VARCHAR,
  price_before_discount_gbp VARCHAR,
  unit_price_gbp_per_litre VARCHAR,
  reference_price_gbp VARCHAR,

  -- Alcohol & value metrics
  bottle_size_l VARCHAR,
  bottle_size_cl VARCHAR,
  abv_percent VARCHAR,
  alcohol_units VARCHAR,
  price_per_alcohol_unit_gbp VARCHAR,

  -- Discount analytics
  discount_amount_gbp VARCHAR,
  discount_percent VARCHAR,
  discount_band VARCHAR,
  is_discounted VARCHAR,
  price_tier VARCHAR,

  -- Age & strength
  age_years VARCHAR,
  is_age_stated VARCHAR,
  age_band VARCHAR,
  is_cask_strength VARCHAR,

  -- Bottle size & ABV groupings
  bottle_size_band VARCHAR,
  abv_band VARCHAR,
  is_standard_bottle VARCHAR,
  is_comparable_bottle VARCHAR,

  -- Outlier flags (added during cleaning)
  is_price_outlier VARCHAR,
  is_value_outlier VARCHAR,
  is_outlier VARCHAR,

  -- Ratings
  rating_stars VARCHAR,
  review_count VARCHAR,

  -- Taste profile
  style_body VARCHAR,
  style_richness VARCHAR,
  style_smoke VARCHAR,
  style_sweetness VARCHAR,
  character_notes VARCHAR,

  -- Facts
  fact_bottler VARCHAR,
  fact_country VARCHAR,
  fact_cask_type VARCHAR,
  fact_colouring VARCHAR

);
