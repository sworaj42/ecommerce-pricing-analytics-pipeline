-- 03_copy_into_raw.sql

use warehouse WH_WHISKY;
use database WHISKY_DWH;

copy into RAW.WHISKY_PRODUCTS_RAW
from @STAGE.WHISKY_STAGE
files = ('whisky_cleaned_2026-01-16.csv')
file_format = (format_name = STAGE.CSV_FMT_WHISKY)
match_by_column_name = case_insensitive
on_error = 'abort_statement';

-- quick checks
select count(*) as rows_loaded from RAW.WHISKY_PRODUCTS_RAW;
select * from RAW.WHISKY_PRODUCTS_RAW limit 10;
