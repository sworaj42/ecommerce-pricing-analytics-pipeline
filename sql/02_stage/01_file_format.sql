-- 01_file_format.sql

use warehouse WH_WHISKY;
use database WHISKY_DWH;
use schema STAGE;

create or replace file format CSV_FMT_WHISKY
  type = csv
  parse_header = true
  field_delimiter = ','
  field_optionally_enclosed_by = '"'
  null_if = ('', 'NULL', 'null')
  empty_field_as_null = true;