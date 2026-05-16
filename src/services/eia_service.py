"""
EIA Service — US Energy Information Administration API integration.
Fetches spot prices, supply/demand data, inventory, production statistics.
"""
from __future__ import annotations
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from src.models.price_series import PriceSeries, PricePoint
from src.models.supply_demand import SupplyDemandBalance

load_dotenv()
logger = logging.getLogger(__name__)

EIA_BASE = "https://api.eia.gov/v2"


class EIAService:
    """EIA Open Data API service."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.environ.get("EIA_API_KEY", "")
        self._session = requests.Session()
        self._last_call = 0.0
        self._min_interval = 0.5

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        self._throttle()
        params = params or {}
        params["api_key"] = self.api_key
        try:
            r = self._session.get(f"{EIA_BASE}{endpoint}", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("response", {}).get("error"):
                logger.error(f"EIA API error: {data['response']['error']}")
                return None
            return data
        except Exception as e:
            logger.error(f"EIA request failed: {e}")
            return None

    def get_spot_prices(self, series_id: str, days: int = 30) -> PriceSeries:
        """Fetch daily spot prices for an EIA series."""
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        data = self._get(f"/series/{series_id}", {"start": start, "end": end, "frequency": "daily"})
        series = PriceSeries(commodity_code=series_id, source="EIA", frequency="daily")
        if not data:
            return series
        for element in data.get("response", {}).get("data", []):
            series.add_point(element.get("period", ""), float(element.get("value", 0)))
        return series

    def get_petroleum_data(self, frequency: str = "weekly") -> Dict:
        """Fetch weekly/monthly petroleum supply/demand data."""
        data = self._get("/petroleum", {"frequency": frequency, "data": ["value"]})
        return data or {}

    def get_petroleum_summary(self) -> Optional[SupplyDemandBalance]:
        """Get current petroleum supply/demand summary."""
        data = self._get("/petroleum/stroke/wcrstus2w", {"frequency": "weekly"})
        if not data:
            return None
        rows = data.get("response", {}).get("data", [])
        if not rows:
            return None
        latest = rows[0] if rows else {}
        return SupplyDemandBalance(
            commodity_code="WTI", period=latest.get("period", ""),
            date=latest.get("period", ""),
            production_mbd=float(latest.get("value", 0)),
        )
