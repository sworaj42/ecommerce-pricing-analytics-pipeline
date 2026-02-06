
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

### Q2. Region-Level Pricing, Quality & Promotion (Single Malt)

**Business Question**  
Which whisky regions are priced higher, which regions deliver the strongest customer ratings, and where are promotions most common (within comparable Single Malt bottles)?

**Query Reference**  
`analytics_queries.sql` → Query 2 (Region-Level Pricing, Quality, and Promotion)

**Source View**  
`VW_PRODUCT_LATEST`

**Analytical Interpretation**  
- **Speyside** dominates the category with the largest SKU count and the highest average pricing, indicating both scale and strong premium positioning.
- **Islay** achieves the strongest weighted consumer ratings, suggesting particularly high perceived quality and brand loyalty despite premium pricing.
- **Highland** balances scale and value, offering a large number of SKUs at slightly lower prices while maintaining strong customer satisfaction.
- **Lowland**, with the smallest SKU base, shows the highest discount intensity, likely reflecting weaker pricing power or inventory-clearing strategies.
- Overall, regional identity plays a clear role in both pricing and consumer perception, with premium regions sustaining higher prices without sacrificing ratings.

**Suggested Screenshot**

![Q2 – Region Pricing and Price Spread](outputs/screenshots/q2_region_pricing_quality_promo_part1.png)

![Q2 – Region Ratings, Reviews and Discount Activity](outputs/screenshots/q2_region_pricing_quality_promo_part2.png)

---
