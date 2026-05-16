"""
GlacierIntelligenceService — composite scoring + Bedrock AI analysis for energy markets.
Score: Supply/Demand 30% + Price Momentum 25% + Geopolitical 25% + Seasonal 20%.
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from src.models.glacier_signal import GlacierSignal, SCORE_WEIGHTS

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior energy market analyst with expertise in crude oil, natural gas,
refining, and global energy geopolitics. Provide data-driven analysis covering supply/demand dynamics,
geopolitical risks, seasonal patterns, and strategic recommendations."""

class GlacierIntelligenceService:
    """Composite energy scoring and Bedrock AI analysis."""

    def __init__(self, bedrock_client: Optional[Any] = None) -> None:
        if bedrock_client is None:
            from bedrock_client import BedrockClient
            self._client = BedrockClient()
        else:
            self._client = bedrock_client
        self._eia_svc = None
        self._pricing_svc = None

    def set_services(self, eia_svc: Any = None, pricing_svc: Any = None) -> None:
        self._eia_svc = eia_svc
        self._pricing_svc = pricing_svc

    def compute_supply_demand_score(self, balance_pct: float = 100.0, inventory_days: float = 40.0) -> float:
        score = 50.0
        # High utilization = bullish (tight supply)
        if balance_pct > 95:
            score += 30
        elif balance_pct > 90:
            score += 20
        elif balance_pct > 85:
            score += 10
        elif balance_pct < 75:
            score -= 15
        # Low inventory = bullish
        if inventory_days < 25:
            score += 20
        elif inventory_days < 35:
            score += 10
        elif inventory_days > 60:
            score -= 10
        return max(0, min(100, score))

    def compute_price_momentum_score(self, return_30d: float = 0.0, volatility: float = 30.0) -> float:
        score = 50.0
        if return_30d > 15:
            score += 25
        elif return_30d > 5:
            score += 15
        elif return_30d > 0:
            score += 5
        elif return_30d < -15:
            score -= 25
        elif return_30d < -5:
            score -= 15
        # Low volatility = stable
        if volatility < 20:
            score += 5
        elif volatility > 50:
            score -= 10
        return max(0, min(100, score))

    def compute_geopolitical_score(self, risk_level: float = 50.0, opec_compliance: float = 80.0) -> float:
        score = 50.0
        if risk_level > 75:
            score -= 25
        elif risk_level > 50:
            score -= 10
        if opec_compliance > 90:
            score += 15
        elif opec_compliance < 70:
            score -= 15
        return max(0, min(100, score))

    def compute_seasonal_score(self, month: int = 1, is_driving_season: bool = False, is_heating_season: bool = False) -> float:
        score = 50.0
        if is_driving_season:
            score += 20  # Summer driving season bullish for gasoline/crude
        if is_heating_season:
            score += 20  # Winter heating season bullish for NG/HO
        if month in (9, 10, 11):
            score += 5  # Fall stock build-up
        return max(0, min(100, score))

    def generate_signal(self, commodity_code: str, **kwargs) -> GlacierSignal:
        sd = kwargs.get("supply_demand_score", self.compute_supply_demand_score(
            kwargs.get("utilization_pct", 100), kwargs.get("inventory_days", 40)))
        pm = kwargs.get("price_momentum_score", self.compute_price_momentum_score(
            kwargs.get("return_30d", 0), kwargs.get("volatility", 30)))
        geo = kwargs.get("geopolitical_score", self.compute_geopolitical_score(
            kwargs.get("geopolitical_risk", 50), kwargs.get("opec_compliance", 80)))
        sea = kwargs.get("seasonal_score", self.compute_seasonal_score(
            kwargs.get("month", 1), kwargs.get("is_driving_season", False), kwargs.get("is_heating_season", False)))
        return GlacierSignal(
            commodity_code=commodity_code,
            supply_demand_score=sd, price_momentum_score=pm,
            geopolitical_score=geo, seasonal_score=sea,
        )

    def generate_ai_analysis(self, signal: GlacierSignal, context: Dict = None) -> str:
        prompt = f"""Analyze {signal.commodity_code} energy market:

Glacier Score: {signal.glacier_score}/100 ({signal.signal_rating.value})
- Supply/Demand: {signal.supply_demand_score:.0f}/100
- Price Momentum: {signal.price_momentum_score:.0f}/100
- Geopolitical: {signal.geopolitical_score:.0f}/100
- Seasonal: {signal.seasonal_score:.0f}/100
"""
        if context:
            prompt += f"\nContext:\n{json.dumps(context, indent=2, default=str)}\n"
        prompt += "\nProvide 2-3 paragraphs with risks, opportunities, and price outlook."
        try:
            return self._client.chat(prompt, system=SYSTEM_PROMPT, max_tokens=800)
        except Exception as e:
            return f"Analysis unavailable: {str(e)}"
