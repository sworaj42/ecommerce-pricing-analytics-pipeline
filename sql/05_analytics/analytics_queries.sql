-- analytics_queries.sql
-- Purpose:
-- 1) Validate curated views created in the CURATED schema
-- 2) Support exploratory analysis and result verification
-- 3) Provide reproducible SQL outputs for documentation/screenshots
--
-- NOTE:
-- - No CREATE / REPLACE statements here
-- - Complex business logic is encapsulated in Snowflake views
-- - This file contains SELECT-only analytical queries

USE DATABASE WHISKY_DWH;
USE SCHEMA CURATED;

--------------------------------------------------------------------------------
-- A) Simple Aggregations
-- These queries are intentionally kept as SELECTs.
-- They are lightweight, easy to reproduce in BI tools,
-- and do not warrant permanent views.
--------------------------------------------------------------------------------

-- 1) Brand-level price and quality positioning
SELECT
  brand,
  COUNT(*) AS sku_count,
  ROUND(MEDIAN(price_inc_vat_gbp), 2) AS median_price_gbp,
  ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price_gbp,
  ROUND(MIN(price_inc_vat_gbp), 2) AS min_price_gbp,
  ROUND(MAX(price_inc_vat_gbp), 2) AS max_price_gbp,
  ROUND(
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY price_inc_vat_gbp)
    - PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY price_inc_vat_gbp),
    2
  ) AS p10_p90_spread_gbp,
  ROUND(AVG(rating_stars), 2) AS avg_catalog_rating,
  ROUND(
    SUM(rating_stars * review_count) / NULLIF(SUM(review_count), 0),
    2
  ) AS weighted_consumer_rating,
  ROUND(AVG(IFF(is_discounted, 1, 0)) * 100, 1) AS pct_skus_on_sale_now
FROM VW_PRODUCT_LATEST
WHERE price_inc_vat_gbp IS NOT NULL
  AND rating_stars IS NOT NULL
  AND review_count IS NOT NULL
  AND brand IS NOT NULL
GROUP BY brand
HAVING COUNT(*) >= 5
ORDER BY median_price_gbp DESC;


-- 2) Region-level pricing, quality, and promotion analysis
SELECT
  region,
  COUNT(*) AS sku_count,
  ROUND(MEDIAN(price_inc_vat_gbp), 2) AS median_price_gbp,
  ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price_gbp,
  ROUND(MIN(price_inc_vat_gbp), 2) AS min_price_gbp,
  ROUND(MAX(price_inc_vat_gbp), 2) AS max_price_gbp,
  ROUND(
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY price_inc_vat_gbp)
    - PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY price_inc_vat_gbp),
    2
  ) AS p10_p90_spread_gbp,
  ROUND(AVG(rating_stars), 2) AS avg_catalog_rating,
  ROUND(
    SUM(rating_stars * review_count) / NULLIF(SUM(review_count), 0),
    2
  ) AS weighted_consumer_rating,
  SUM(review_count) AS total_reviews,
  ROUND(AVG(IFF(is_discounted, 1, 0)) * 100, 2) AS pct_skus_discounted_now
FROM VW_PRODUCT_LATEST
WHERE region IS NOT NULL
  AND price_inc_vat_gbp IS NOT NULL
  AND rating_stars IS NOT NULL
  AND review_count IS NOT NULL
  AND category = 'Single Malt'
  AND is_comparable_bottle = TRUE
GROUP BY region
HAVING COUNT(*) >= 5
ORDER BY avg_price_gbp DESC;


-- 3) Best value-for-money whiskies (top 20)
SELECT
  product_id,
  name,
  brand,
  region,
  bottle_size_l,
  rating_stars,
  review_count,
  price_inc_vat_gbp,
  alcohol_units,
  price_per_alcohol_unit_gbp,
  ROUND(rating_stars / NULLIF(price_per_alcohol_unit_gbp, 0), 2) AS value_score
FROM VW_PRODUCT_LATEST
WHERE is_standard_bottle = TRUE
  AND price_per_alcohol_unit_gbp IS NOT NULL
  AND rating_stars IS NOT NULL
  AND review_count IS NOT NULL
  AND rating_stars >= 4.0
  AND review_count >= 50
ORDER BY value_score DESC
LIMIT 20;


-- 4) Discount strategy overview (current discounts only)
SELECT
  discount_band,
  COUNT(*) AS discounted_skus_now,
  ROUND(AVG(discount_percent), 2) AS avg_discount_pct,
  ROUND(AVG(discount_amount_gbp), 2) AS avg_discount_amount_gbp,
  ROUND(MIN(discount_percent), 2) AS min_discount_pct,
  ROUND(MAX(discount_percent), 2) AS max_discount_pct
FROM VW_PRODUCT_LATEST
WHERE is_discounted = TRUE
  AND discount_percent IS NOT NULL
GROUP BY discount_band
ORDER BY avg_discount_pct DESC;

--------------------------------------------------------------------------------
-- B) Complex Analytical Outputs
-- These results are sourced from Snowflake views.
-- Views ensure consistency, reusability, and BI compatibility.
--------------------------------------------------------------------------------

-- 5) Top 3 Brands, Regions, and Individual Whiskies by weighted rating
SELECT *
FROM VW_TOP3_RATINGS
ORDER BY entity_type, weighted_rating DESC, total_reviews DESC;


-- 6) Price Premium Decomposition across key dimensions
SELECT *
FROM VW_PRICE_PREMIUM_DECOMP
ORDER BY factor, vs_baseline_gbp DESC NULLS LAST;


-- 7) Age Statement ROI and diminishing returns analysis
SELECT *
FROM VW_AGE_ROI
ORDER BY avg_age_years;
