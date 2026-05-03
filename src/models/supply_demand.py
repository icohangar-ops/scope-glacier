"""
SupplyDemandBalance model — supply, demand, inventory, and implied balance.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

@dataclass
class SupplyDemandBalance:
    balance_id: str = ""
    commodity_code: str = ""
    period: str = ""
    date: str = ""
    production_mbd: float = 0.0  # million barrels/day
    consumption_mbd: float = 0.0
    imports_mbd: float = 0.0
    exports_mbd: float = 0.0
    inventory_mmbl: float = 0.0  # million barrels
    inventory_change_mmbl: float = 0.0
    spare_capacity_mbd: float = 0.0
    utilization_pct: float = 0.0

    def __post_init__(self) -> None:
        if not self.balance_id:
            self.balance_id = f"SD_{self.commodity_code}_{self.period}_{self.date}".strip("_")

    @property
    def implied_balance_mbd(self) -> float:
        return self.production_mbd - self.consumption_mbd + self.imports_mbd - self.exports_mbd

    @property
    def inventory_coverage_days(self) -> float:
        if self.consumption_mbd <= 0:
            return 0.0
        return self.inventory_mmbl / self.consumption_mbd

    @property
    def drawdown_risk(self) -> str:
        days = self.inventory_coverage_days
        if days < 20:
            return "Critical"
        elif days < 30:
            return "Low"
        elif days < 50:
            return "Adequate"
        return "Comfortable"

    def to_dict(self) -> Dict:
        return {
            "balance_id": self.balance_id, "commodity_code": self.commodity_code,
            "period": self.period, "date": self.date,
            "production_mbd": self.production_mbd, "consumption_mbd": self.consumption_mbd,
            "imports_mbd": self.imports_mbd, "exports_mbd": self.exports_mbd,
            "inventory_mmbl": self.inventory_mmbl, "inventory_change_mmbl": self.inventory_change_mmbl,
            "spare_capacity_mbd": self.spare_capacity_mbd, "utilization_pct": self.utilization_pct,
            "implied_balance_mbd": round(self.implied_balance_mbd, 2),
            "inventory_coverage_days": round(self.inventory_coverage_days, 1),
            "drawdown_risk": self.drawdown_risk,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> SupplyDemandBalance:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
