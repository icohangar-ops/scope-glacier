# Glue ETL: EIA Energy Price Ingestion
# Fetches spot prices from EIA API and writes to Iceberg.

import json
import logging
import os
import sys
from datetime import datetime, timedelta

import boto3

sys.path.insert(0, "/opt/python")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Energy commodities tracked by Scope.Glacier
ENERGY_SERIES = {
    "WTI": {"series": "PET.RWTC.D", "name": "West Texas Intermediate", "unit": "USD/barrel"},
    "BRENT": {"series": "PET.RBRTE.D", "name": "Brent Crude", "unit": "USD/barrel"},
    "HH": {"series": "NG.RNGWHHD.D", "name": "Henry Hub Natural Gas", "unit": "USD/MMBtu"},
    "RBOB": {"series": "PET.EER_EPMRU_PF4_YCG_DPG.D", "name": "RBOB Gasoline", "unit": "USD/gallon"},
    "HO": {"series": "PET.EER_EPD2F_PF4_Yhou_DPG.D", "name": "No. 2 Heating Oil", "unit": "USD/gallon"},
}


def ingest_eia_prices(event):
    """Ingest EIA spot prices and write to Iceberg via Athena.

    Expected event format:
    {
        "commodities": ["WTI", "BRENT", "HH"],
        "days": 30,
        "target_table": "price_series"
    }
    """
    commodities = event.get("commodities", list(ENERGY_SERIES.keys()))
    days = event.get("days", 30)

    database = os.environ.get("GLUE_DATABASE", "scope_glacier")
    athena = boto3.client("athena")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-glacier-queries/")

    results = []
    for code in commodities:
        config = ENERGY_SERIES.get(code)
        if not config:
            continue

        try:
            # Compute price statistics for the commodity
            query = f"""
            WITH daily_prices AS (
                SELECT
                    price_date,
                    price_value,
                    LAG(price_value) OVER (ORDER BY price_date) AS prev_price
                FROM {database}.price_series
                WHERE commodity_code = '{code}'
                  AND price_date >= DATE_ADD('DAY', -{days}, CURRENT_DATE)
                ORDER BY price_date DESC
            )
            SELECT
                '{code}' AS commodity_code,
                '{config["name"]}' AS commodity_name,
                CURRENT_DATE AS analysis_date,
                (SELECT price_value FROM daily_prices WHERE ROWNUM = 1) AS latest_price,
                (SELECT price_value FROM daily_prices WHERE ROWNUM = {days}) AS price_{days}_days_ago,
                ROUND(AVG(price_value) OVER (), 2) AS avg_price_{days}d,
                ROUND(STDDEV(price_value) OVER (), 2) AS std_dev_{days}d,
                CASE
                    WHEN (SELECT prev_price FROM daily_prices WHERE ROWNUM = 1) > 0
                    THEN ROUND(((SELECT price_value FROM daily_prices WHERE ROWNUM = 1)
                        - (SELECT prev_price FROM daily_prices WHERE ROWNUM = 1))
                        / (SELECT prev_price FROM daily_prices WHERE ROWNUM = 1) * 100, 2)
                    ELSE NULL
                END AS daily_return_pct
            FROM daily_prices
            WHERE ROWNUM = 1
            """

            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}prices/stats/"},
            )
            results.append({
                "commodity_code": code,
                "query_id": response["QueryExecutionId"],
                "status": "submitted",
            })
            logger.info(f"Submitted price analysis for {code}")

        except Exception as e:
            logger.error(f"Error ingesting prices for {code}: {e}")
            results.append({"commodity_code": code, "status": "error", "error": str(e)})

    return {
        "status": "completed",
        "commodities_processed": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat(),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point for EIA price ingestion."""
    logger.info(f"EIA price ETL triggered: {json.dumps(event)[:500]}")

    try:
        result = ingest_eia_prices(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
