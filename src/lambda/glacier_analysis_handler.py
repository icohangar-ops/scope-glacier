"""
Glacier Analysis Lambda Handler — computes composite energy signals and Bedrock AI analysis.

Orchestrated by Step Functions state machine:
1. Compute component scores (supply/demand, price momentum, geopolitical, seasonal)
2. Generate Glacier Signals
3. Call Bedrock for AI analysis via Converse API
4. Write signals to Iceberg
"""

import json
import logging
import os
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)

SCORE_WEIGHTS = {"supply_demand": 0.30, "price_momentum": 0.25, "geopolitical": 0.25, "seasonal": 0.20}


def compute_glacier_scores(event):
    """Compute composite Glacier scores for specified energy commodities.

    Expected event:
    {
        "commodity_codes": ["WTI", "BRENT", "HH"],
        "utilization_pct": 92.0,
        "inventory_days": 28.0
    }
    """
    commodity_codes = event.get("commodity_codes", ["WTI", "BRENT", "HH"])
    utilization_pct = event.get("utilization_pct", 92.0)
    inventory_days = event.get("inventory_days", 28.0)

    athena = boto3.client("athena")
    database = os.environ.get("GLUE_DATABASE", "scope_glacier")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-glacier-queries/")

    signals = []
    for code in commodity_codes:
        try:
            query = f"""
            WITH latest_price AS (
                SELECT price_value, price_date FROM scope_glacier.price_series
                WHERE commodity_code = '{code}'
                ORDER BY price_date DESC LIMIT 1
            ),
            price_30d_ago AS (
                SELECT price_value FROM scope_glacier.price_series
                WHERE commodity_code = '{code}'
                  AND price_date >= DATE_ADD('DAY', -35, CURRENT_DATE)
                ORDER BY price_date ASC LIMIT 1
            ),
            vol AS (
                SELECT
                    STDDEV(price_value) AS daily_std
                FROM scope_glacier.price_series
                WHERE commodity_code = '{code}'
                  AND price_date >= DATE_ADD('DAY', -25, CURRENT_DATE)
            )
            SELECT
                '{code}' AS commodity_code,
                (SELECT price_value FROM latest_price) AS latest_price,
                CASE
                    WHEN (SELECT price_value FROM latest_price) > 0
                        AND (SELECT price_value FROM price_30d_ago) > 0
                    THEN ROUND(
                        ((SELECT price_value FROM latest_price) - (SELECT price_value FROM price_30d_ago))
                        / (SELECT price_value FROM price_30d_ago) * 100, 2)
                    ELSE 0
                END AS return_30d_pct,
                ROUND(COALESCE((SELECT daily_std FROM vol), 0) * (252.0 ** 0.5) * 100, 2) AS annualized_volatility_pct
            """

            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}glacier/scores/"},
            )

            # Compute component scores
            sd_score = 50.0
            if utilization_pct > 95:
                sd_score += 30
            elif utilization_pct > 90:
                sd_score += 20
            elif utilization_pct < 75:
                sd_score -= 15
            if inventory_days < 25:
                sd_score += 20
            elif inventory_days > 60:
                sd_score -= 10

            glacier_score = round(
                sd_score * SCORE_WEIGHTS["supply_demand"]
                + 50.0 * SCORE_WEIGHTS["price_momentum"]
                + 50.0 * SCORE_WEIGHTS["geopolitical"]
                + 50.0 * SCORE_WEIGHTS["seasonal"],
                2,
            )

            rating = "Hold"
            if glacier_score >= 80:
                rating = "Strong Buy"
            elif glacier_score >= 65:
                rating = "Buy"
            elif glacier_score < 35:
                rating = "Sell"
            elif glacier_score < 20:
                rating = "Strong Sell"

            signals.append({
                "commodity_code": code,
                "query_id": response["QueryExecutionId"],
                "glacier_score": glacier_score,
                "signal_rating": rating,
                "supply_demand_score": sd_score,
                "status": "submitted",
            })
            logger.info(f"Computed Glacier score for {code}: {glacier_score} ({rating})")

        except Exception as e:
            logger.error(f"Error computing score for {code}: {e}")
            signals.append({"commodity_code": code, "status": "error", "error": str(e)})

    return signals


def invoke_bedrock_analysis(commodity_code: str, signal_data: dict) -> str:
    """Invoke Bedrock Converse API for energy market AI analysis."""
    bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    model_id = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    prompt = f"""Analyze {commodity_code} energy market:

Glacier Score: {signal_data.get('glacier_score', 'N/A')}/100 ({signal_data.get('signal_rating', 'Hold')})
- Supply/Demand Score: {signal_data.get('supply_demand_score', 50):.0f}/100
- Price Momentum Score: {signal_data.get('price_momentum_score', 50):.0f}/100
- Geopolitical Score: {signal_data.get('geopolitical_score', 50):.0f}/100
- Seasonal Score: {signal_data.get('seasonal_score', 50):.0f}/100
- Latest Price: {signal_data.get('latest_price', 'N/A')}
- 30-Day Return: {signal_data.get('return_30d_pct', 'N/A')}%
- Annualized Volatility: {signal_data.get('annualized_volatility', 'N/A')}%

Provide 2-3 paragraphs covering supply/demand outlook, geopolitical risks, seasonal factors, and price direction."""

    try:
        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[{"text": "You are a senior energy market analyst. Be data-driven and concise."}],
            inferenceConfig={"maxTokens": 800, "temperature": 0.3},
        )
        content_blocks = response.get("output", {}).get("message", {}).get("content", [])
        return "".join(cb.get("text", "") for cb in content_blocks)
    except Exception as e:
        logger.error(f"Bedrock analysis failed for {commodity_code}: {e}")
        return f"Analysis unavailable: {str(e)}"


def write_signals_to_iceberg(signals: list):
    """Write Glacier signals to Iceberg table via Athena."""
    athena = boto3.client("athena")
    database = os.environ.get("GLUE_DATABASE", "scope_glacier")
    s3_output = os.environ.get("ATHENA_OUTPUT", "s3://scope-glacier-queries/")

    for signal in signals:
        if signal.get("status") != "analyzed":
            continue
        try:
            code = signal["commodity_code"]
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            signal_id = f"{code}_{ts}"
            analysis = signal.get("ai_analysis", "")[:4000].replace("'", "''")

            query = f"""
            INSERT INTO {database}.glacier_signals
            VALUES (
                '{signal_id}',
                '{code}',
                TIMESTAMP '{datetime.utcnow().isoformat()}',
                {signal.get('supply_demand_score', 50)},
                {signal.get('price_momentum_score', 50)},
                {signal.get('geopolitical_score', 50)},
                {signal.get('seasonal_score', 50)},
                {signal.get('glacier_score', 50)},
                '{signal.get('signal_rating', 'Hold')}',
                '{analysis}',
                {signal.get('confidence_score', 0.5)},
                '{json.dumps(signal.get('data_sources', [])).replace("'", "''")}'
            )
            """
            athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": database},
                ResultConfiguration={"OutputLocation": f"{s3_output}signals/write/"},
            )
        except Exception as e:
            logger.error(f"Error writing signal for {code}: {e}")


def handler(event, context):
    """AWS Lambda entry point for Glacier analysis pipeline.

    Step Functions passes:
    {
        "step": "compute_scores" | "bedrock_analysis" | "write_signals",
        "commodity_codes": ["WTI", "BRENT", "HH"],
        "signals": [...]  // for bedrock_analysis or write_signals steps
    }
    """
    logger.info(f"Glacier analysis Lambda triggered: {json.dumps(event)[:500]}")

    step = event.get("step", "compute_scores")

    if step == "compute_scores":
        signals = compute_glacier_scores(event)
        return {"statusCode": 200, "body": json.dumps({"step": step, "signals": signals})}

    elif step == "bedrock_analysis":
        signals = event.get("signals", [])
        for signal in signals:
            code = signal.get("commodity_code", "")
            analysis = invoke_bedrock_analysis(code, signal)
            signal["ai_analysis"] = analysis
            signal["status"] = "analyzed"
        return {"statusCode": 200, "body": json.dumps({"step": step, "signals": signals})}

    elif step == "write_signals":
        write_signals_to_iceberg(event.get("signals", []))
        return {"statusCode": 200, "body": json.dumps({"step": step, "status": "completed"})}

    return {"statusCode": 400, "body": json.dumps({"error": f"Unknown step: {step}"})}
