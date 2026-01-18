-- analytics_queries.sql

use warehouse WH_WHISKY;
use database WHISKY_DWH;
use schema CURATED;

-- 1) Most expensive brands (avg inc VAT)
select brand, round(avg(price_inc_vat_gbp), 2) as avg_price
from VW_PRODUCT_SNAPSHOTS
group by brand
order by avg_price desc
limit 20;

-- 2) Best value by price per alcohol unit
select name, brand, region, price_inc_vat_gbp, alcohol_units, price_per_alcohol_unit_gbp
from VW_PRODUCT_SNAPSHOTS
where price_per_alcohol_unit_gbp is not null
order by price_per_alcohol_unit_gbp asc
limit 20;

-- 3) Discount impact
select
  discount_band,
  count(*) as row_count,
  round(avg(discount_percent), 2) as avg_discount_pct,
  round(avg(discount_amount_gbp), 2) as avg_discount_amt
from VW_PRODUCT_SNAPSHOTS
where is_discounted = true
group by discount_band
order by avg_discount_pct desc;


-- 4) Flavor profile vs price (smoke)
select
  style_smoke,
  count(*) as bottle_count,
  round(avg(price_inc_vat_gbp), 2) as avg_price_gbp
from VW_PRODUCT_SNAPSHOTS
where style_smoke is not null
  and price_inc_vat_gbp is not null
group by style_smoke
order by style_smoke;

