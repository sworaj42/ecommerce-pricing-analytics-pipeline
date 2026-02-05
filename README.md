# Whisky Pricing Analytics Pipeline & Dashboard Project

This project implements an end to end data analytics pipeline to analyze whisky product pricing, discounts, ratings, and value for money metrics. The processed data is used to generate interactive dashboards in Power BI, providing insights into market pricing behavior and consumer preferences.

The analysis focuses on:
- Whisky price distribution
- Regional price differences
- Relationship between price, ratings, and popularity
- Product segmentation by price tier
- Discount and value-for-money analysis

---
## Tech Stack

- Data Collection: Python (web scraping)
- Data Processing: Python
- Data Warehouse: Snowflake
- Data Modeling: Star schema (DIM_* + snapshot fact table)
- Analytics Layer: Snowflake Views
- Visualization: Power BI
- Version Control: Git & GitHub

---

## Repository Structure

- `src/` – Python scripts for web scraping and data transformation  
- `sql/` – Snowflake DDL, fact/dimension tables, and curated views  
- `outputs/figures/` – Architecture and data model diagrams  
- `powerbi/` – Power BI dashboard file  
- `ANALYTICS_QUERIES.md` – Documented analytical queries and business logic  

---

## Architecture Overview

**Pipeline Flow**

![Whisky Data Pipeline Architecture](outputs/figures/whisky_data_pipeline_architecture.png)

**Diagram Explanation**

The pipeline begins by scraping whisky product data from The Whisky Exchange website using Python. The scraped data is first saved as a raw CSV, then cleaned and enriched in Python to derive pricing, alcohol, discount, and categorization metrics. The cleaned CSV is loaded into Snowflake using a Stage and `COPY INTO`, landing in the RAW schema. From there, the data is transformed into a curated star schema where **DIM_\*** tables store descriptive product, date, price tier, and discount attributes, while **FACT_PRODUCT_SNAPSHOT** captures time-varying pricing, discount, and rating metrics per product per scrape date. Finally, analytical views are created in Snowflake and consumed by Power BI to power interactive dashboards.

---

## Data Model Overview

The curated data warehouse follows a star schema design. Dimension tables store descriptive attributes such as product details, regions, and categorization, while a snapshot-based fact table records time-varying pricing, discount, and rating metrics to support analytical queries and time-based analysis.

![Star Schema Data Model](outputs/figures/data_model_star_schema.png)

---