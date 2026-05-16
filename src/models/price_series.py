"""
PriceSeries model — time series of energy commodity prices.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class PricePoint:
    date: str
    price: float
    volume: float = 0.0

    def to_dict(self) -> Dict:
        return {"date": self.date, "price": self.price, "volume": self.volume}

@dataclass
class PriceSeries:
    series_id: str = ""
    commodity_code: str = ""
    source: str = "EIA"
    frequency: str = "daily"
    points: List[PricePoint] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.series_id and self.commodity_code:
            self.series_id = f"PS_{self.commodity_code}"

    def add_point(self, date: str, price: float, volume: float = 0.0) -> None:
        self.points.append(PricePoint(date=date, price=price, volume=volume))

    @property
    def latest_price(self) -> Optional[float]:
        return self.points[0].price if self.points else None

    @property
    def latest_date(self) -> Optional[str]:
        return self.points[0].date if self.points else None

    def get_return_pct(self, days: int = 30) -> Optional[float]:
        if len(self.points) < days + 1:
            return None
        current = self.points[0].price
        past = self.points[days].price
        if past <= 0:
            return None
        return round(((current - past) / past) * 100, 2)

    def get_volatility(self, window: int = 20) -> float:
        if len(self.points) < window + 1:
            return 0.0
        returns = [(self.points[i].price - self.points[i+1].price) / self.points[i+1].price
                   for i in range(window) if self.points[i+1].price > 0]
        if not returns:
            return 0.0
        avg = sum(returns) / len(returns)
        var = sum((r - avg)**2 for r in returns) / len(returns)
        return round(var**0.5 * (252**0.5) * 100, 2)  # Annualized

    def get_moving_avg(self, window: int = 20) -> Optional[float]:
        if len(self.points) < window:
            return None
        return round(sum(p.price for p in self.points[:window]) / window, 2)

    def to_dict(self) -> Dict:
        return {"series_id": self.series_id, "commodity_code": self.commodity_code,
                "source": self.source, "frequency": self.frequency,
                "point_count": len(self.points), "latest_price": self.latest_price,
                "created_at": self.created_at.isoformat()}
