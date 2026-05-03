# Glue ETL: Infrastructure Tracking (Pipelines + Refineries)
# Computes utilization, disruption status, and capacity offline estimates.

import json
import logging
import os
import sys
from datetime import datetime

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def compute_infrastructure_metrics(event):
    """Compute pipeline and refinery utilization metrics.

    Expected event format:
    {
        "commodity": "Crude Oil",
        "include_pipelines": true,
        "include_refineries": true,
        "target_table": "infrastructure_summary"
    }
    """
    commodity = event.get("commodity", "Crude Oil")
    include_pipelines = event.get("include_pipelines", True)
    include_refineries = event.get("include_refineries", True)

    database = os.environ.get("GLUE_DATABASE", "scope_glacier")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-glacier-queries/")

    results = []

    if include_pipelines:
        try:
            pipeline_query = f"""
            SELECT
                pipeline_id,
                name,
                commodity,
                origin,
                destination,
                capacity_bpd,
                current_flow_bpd,
                ROUND(current_flow_bpd / NULLIF(capacity_bpd, 0) * 100, 1) AS utilization_pct,
                status,
                CASE
                    WHEN status IN ('Shutdown', 'Reduced Flow', 'Force Majeure') THEN TRUE
                    ELSE FALSE
                END AS is_disrupted,
                length_miles,
                CURRENT_TIMESTAMP AS computed_at
            FROM {database}.pipelines
            WHERE commodity = '{commodity}' OR '{commodity}' = 'All'
            ORDER BY is_disrupted DESC, utilization_pct DESC
            """

            response = athena.start_query_execution(
                QueryString=pipeline_query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}infrastructure/pipelines/"},
            )
            results.append({
                "type": "pipelines",
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Submitted pipeline metrics query")

        except Exception as e:
            logger.error(f"Error computing pipeline metrics: {e}")
            results.append({"type": "pipelines", "status": "error", "error": str(e)})

    if include_refineries:
        try:
            refinery_query = f"""
            SELECT
                refinery_id,
                name,
                region,
                country,
                capacity_bpd,
                utilization_pct,
                ROUND(capacity_bpd * utilization_pct / 100.0, 0) AS throughput_bpd,
                capacity_bpd - ROUND(capacity_bpd * utilization_pct / 100.0, 0) AS offline_bpd,
                status,
                crude_type,
                CASE
                    WHEN status = 'Shutdown' THEN capacity_bpd
                    WHEN status = 'Maintenance' THEN capacity_bpd * 0.5
                    ELSE 0
                END AS estimated_offline_bpd,
                CURRENT_TIMESTAMP AS computed_at
            FROM {database}.refineries
            ORDER BY estimated_offline_bpd DESC
            """

            response = athena.start_query_execution(
                QueryString=refinery_query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}infrastructure/refineries/"},
            )
            results.append({
                "type": "refineries",
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Submitted refinery metrics query")

        except Exception as e:
            logger.error(f"Error computing refinery metrics: {e}")
            results.append({"type": "refineries", "status": "error", "error": str(e)})

    # Compute aggregate infrastructure summary
    try:
        summary_query = f"""
        INSERT INTO {database}.infrastructure_summary
        SELECT
            '{commodity}' AS commodity,
            CURRENT_TIMESTAMP AS computed_at,
            (SELECT COUNT(*) FROM {database}.pipelines
                WHERE (commodity = '{commodity}' OR '{commodity}' = 'All')
                AND status IN ('Shutdown', 'Reduced Flow', 'Force Majeure')) AS disrupted_pipelines,
            (SELECT COUNT(*) FROM {database}.pipelines
                WHERE (commodity = '{commodity}' OR '{commodity}' = 'All')
                AND status = 'Operational') AS operational_pipelines,
            (SELECT SUM(offline_bpd) FROM {database}.refineries
                WHERE status IN ('Shutdown', 'Maintenance')) AS total_refinery_offline_bpd,
            (SELECT COUNT(*) FROM {database}.refineries
                WHERE status = 'Operating') AS operating_refineries
        """
        athena.start_query_execution(
            QueryString=summary_query,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": f"{s3_output}infrastructure/summary/"},
        )
    except Exception as e:
        logger.error(f"Error computing infrastructure summary: {e}")

    return {
        "status": "completed",
        "commodity": commodity,
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for infrastructure ETL."""
    logger.info(f"Infrastructure ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = compute_infrastructure_metrics(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
