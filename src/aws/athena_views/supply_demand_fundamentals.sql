-- Athena View: Supply/Demand Fundamentals
-- Production, consumption, inventory, and implied balance analysis

CREATE OR REPLACE VIEW scope_glacier.supply_demand_fundamentals_v AS
SELECT
    sdb.commodity_code,
    COALESCE(ec.name, sdb.commodity_code) AS commodity_name,
    sdb.period,
    sdb.date,
    sdb.production_mbd,
    sdb.consumption_mbd,
    sdb.imports_mbd,
    sdb.exports_mbd,
    (sdb.production_mbd - sdb.consumption_mbd + sdb.imports_mbd - sdb.exports_mbd) AS implied_balance_mbd,
    sdb.inventory_mmbl,
    sdb.inventory_change_mmbl,
    CASE WHEN sdb.consumption_mbd > 0
        THEN ROUND(sdb.inventory_mmbl / sdb.consumption_mbd, 1)
        ELSE 0
    END AS inventory_coverage_days,
    CASE
        WHEN (CASE WHEN sdb.consumption_mbd > 0 THEN sdb.inventory_mmbl / sdb.consumption_mbd ELSE 999 END) < 20
            THEN 'Critical'
        WHEN (CASE WHEN sdb.consumption_mbd > 0 THEN sdb.inventory_mmbl / sdb.consumption_mbd ELSE 999 END) < 30
            THEN 'Low'
        WHEN (CASE WHEN sdb.consumption_mbd > 0 THEN sdb.inventory_mmbl / sdb.consumption_mbd ELSE 999 END) < 50
            THEN 'Adequate'
        ELSE 'Comfortable'
    END AS drawdown_risk,
    sdb.spare_capacity_mbd,
    sdb.utilization_pct,
    -- Trend: compare current implied balance to 4-week average
    ROUND(
        (sdb.production_mbd - sdb.consumption_mbd + sdb.imports_mbd - sdb.exports_mbd)
        - COALESCE(
            (SELECT AVG(production_mbd - consumption_mbd + imports_mbd - exports_mbd)
             FROM scope_glacier.supply_demand_balance
             WHERE commodity_code = sdb.commodity_code
               AND date BETWEEN DATE_ADD('DAY', -28, sdb.date) AND DATE_ADD('DAY', -1, sdb.date)
            ), 0
        ), 2
    ) AS balance_vs_4w_avg_mbd
FROM scope_glacier.supply_demand_balance sdb
LEFT JOIN scope_glacier.energy_commodities ec ON ec.code = sdb.commodity_code
ORDER BY sdb.commodity_code, sdb.date DESC;
