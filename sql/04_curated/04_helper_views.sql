USE DATABASE WHISKY_DWH;
USE SCHEMA CURATED;

--------------------------------------------------------------------------------
-- 1) Latest product view (latest scraped snapshot per product)
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_PRODUCT_LATEST AS
SELECT *
FROM VW_PRODUCT_SNAPSHOT
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY product_id
  ORDER BY full_date DESC
) = 1;

--------------------------------------------------------------------------------
-- 2) Top 3 Brands, Regions, and Whiskies by weighted rating
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_TOP3_RATINGS AS
WITH
brand_ratings AS (
  SELECT
    'Brand' AS entity_type,
    brand AS entity_name,
    COUNT(*) AS sku_count,
    SUM(review_count) AS total_reviews,
    ROUND(SUM(rating_stars * review_count) / NULLIF(SUM(review_count), 0), 2) AS weighted_rating
  FROM VW_PRODUCT_LATEST
  WHERE brand IS NOT NULL
    AND rating_stars IS NOT NULL
    AND review_count IS NOT NULL
  GROUP BY brand
  HAVING SUM(review_count) >= 200
),
region_ratings AS (
  SELECT
    'Region' AS entity_type,
    region AS entity_name,
    COUNT(*) AS sku_count,
    SUM(review_count) AS total_reviews,
    ROUND(SUM(rating_stars * review_count) / NULLIF(SUM(review_count), 0), 2) AS weighted_rating
  FROM VW_PRODUCT_LATEST
  WHERE region IS NOT NULL
    AND rating_stars IS NOT NULL
    AND review_count IS NOT NULL
  GROUP BY region
  HAVING SUM(review_count) >= 200
),
whisky_ratings AS (
  SELECT
    'Whisky' AS entity_type,
    CAST(product_id AS VARCHAR) AS entity_name,
    1 AS sku_count,
    review_count AS total_reviews,
    ROUND(rating_stars, 2) AS weighted_rating
  FROM VW_PRODUCT_LATEST
  WHERE rating_stars IS NOT NULL
    AND review_count IS NOT NULL
    AND review_count >= 50
),
all_rows AS (
  SELECT * FROM brand_ratings
  UNION ALL
  SELECT * FROM region_ratings
  UNION ALL
  SELECT * FROM whisky_ratings
),
ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY entity_type
      ORDER BY weighted_rating DESC, total_reviews DESC
    ) AS rn
  FROM all_rows
)
SELECT
  entity_type,
  entity_name,
  sku_count,
  total_reviews,
  weighted_rating
FROM ranked
WHERE rn <= 3;

--------------------------------------------------------------------------------
-- 3) Price Premium Decomposition
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_PRICE_PREMIUM_DECOMP AS
WITH
baseline AS (
  SELECT
    MEDIAN(price_inc_vat_gbp) AS base_price,
    COUNT(DISTINCT product_id) AS total_skus
  FROM VW_PRODUCT_LATEST
  WHERE is_comparable_bottle = TRUE
    AND price_inc_vat_gbp IS NOT NULL
),
b AS (SELECT base_price, total_skus FROM baseline),
age_tiers AS (
  SELECT
    CASE
      WHEN age_years BETWEEN 1 AND 9 THEN '01-09'
      WHEN age_years BETWEEN 10 AND 12 THEN '10-12'
      WHEN age_years BETWEEN 13 AND 15 THEN '13-15'
      WHEN age_years BETWEEN 16 AND 18 THEN '16-18'
      WHEN age_years BETWEEN 19 AND 21 THEN '19-21'
      WHEN age_years BETWEEN 22 AND 25 THEN '22-25'
      WHEN age_years BETWEEN 26 AND 30 THEN '26-30'
      ELSE '31+'
    END AS category,
    COUNT(DISTINCT product_id) AS sku_count,
    AVG(price_inc_vat_gbp) AS avg_price
  FROM VW_PRODUCT_LATEST
  WHERE is_comparable_bottle = TRUE
    AND price_inc_vat_gbp IS NOT NULL
    AND is_age_stated = TRUE
    AND age_years IS NOT NULL
    AND age_years > 0
  GROUP BY 1
  HAVING COUNT(DISTINCT product_id) >= 5
)

SELECT
  'Overall Baseline' AS factor,
  'All comparable bottles (median baseline)' AS category,
  (SELECT total_skus FROM b) AS sku_count,
  ROUND((SELECT base_price FROM b), 2) AS avg_price,
  NULL AS vs_baseline_gbp,
  NULL AS vs_baseline_pct

UNION ALL

SELECT
  'Age Tier Premium' AS factor,
  category,
  sku_count,
  ROUND(avg_price, 2) AS avg_price,
  ROUND(avg_price - (SELECT base_price FROM b), 2) AS vs_baseline_gbp,
  ROUND(
    (avg_price - (SELECT base_price FROM b))
    / NULLIF((SELECT base_price FROM b), 0) * 100,
    1
  ) AS vs_baseline_pct
FROM age_tiers

UNION ALL

SELECT
  'Cask Strength' AS factor,
  CASE WHEN is_cask_strength THEN 'Cask Strength' ELSE 'Standard ABV' END AS category,
  COUNT(DISTINCT product_id) AS sku_count,
  ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price,
  ROUND(AVG(price_inc_vat_gbp) - (SELECT base_price FROM b), 2) AS vs_baseline_gbp,
  ROUND(
    (AVG(price_inc_vat_gbp) - (SELECT base_price FROM b))
    / NULLIF((SELECT base_price FROM b), 0) * 100,
    1
  ) AS vs_baseline_pct
FROM VW_PRODUCT_LATEST
WHERE is_comparable_bottle = TRUE
  AND price_inc_vat_gbp IS NOT NULL
  AND is_cask_strength IS NOT NULL
GROUP BY is_cask_strength

UNION ALL

SELECT
  'Region Premium' AS factor,
  region AS category,
  COUNT(DISTINCT product_id) AS sku_count,
  ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price,
  ROUND(AVG(price_inc_vat_gbp) - (SELECT base_price FROM b), 2) AS vs_baseline_gbp,
  ROUND(
    (AVG(price_inc_vat_gbp) - (SELECT base_price FROM b))
    / NULLIF((SELECT base_price FROM b), 0) * 100,
    1
  ) AS vs_baseline_pct
FROM VW_PRODUCT_LATEST
WHERE is_comparable_bottle = TRUE
  AND price_inc_vat_gbp IS NOT NULL
  AND region IS NOT NULL
GROUP BY region
HAVING COUNT(DISTINCT product_id) >= 10

UNION ALL

SELECT
  'Quality Tier' AS factor,
  CASE
    WHEN rating_stars >= 4.5 THEN 'Exceptional (4.5+)'
    WHEN rating_stars >= 4.0 THEN 'Excellent (4.0-4.5)'
    WHEN rating_stars >= 3.5 THEN 'Good (3.5-4.0)'
    ELSE 'Average (<3.5)'
  END AS category,
  COUNT(DISTINCT product_id) AS sku_count,
  ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price,
  ROUND(AVG(price_inc_vat_gbp) - (SELECT base_price FROM b), 2) AS vs_baseline_gbp,
  ROUND(
    (AVG(price_inc_vat_gbp) - (SELECT base_price FROM b))
    / NULLIF((SELECT base_price FROM b), 0) * 100,
    1
  ) AS vs_baseline_pct
FROM VW_PRODUCT_LATEST
WHERE is_comparable_bottle = TRUE
  AND price_inc_vat_gbp IS NOT NULL
  AND rating_stars IS NOT NULL
GROUP BY 1, 2;

--------------------------------------------------------------------------------
-- 4) Age Statement ROI: Diminishing Returns
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW VW_AGE_ROI AS
WITH age_metrics AS (
  SELECT
    age_band,
    ROUND(AVG(age_years), 1) AS avg_age_years,
    COUNT(DISTINCT product_id) AS sku_count,
    ROUND(AVG(price_inc_vat_gbp), 2) AS avg_price,
    ROUND(MEDIAN(price_inc_vat_gbp), 2) AS median_price,
    ROUND(AVG(price_inc_vat_gbp / NULLIF(age_years, 0)), 2) AS price_per_year_aged,
    ROUND(AVG(rating_stars), 2) AS avg_rating,
    ROUND(AVG(price_per_alcohol_unit_gbp), 2) AS avg_price_per_unit
  FROM VW_PRODUCT_LATEST
  WHERE is_age_stated = TRUE
    AND is_comparable_bottle = TRUE
    AND age_years IS NOT NULL
    AND price_inc_vat_gbp IS NOT NULL
  GROUP BY age_band
)
SELECT
  age_band,
  avg_age_years,
  sku_count,
  avg_price,
  median_price,
  price_per_year_aged,
  avg_rating,
  avg_price_per_unit,
  ROUND(avg_price - LAG(avg_price) OVER (ORDER BY avg_age_years), 2) AS marginal_price_increase_gbp,
  ROUND(
    (avg_price - LAG(avg_price) OVER (ORDER BY avg_age_years)) /
    NULLIF((avg_age_years - LAG(avg_age_years) OVER (ORDER BY avg_age_years)), 0),
    2
  ) AS marginal_cost_per_additional_year,
  CASE
    WHEN price_per_year_aged <= 5 THEN 'Excellent Value'
    WHEN price_per_year_aged <= 10 THEN 'Good Value'
    WHEN price_per_year_aged <= 15 THEN 'Fair Value'
    ELSE 'Premium/Diminishing Returns'
  END AS value_assessment
FROM age_metrics;
