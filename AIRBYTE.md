# Airbyte Agents Integration — Scope.Glacier

This document describes how [Airbyte Agents](https://docs.airbyte.com/ai-agents) can replace the custom Lambda ingestion layer for EIA, AlphaVantage, and FRED data with managed connectors.

---

## Overview

Scope.Glacier ingests energy market data via EIA, AlphaVantage, and FRED APIs through custom Lambda handlers. Airbyte Agents can replace these with declarative source configurations, incremental syncs, and built-in error handling.

**Integration options:**
- **[MCP](https://docs.airbyte.com/ai-agents/interfaces/mcp)** — Remote MCP server for ad-hoc energy market queries.
- **[SDK](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — Python library for replacing Lambda-based ingestion.
- **[API](https://docs.airbyte.com/ai-agents/interfaces/sdk)** — REST for IaC orchestration.

---

## Integration Points

### 1. Replace Lambda Ingestion with Airbyte Sources

| Current Service | File | Data | Airbyte Alternative |
|----------------|------|------|-------------------|
| `EIAService` | `src/services/eia_service.py` | Energy spot prices (WTI, Brent, HH, RBOB, HO), supply/demand, inventory | Airbyte EIA (or custom HTTP source) |
| `EnergyPricingService` | `src/services/pricing_service.py` | FRED energy price series (DCOILWTICO, DCOILBRENTEU, DHHNGSP) | Airbyte FRED source |
| `EnergyPricingService` | `src/services/pricing_service.py` | AlphaVantage supplementary energy data | Airbyte AlphaVantage source |

### 2. Airbyte → Iceberg Pipeline

```
External Sources
  ├── EIA API ──────→ Airbyte Source ──→ S3 ──→ Iceberg: price_series, supply_demand_balance
  ├── FRED ──────────→ Airbyte Source ──→ S3 ──→ Iceberg: energy_commodities  
  └── AlphaVantage ──→ Airbyte Source ──→ S3 ──→ Iceberg: price_series
                                                  │
                                                  ▼
                                          Glue ETL (unchanged):
                                            - energy_price_etl.py
                                            - supply_demand_etl.py
                                            - infrastructure_etl.py
                                          Athena Views (unchanged)
                                          Bedrock AI Analysis (unchanged)
```

### 3. Example SDK Usage

```python
from airbyte_agent_sdk import connect

async def refresh_energy_prices():
    """Replace EIA ingestion Lambda."""
    eia = connect("eia")  # or generic HTTP connector
    try:
        result = await eia.execute("data", "list", params={
            "facets": {"duoarea": ["NUS"]},
            "data": ["value"],
            "frequency": "weekly",
            "start": "2026-01-01",
        })
        print(f"Synced {len(result.data)} energy price records")
    finally:
        await eia.close()
```

### 4. MCP for Ad-Hoc Queries

Add the Airbyte MCP server:

```json
{
  "mcpServers": {
    "airbyte": {
      "url": "https://mcp.airbyte.ai/mcp"
    }
  }
}
```

> "Using Airbyte MCP, query my connected energy data sources. Show me the spread between WTI and Brent for the last 30 days."

---

## Getting Started

1. **Sign up** at [app.airbyte.ai](https://app.airbyte.ai).
2. **Install the SDK**:
   ```bash
   uv add airbyte-agent-sdk
   ```
3. **Add to `.env.example`**:
   ```
   AIRBYTE_CLIENT_ID=your_client_id
   AIRBYTE_CLIENT_SECRET=***   ```
4. **Create Airbyte source configurations** for EIA, FRED, and AlphaVantage, removing the need for the Lambda ingestion handlers.

---

## Connector Catalog

| Category | Connectors | Scope.Glacier Use |
|----------|-----------|------------------|
| **Energy** | EIA (custom), S&P Global Platts | Spot prices, supply/demand, inventory |
| **Macro** | FRED | Energy price series, inflation |
| **Financial** | AlphaVantage, Yahoo Finance | Supplementary energy market data |
| **News** | NewsAPI, GDELT | Energy sector news, geopolitical events |
| **Data Warehouse** | Snowflake, S3, Iceberg | Storage |

Full catalog: [docs.airbyte.com/ai-agents/connectors](https://docs.airbyte.com/ai-agents/connectors)
