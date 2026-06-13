"""
EIA Data Ingestion Lambda Handler — Fetches EIA energy data and writes to S3.

Triggered by EventBridge schedule or Step Functions.
Uses EIA Open Data API for spot prices and petroleum supply/demand data.

The generic "fetch external records -> write JSON Lines to S3 -> envelope" flow
lives in scope_core.BaseIngestionHandler / write_jsonl_to_s3; this module keeps
only the EIA-specific fetch logic and S3 partitioning.
"""

import json
import logging
import os
from datetime import datetime, timedelta

import boto3
import requests

from cubiczan_resilience import resilient
from scope_core import (
    BaseIngestionHandler,
    error_response,
    success_response,
    write_jsonl_to_s3,
)

logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"

# Cache the resolved API key across warm invocations of the same container.
_EIA_API_KEY_CACHE = None


def _get_eia_api_key():
    """Resolve the EIA API key, preferring SSM SecureString over env vars.

    The key is fetched from SSM Parameter Store at cold start (path supplied via
    EIA_API_KEY_PARAM) so it never lives in a plaintext Lambda env var. Falls back
    to the EIA_API_KEY env var only if no parameter path is configured.
    """
    global _EIA_API_KEY_CACHE
    if _EIA_API_KEY_CACHE is not None:
        return _EIA_API_KEY_CACHE

    param_name = os.environ.get("EIA_API_KEY_PARAM", "")
    if param_name:
        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
        _EIA_API_KEY_CACHE = resp["Parameter"]["Value"]
    else:
        _EIA_API_KEY_CACHE = os.environ.get("EIA_API_KEY", "")
    return _EIA_API_KEY_CACHE

ENERGY_SERIES = {
    "WTI": {"series": "PET.RWTC.D", "name": "West Texas Intermediate"},
    "BRENT": {"series": "PET.RBRTE.D", "name": "Brent Crude"},
    "HH": {"series": "NG.RNGWHHD.D", "name": "Henry Hub Natural Gas"},
    "RBOB": {"series": "PET.EER_EPMRU_PF4_YCG_DPG.D", "name": "RBOB Gasoline"},
    "HO": {"series": "PET.EER_EPD2F_PF4_Yhou_DPG.D", "name": "No. 2 Heating Oil"},
}


@resilient(timeout=30, max_attempts=3)
def _fetch_series(series, params, api_key):
    """Fetch a single EIA series with timeout, retry/backoff and circuit breaker.

    Transient EIA/network failures are retried with exponential backoff + jitter
    before surfacing to the per-commodity error handler in EIAIngestionHandler.
    """
    r = requests.get(
        f"{EIA_BASE}/series/{series}",
        params=params,
        # Pass the API key via the X-Api-Key header (supported by the EIA v2
        # API) rather than a URL query parameter. Query params leak into
        # CloudWatch logs, EIA access logs, and any HTTP proxy logs.
        headers={"X-Api-Key": api_key},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


class EIAIngestionHandler(BaseIngestionHandler):
    """EIA-specific ingestion: fetch spot prices, write JSON Lines to S3.

    The S3 write and JSON-Lines serialization are inherited from
    scope_core.BaseIngestionHandler; only fetch_records and the partitioned
    S3 key are domain-specific.
    """

    def fetch_records(self, event):
        commodities = event.get("commodities", list(ENERGY_SERIES.keys()))
        days = event.get("days", 30)

        api_key = _get_eia_api_key()
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        records = []
        for code, config in ENERGY_SERIES.items():
            if code not in commodities:
                continue
            try:
                data = _fetch_series(
                    config["series"],
                    {"start": start, "end": end, "frequency": "daily"},
                    api_key,
                )
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
        return records

    def build_s3_key(self, event):
        return f"eia/prices/{datetime.now().strftime('%Y/%m/%d')}/spot_prices.jsonl"


def fetch_eia_data(event):
    """Fetch EIA spot prices and write to S3.

    Expected event:
    {
        "commodities": ["WTI", "BRENT", "HH"],
        "days": 30
    }
    """
    commodities = event.get("commodities", list(ENERGY_SERIES.keys()))
    s3 = boto3.client("s3")
    bucket = os.environ.get("RAW_BUCKET", "scope-glacier-raw")

    handler_obj = EIAIngestionHandler(s3, bucket=bucket)
    records = handler_obj.fetch_records(event)

    s3_path = ""
    if records:
        key = handler_obj.build_s3_key(event)
        s3_path = write_jsonl_to_s3(s3, bucket=bucket, key=key, records=records)
        logger.info(f"Wrote {len(records)} records to {s3_path}")

    return {
        "status": "completed",
        "commodities": commodities,
        "records_fetched": len(records),
        "s3_path": s3_path,
        "timestamp": datetime.utcnow().isoformat(),
    }


def handler(event, context):
    """AWS Lambda entry point for EIA data ingestion."""
    logger.info(f"EIA ingestion triggered: {json.dumps(event)[:500]}")

    try:
        return success_response(fetch_eia_data(event))
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return error_response(e)
