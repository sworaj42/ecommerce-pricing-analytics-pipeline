-- 01_dim_tables.sql
-- Dimension tables for whisky product data warehouse

use warehouse WH_WHISKY;
use database WHISKY_DWH;
use schema CURATED;

-- Date dimension: one row per scrape date for time-based analysis
create or replace table DIM_DATE (
  DATE_KEY number(8,0) not null,         -- YYYYMMDD format
  FULL_DATE date not null,
  YEAR number(4,0),
  MONTH number(2,0),
  DAY number(2,0),
  WEEK number(2,0),
  DAY_NAME varchar,
  constraint PK_DIM_DATE primary key (DATE_KEY)
);

-- Price tier dimension: categorizes products by price range
create or replace table DIM_PRICE_TIER (
  PRICE_TIER_KEY number(38,0) autoincrement start 1 increment 1,
  PRICE_TIER varchar not null,
  constraint PK_DIM_PRICE_TIER primary key (PRICE_TIER_KEY),
  constraint UK_DIM_PRICE_TIER unique (PRICE_TIER)
);

-- Discount band dimension: categorizes discount levels
create or replace table DIM_DISCOUNT_BAND (
  DISCOUNT_BAND_KEY number(38,0) autoincrement start 1 increment 1,
  DISCOUNT_BAND varchar not null,
  constraint PK_DIM_DISCOUNT_BAND primary key (DISCOUNT_BAND_KEY),
  constraint UK_DIM_DISCOUNT_BAND unique (DISCOUNT_BAND)
);

-- Product dimension: stores stable product attributes (SCD Type 1 - latest values only)
create or replace table DIM_PRODUCT (
  PRODUCT_KEY number(38,0) autoincrement start 1 increment 1,  -- Surrogate key
  PRODUCT_ID number(38,0) not null,                            -- Natural key from source

  -- Basic product info
  NAME varchar not null,
  BRAND varchar,
  CATEGORY varchar,
  REGION varchar,
  PRODUCT_URL varchar,
  IMAGE_URL varchar,

  -- Flavor profile (stable attributes)
  STYLE_BODY number(2,0),
  STYLE_RICHNESS number(2,0),
  STYLE_SMOKE number(2,0),
  STYLE_SWEETNESS number(2,0),
  CHARACTER_NOTES varchar,

  -- Production details
  FACT_BOTTLER varchar,
  FACT_COUNTRY varchar,
  FACT_CASK_TYPE varchar,
  FACT_COLOURING varchar,

  -- Bottle specifications
  BOTTLE_SIZE_L number(10,3),
  BOTTLE_SIZE_CL number(10,1),
  BOTTLE_SIZE_BAND varchar,

  -- Alcohol content
  ABV_PERCENT number(5,2),
  ABV_BAND varchar,
  IS_CASK_STRENGTH boolean,

  -- Age information
  AGE_YEARS number(5,0),
  IS_AGE_STATED boolean,
  AGE_BAND varchar,

  -- Metadata
  IS_BRAND_PLACEHOLDER boolean,

  constraint PK_DIM_PRODUCT primary key (PRODUCT_KEY),
  constraint UK_DIM_PRODUCT_PRODUCT_ID unique (PRODUCT_ID)
);