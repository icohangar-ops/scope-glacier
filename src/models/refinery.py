"""
Refinery model — oil refinery tracking.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict

class RefineryStatus(str, Enum):
    OPERATING = "Operating"
    MAINTENANCE = "Maintenance"
    SHUTDOWN = "Shutdown"
    IDLE = "Idle"

@dataclass
class Refinery:
    refinery_id: str = ""
    name: str = ""
    region: str = ""
    country: str = ""
    capacity_bpd: float = 0.0
    utilization_pct: float = 0.0
    status: RefineryStatus = RefineryStatus.OPERATING
    crude_type: str = ""
    throughput_bpd: float = 0.0

    def __post_init__(self) -> None:
        if not self.refinery_id:
            self.refinery_id = f"REF_{self.name.replace(' ', '_')}_{self.region}".strip("_")
        self.throughput_bpd = self.capacity_bpd * (self.utilization_pct / 100.0) if self.utilization_pct else 0.0

    @property
    def offline_bpd(self) -> float:
        return self.capacity_bpd - self.throughput_bpd

    def to_dict(self) -> Dict:
        return {
            "refinery_id": self.refinery_id, "name": self.name, "region": self.region,
            "country": self.country, "capacity_bpd": self.capacity_bpd,
            "utilization_pct": self.utilization_pct, "status": self.status.value,
            "crude_type": self.crude_type, "throughput_bpd": self.throughput_bpd,
            "offline_bpd": self.offline_bpd,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Refinery:
        if "status" in d and isinstance(d["status"], str):
            d["status"] = RefineryStatus(d["status"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
