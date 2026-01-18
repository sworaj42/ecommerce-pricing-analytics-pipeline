-- 02_stage.sql

use warehouse WH_WHISKY;
use database WHISKY_DWH;
use schema STAGE;

create or replace stage WHISKY_STAGE
  file_format = CSV_FMT_WHISKY;

