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

-- Product dimension: stores stable product attributes 
CREATE OR REPLACE TABLE DIM_PRODUCT (
  PRODUCT_KEY NUMBER(38,0) AUTOINCREMENT START 1 INCREMENT 1,  -- Surrogate key
  PRODUCT_ID NUMBER(38,0) NOT NULL,                            -- Natural key from source

  -- Basic product info
  NAME VARCHAR NOT NULL,
  BRAND VARCHAR,
  CATEGORY VARCHAR,
  REGION VARCHAR,
  PRODUCT_URL VARCHAR,
  IMAGE_URL VARCHAR,

  -- Flavor profile (stable attributes)
  STYLE_BODY NUMBER(2,0),
  STYLE_RICHNESS NUMBER(2,0),
  STYLE_SMOKE NUMBER(2,0),
  STYLE_SWEETNESS NUMBER(2,0),
  CHARACTER_NOTES VARCHAR,

  -- Production details
  FACT_BOTTLER VARCHAR,
  FACT_COUNTRY VARCHAR,
  FACT_CASK_TYPE VARCHAR,
  FACT_COLOURING VARCHAR,

  -- Bottle specifications
  BOTTLE_SIZE_L NUMBER(10,3),
  BOTTLE_SIZE_CL NUMBER(10,1),
  BOTTLE_SIZE_BAND VARCHAR,
  IS_STANDARD_BOTTLE BOOLEAN,        
  IS_COMPARABLE_BOTTLE BOOLEAN,      

  -- Alcohol content
  ABV_PERCENT NUMBER(5,2),
  ABV_BAND VARCHAR,
  IS_CASK_STRENGTH BOOLEAN,

  -- Age information
  AGE_YEARS NUMBER(5,0),
  IS_AGE_STATED BOOLEAN,
  AGE_BAND VARCHAR,

  -- Metadata
  IS_BRAND_PLACEHOLDER BOOLEAN,

  -- Outlier flags (added during cleaning; advisory only)
  IS_PRICE_OUTLIER BOOLEAN,
  IS_VALUE_OUTLIER BOOLEAN,
  IS_OUTLIER BOOLEAN,

  CONSTRAINT PK_DIM_PRODUCT PRIMARY KEY (PRODUCT_KEY),
  CONSTRAINT UK_DIM_PRODUCT_PRODUCT_ID UNIQUE (PRODUCT_ID)
);