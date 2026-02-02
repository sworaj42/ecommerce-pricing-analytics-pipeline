-- 01_create_warehouse_db_schema.sql

create warehouse if not exists WH_WHISKY
  warehouse_size = 'XSMALL'
  auto_suspend = 60
  auto_resume = true;

create database if not exists WHISKY_DWH;

create schema if not exists WHISKY_DWH.RAW;
create schema if not exists WHISKY_DWH.STAGE;
create schema if not exists WHISKY_DWH.CURATED;

use warehouse WH_WHISKY;
use database WHISKY_DWH;
