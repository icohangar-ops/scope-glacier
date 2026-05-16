-- Athena View: Infrastructure Disruption Monitor
-- Pipeline and refinery disruption status with capacity impact

CREATE OR REPLACE VIEW scope_glacier.infrastructure_disruption_v AS
SELECT
    'Pipeline' AS asset_type,
    p.pipeline_id AS asset_id,
    p.name AS asset_name,
    p.commodity,
    p.origin,
    p.destination,
    p.capacity_bpd,
    p.current_flow_bpd,
    ROUND(p.current_flow_bpd / NULLIF(p.capacity_bpd, 0) * 100, 1) AS utilization_pct,
    p.status,
    CASE WHEN p.status IN ('Shutdown', 'Reduced Flow', 'Force Majeure') THEN TRUE ELSE FALSE END AS is_disrupted,
    CASE WHEN p.status = 'Shutdown' THEN p.capacity_bpd
         WHEN p.status = 'Reduced Flow' THEN p.capacity_bpd - p.current_flow_bpd
         WHEN p.status = 'Force Majeure' THEN p.capacity_bpd
         ELSE 0
    END AS estimated_offline_bpd,
    NULL AS region,
    NULL AS country,
    NULL AS crude_type,
    p.length_miles AS length_miles,
    NULL AS capacity_offline_bpd
FROM scope_glacier.pipelines p

UNION ALL

SELECT
    'Refinery' AS asset_type,
    r.refinery_id AS asset_id,
    r.name AS asset_name,
    'Crude Oil' AS commodity,
    NULL AS origin,
    NULL AS destination,
    r.capacity_bpd,
    r.throughput_bpd AS current_flow_bpd,
    r.utilization_pct,
    r.status,
    CASE WHEN r.status IN ('Shutdown', 'Maintenance') THEN TRUE ELSE FALSE END AS is_disrupted,
    CASE WHEN r.status = 'Shutdown' THEN r.capacity_bpd
         WHEN r.status = 'Maintenance' THEN r.capacity_bpd * 0.5
         ELSE 0
    END AS estimated_offline_bpd,
    r.region,
    r.country,
    r.crude_type,
    NULL AS length_miles,
    r.offline_bpd AS capacity_offline_bpd
FROM scope_glacier.refineries r

ORDER BY is_disrupted DESC, estimated_offline_bpd DESC;
