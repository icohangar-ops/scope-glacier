-- Athena View: Energy Price Dashboard
-- Multi-commodity price comparison with volatility and moving averages

CREATE OR REPLACE VIEW scope_glacier.energy_price_dashboard_v AS
WITH price_stats AS (
    SELECT
        commodity_code,
        MIN(price_date) AS earliest_date,
        MAX(price_date) AS latest_date,
        (SELECT price_value FROM scope_glacier.price_series p2
         WHERE p2.commodity_code = p1.commodity_code ORDER BY p2.price_date DESC LIMIT 1) AS latest_price,
        ROUND(AVG(price_value), 2) AS avg_price_30d,
        ROUND(STDDEV(price_value), 2) AS std_dev_30d,
        CASE WHEN STDDEV(price_value) > 0
            THEN ROUND(STDDEV(price_value) / NULLIF(AVG(price_value), 0) * 100, 2)
            ELSE 0
        END AS coefficient_of_variation_pct
    FROM scope_glacier.price_series p1
    WHERE price_date >= DATE_ADD('DAY', -30, CURRENT_DATE)
    GROUP BY commodity_code
),
returns AS (
    SELECT
        commodity_code,
        price_date,
        price_value,
        LAG(price_value) OVER (PARTITION BY commodity_code ORDER BY price_date) AS prev_price,
        LAG(price_value, 20) OVER (PARTITION BY commodity_code ORDER BY price_date) AS price_20d_ago
    FROM scope_glacier.price_series
    WHERE price_date >= DATE_ADD('DAY', -30, CURRENT_DATE)
)
SELECT
    ps.commodity_code,
    COALESCE(ec.name, ps.commodity_code) AS commodity_name,
    COALESCE(ec.energy_type, 'Unknown') AS energy_type,
    ps.latest_price,
    COALESCE(ec.unit, 'USD/barrel') AS unit,
    ps.avg_price_30d,
    ps.std_dev_30d,
    ps.coefficient_of_variation_pct,
    CASE WHEN r.prev_price > 0
        THEN ROUND((r.latest_price - r.prev_price) / r.prev_price * 100, 2)
        ELSE NULL
    END AS daily_return_pct,
    CASE WHEN r.price_20d_ago > 0
        THEN ROUND((r.latest_price - r.price_20d_ago) / r.price_20d_ago * 100, 2)
        ELSE NULL
    END AS return_20d_pct,
    ps.latest_date
FROM price_stats ps
LEFT JOIN (
    SELECT commodity_code, latest_price FROM returns
    WHERE price_date = (SELECT MAX(price_date) FROM returns)
) r ON r.commodity_code = ps.commodity_code
LEFT JOIN scope_glacier.energy_commodities ec ON ec.code = ps.commodity_code
ORDER BY ps.latest_price DESC;
