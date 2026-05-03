"""
GlacierSignal model — composite energy market signal.
Score: Supply/Demand 30% + Price Momentum 25% + Geopolitical 25% + Seasonal 20%.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

class SignalRating(str, Enum):
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"

SCORE_WEIGHTS = {"supply_demand": 0.30, "price_momentum": 0.25, "geopolitical": 0.25, "seasonal": 0.20}

@dataclass
class GlacierSignal:
    signal_id: str = ""
    commodity_code: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    supply_demand_score: float = 50.0
    price_momentum_score: float = 50.0
    geopolitical_score: float = 50.0
    seasonal_score: float = 50.0
    glacier_score: float = 50.0
    signal_rating: SignalRating = SignalRating.HOLD
    ai_analysis: str = ""
    confidence_score: float = 0.0
    data_sources: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.signal_id:
            ts = self.generated_at.strftime("%Y%m%d_%H%M%S")
            self.signal_id = f"{self.commodity_code}_{ts}" if self.commodity_code else f"signal_{ts}"
        self._compute_composite()

    def _compute_composite(self) -> None:
        self.glacier_score = round(
            self.supply_demand_score * SCORE_WEIGHTS["supply_demand"]
            + self.price_momentum_score * SCORE_WEIGHTS["price_momentum"]
            + self.geopolitical_score * SCORE_WEIGHTS["geopolitical"]
            + self.seasonal_score * SCORE_WEIGHTS["seasonal"], 2)
        self.signal_rating = self._score_to_rating(self.glacier_score)

    @staticmethod
    def _score_to_rating(score: float) -> SignalRating:
        if score >= 80: return SignalRating.STRONG_BUY
        elif score >= 65: return SignalRating.BUY
        elif score >= 35: return SignalRating.HOLD
        elif score >= 20: return SignalRating.SELL
        return SignalRating.STRONG_SELL

    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id, "commodity_code": self.commodity_code,
            "generated_at": self.generated_at.isoformat(),
            "supply_demand_score": self.supply_demand_score,
            "price_momentum_score": self.price_momentum_score,
            "geopolitical_score": self.geopolitical_score,
            "seasonal_score": self.seasonal_score,
            "glacier_score": self.glacier_score,
            "signal_rating": self.signal_rating.value,
            "ai_analysis": self.ai_analysis, "confidence_score": self.confidence_score,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> GlacierSignal:
        if "signal_rating" in d and isinstance(d["signal_rating"], str):
            d["signal_rating"] = SignalRating(d["signal_rating"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
