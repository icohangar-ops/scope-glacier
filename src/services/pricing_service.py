"""
EnergyPricingService — AlphaVantage + FRED energy price integration.
"""
from __future__ import annotations
import logging
import os
from typing import Dict, Optional
import requests

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"
AV_BASE = "https://www.alphavantage.co/query"

class EnergyPricingService:
    """Energy price data from AlphaVantage and FRED."""

    def __init__(self, av_key: str = "", fred_key: str = "") -> None:
        self.av_key = av_key or os.environ.get("ALPHA_VANTAGE_KEY", "")
        self.fred_key = fred_key or os.environ.get("FRED_API_KEY", "")
        self._session = requests.Session()
        self._av_calls = 0

    def get_fred_energy_price(self, series_id: str) -> Optional[float]:
        if not self.fred_key:
            return None
        try:
            r = self._session.get(f"{FRED_BASE}/series/observations", params={
                "series_id": series_id, "api_key": self.fred_key,
                "file_type": "json", "sort_order": "desc", "limit": 1,
            }, timeout=30)
            obs = r.json().get("observations", [])
            if obs and obs[0].get("value", ".") != ".":
                return float(obs[0]["value"])
            return None
        except Exception as e:
            logger.error(f"FRED energy error: {e}")
            return None

    def get_crude_oil_prices(self) -> Dict[str, Optional[float]]:
        """Get WTI and Brent crude prices."""
        return {
            "WTI": self.get_fred_energy_price("DCOILWTICO"),
            "BRENT": self.get_fred_energy_price("DCOILBRENTEU"),
        }

    def get_natural_gas_price(self) -> Optional[float]:
        return self.get_fred_energy_price("DHHNGSP")

    def get_all_prices(self) -> Dict[str, Optional[float]]:
        prices = self.get_crude_oil_prices()
        prices["NG"] = self.get_natural_gas_price()
        return prices
