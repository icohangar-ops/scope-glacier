"""
EIA Data Ingestion Lambda Handler — Fetches EIA energy data and writes to S3.

Triggered by EventBridge schedule or Step Functions.
Uses EIA Open Data API for spot prices and petroleum supply/demand data.
"""

import json
import logging
import os
from datetime import datetime, timedelta

import boto3
import requests

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"

ENERGY_SERIES = {
    "WTI": {"series": "PET.RWTC.D", "name": "West Texas Intermediate"},
    "BRENT": {"series": "PET.RBRTE.D", "name": "Brent Crude"},
    "HH": {"series": "NG.RNGWHHD.D", "name": "Henry Hub Natural Gas"},
    "RBOB": {"series": "PET.EER_EPMRU_PF4_YCG_DPG.D", "name": "RBOB Gasoline"},
    "HO": {"series": "PET.EER_EPD2F_PF4_Yhou_DPG.D", "name": "No. 2 Heating Oil"},
}


def fetch_eia_data(event):
    """Fetch EIA spot prices and write to S3.

    Expected event:
    {
        "commodities": ["WTI", "BRENT", "HH"],
        "days": 30
    }
    """
    commodities = event.get("commodities", list(ENERGY_SERIES.keys()))
    days = event.get("days", 30)

    api_key = os.environ.get("EIA_API_KEY", "")
    s3 = boto3.client("s3")
    bucket = os.environ.get("RAW_BUCKET", "scope-glacier-raw")

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    records = []
    for code, config in ENERGY_SERIES.items():
        if code not in commodities:
            continue

        try:
            r = requests.get(
                f"{EIA_BASE}/series/{config['series']}",
                params={"api_key": api_key, "start": start, "end": end, "frequency": "daily"},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()

            for element in data.get("response", {}).get("data", []):
                records.append({
                    "commodity_code": code,
                    "commodity_name": config["name"],
                    "price_date": element.get("period", ""),
                    "price_value": float(element.get("value", 0)),
                    "source": "EIA",
                    "ingested_at": datetime.utcnow().isoformat(),
                })
            logger.info(f"Fetched {len(data.get('response', {}).get('data', []))} prices for {code}")

        except Exception as e:
            logger.error(f"EIA fetch failed for {code}: {e}")

    # Write to S3 as JSON Lines
    if records:
        key = f"eia/prices/{datetime.now().strftime('%Y/%m/%d')}/spot_prices.jsonl"
        body = "\n".join(json.dumps(r) for r in records)
        s3.put_object(Bucket=bucket, Key=key, Body=body)
        logger.info(f"Wrote {len(records)} records to s3://{bucket}/{key}")

    return {
        "status": "completed",
        "commodities": commodities,
        "records_fetched": len(records),
        "s3_path": f"s3://{bucket}/{key}" if records else "",
        "timestamp": datetime.utcnow().isoformat(),
    }


def handler(event, context):
    """AWS Lambda entry point for EIA data ingestion."""
    logger.info(f"EIA ingestion triggered: {json.dumps(event)[:500]}")

    try:
        result = fetch_eia_data(event)
        return {"statusCode": 200, "body": json.dumps(result)}
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
