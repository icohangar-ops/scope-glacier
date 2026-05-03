"""
EnergyCommodity model — crude oil, natural gas, gasoline, heating oil, electricity.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

class EnergyType(str, Enum):
    CRUDE_OIL = "Crude Oil"
    NATURAL_GAS = "Natural Gas"
    GASOLINE = "Gasoline"
    HEATING_OIL = "Heating Oil"
    ELECTRICITY = "Electricity"
    RENEWABLE = "Renewable"
    NUCLEAR = "Nuclear"
    COAL = "Coal"

ENERGY_COMMODITIES = [
    {"code": "WTI", "name": "West Texas Intermediate", "type": EnergyType.CRUDE_OIL, "unit": "USD/barrel", "eia_series": "PET.RWTC.D"},
    {"code": "BRENT", "name": "Brent Crude", "type": EnergyType.CRUDE_OIL, "unit": "USD/barrel", "eia_series": "PET.RBRTE.D"},
    {"code": "HH", "name": "Henry Hub Natural Gas", "type": EnergyType.NATURAL_GAS, "unit": "USD/MMBtu", "eia_series": "NG.RNGWHHD.D"},
    {"code": "RBOB", "name": "RBOB Gasoline", "type": EnergyType.GASOLINE, "unit": "USD/gallon", "eia_series": "PET.EER_EPMRU_PF4_YCG_DPG.D"},
    {"code": "HO", "name": "No. 2 Heating Oil", "type": EnergyType.HEATING_OIL, "unit": "USD/gallon", "eia_series": "PET.EER_EPD2F_PF4_Yhou_DPG.D"},
    {"code": "URANIUM", "name": "Uranium U3O8", "type": EnergyType.NUCLEAR, "unit": "USD/lb", "eia_series": ""},
]

@dataclass
class EnergyCommodity:
    commodity_id: str = ""
    code: str = ""
    name: str = ""
    energy_type: EnergyType = EnergyType.CRUDE_OIL
    current_price: float = 0.0
    unit: str = "USD/barrel"
    eia_series_id: str = ""
    av_symbol: str = ""
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not self.commodity_id and self.code:
            self.commodity_id = f"NRG_{self.code}"

    def to_dict(self) -> Dict:
        return {"commodity_id": self.commodity_id, "code": self.code, "name": self.name,
                "energy_type": self.energy_type.value, "current_price": self.current_price,
                "unit": self.unit, "eia_series_id": self.eia_series_id, "updated_at": self.updated_at.isoformat()}

    @classmethod
    def from_dict(cls, d: Dict) -> EnergyCommodity:
        if "energy_type" in d and isinstance(d["energy_type"], str):
            d["energy_type"] = EnergyType(d["energy_type"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def create_all(cls) -> List[EnergyCommodity]:
        return [cls(code=e["code"], name=e["name"], energy_type=e["type"], unit=e["unit"], eia_series_id=e.get("eia_series", "")) for e in ENERGY_COMMODITIES]

    def __repr__(self) -> str:
        return f"EnergyCommodity({self.code}, {self.name}, ${self.current_price:.2f}/{self.unit})"
