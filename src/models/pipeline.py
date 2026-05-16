"""
Pipeline model — oil/gas pipeline tracking.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

class PipelineStatus(str, Enum):
    OPERATIONAL = "Operational"
    REDUCED = "Reduced Flow"
    SHUTDOWN = "Shutdown"
    PLANNED = "Planned Maintenance"
    FORCE_MAJEURE = "Force Majeure"

@dataclass
class Pipeline:
    pipeline_id: str = ""
    name: str = ""
    commodity: str = ""
    origin: str = ""
    destination: str = ""
    capacity_bpd: float = 0.0
    current_flow_bpd: float = 0.0
    status: PipelineStatus = PipelineStatus.OPERATIONAL
    length_miles: float = 0.0
    countries_crossed: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.pipeline_id:
            self.pipeline_id = f"PIPE_{self.name.replace(' ', '_')}".strip("_")

    @property
    def utilization_pct(self) -> float:
        if self.capacity_bpd <= 0:
            return 0.0
        return round((self.current_flow_bpd / self.capacity_bpd) * 100, 1)

    @property
    def is_disrupted(self) -> bool:
        return self.status in (PipelineStatus.SHUTDOWN, PipelineStatus.REDUCED, PipelineStatus.FORCE_MAJEURE)

    def to_dict(self) -> Dict:
        return {
            "pipeline_id": self.pipeline_id, "name": self.name, "commodity": self.commodity,
            "origin": self.origin, "destination": self.destination,
            "capacity_bpd": self.capacity_bpd, "current_flow_bpd": self.current_flow_bpd,
            "utilization_pct": self.utilization_pct, "status": self.status.value,
            "length_miles": self.length_miles, "is_disrupted": self.is_disrupted,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> Pipeline:
        if "status" in d and isinstance(d["status"], str):
            d["status"] = PipelineStatus(d["status"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
