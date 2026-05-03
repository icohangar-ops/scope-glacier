# Glue ETL: Supply/Demand Balance Computation
# Computes implied balance, inventory coverage, and spare capacity metrics.

import json
import logging
import os
import sys
from datetime import datetime

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def compute_supply_demand_metrics(event):
    """Compute supply/demand balance metrics and risk indicators.

    Expected event format:
    {
        "commodity_codes": ["WTI", "BRENT"],
        "periods": ["2024-W01", "2024-W02"],
        "target_table": "supply_demand_balance"
    }
    """
    commodity_codes = event.get("commodity_codes", ["WTI", "BRENT"])

    database = os.environ.get("GLUE_DATABASE", "scope_glacier")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-glacier-queries/")

    results = []
    for code in commodity_codes:
        try:
            # Compute implied balance and inventory coverage
            balance_query = f"""
            SELECT
                commodity_code,
                period,
                date,
                production_mbd,
                consumption_mbd,
                imports_mbd,
                exports_mbd,
                inventory_mmbl,
                inventory_change_mmbl,
                spare_capacity_mbd,
                utilization_pct,
                -- Implied balance: production - consumption + imports - exports
                (production_mbd - consumption_mbd + imports_mbd - exports_mbd) AS implied_balance_mbd,
                -- Inventory coverage in days
                CASE WHEN consumption_mbd > 0
                    THEN inventory_mmbl / consumption_mbd
                    ELSE 0
                END AS inventory_coverage_days,
                -- Drawdown risk rating
                CASE
                    WHEN (CASE WHEN consumption_mbd > 0 THEN inventory_mmbl / consumption_mbd ELSE 0 END) < 20
                        THEN 'Critical'
                    WHEN (CASE WHEN consumption_mbd > 0 THEN inventory_mmbl / consumption_mbd ELSE 0 END) < 30
                        THEN 'Low'
                    WHEN (CASE WHEN consumption_mbd > 0 THEN inventory_mmbl / consumption_mbd ELSE 0 END) < 50
                        THEN 'Adequate'
                    ELSE 'Comfortable'
                END AS drawdown_risk,
                CURRENT_TIMESTAMP AS computed_at
            FROM {database}.supply_demand_balance
            WHERE commodity_code = '{code}'
            ORDER BY date DESC
            LIMIT 52
            """

            response = athena.start_query_execution(
                QueryString=balance_query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}supply_demand/"},
            )
            results.append({
                "commodity_code": code,
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Submitted supply/demand query for {code}")

        except Exception as e:
            logger.error(f"Error computing supply/demand for {code}: {e}")
            results.append({"commodity_code": code, "status": "error", "error": str(e)})

    return {
        "status": "completed",
        "commodities_processed": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for supply/demand ETL."""
    logger.info(f"Supply/demand ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = compute_supply_demand_metrics(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
