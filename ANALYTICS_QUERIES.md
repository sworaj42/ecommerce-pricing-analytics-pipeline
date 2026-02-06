
# Analytics Queries Documentation

This document describes the analytical SQL queries used in the project, outlining  
the business questions addressed, data sources, and key insights derived from each analysis.

Each query is implemented in `analytics_queries.sql` and supported by visual outputs  
stored in the `outputs/screenshots/` directory.

---

### Q1. Brand-Level Price & Quality Positioning

**Business Question**  
How do brands differ in terms of pricing, product spread, customer ratings, and current promotional activity?

**Query Reference**  
`analytics_queries.sql` → Query 1 (Brand-Level Price and Quality Positioning)

**Source View**  
`VW_PRODUCT_LATEST`

**Analytical Interpretation**  
- Macallan and Balvenie emerge as the strongest premium brands, combining the highest median prices with consistently high weighted consumer ratings (≈4.4–4.6), indicating strong brand equity and customer trust at higher price points.
- Glenfiddich and Johnnie Walker show the widest price spreads, suggesting broad portfolios that span both entry-level and premium offerings rather than a single pricing tier.
- Brands such as Aberlour, Glenfarclas, and Bunnahabhain achieve high consumer ratings while maintaining mid-range pricing, indicating strong value-for-money positioning.
- Discount activity is uneven across brands: some premium brands maintain a near zero on-sale rate, reinforcing exclusivity, while others (e.g., Johnnie Walker, Balvenie) use selective promotions to drive volume.
- Overall, higher pricing does not correlate negatively with customer ratings, suggesting that perceived quality and brand reputation outweigh price sensitivity in this category.

**Suggested Screenshot**  

![Q1 – Brand Price & Quality Positioning](outputs/screenshots/q1_brand_price_quality_positioning.png)

---
