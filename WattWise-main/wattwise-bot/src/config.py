"""
config.py — loads .wattwise.yml from the repo root and exposes a typed config object.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


DEFAULT_CALLS_PER_DAY: Dict[str, int] = {
    "FunctionDef": 10_000,
    "For": 50_000,
    "While": 20_000,
    "If": 100_000,
    "Try": 5_000,
    "With": 10_000,
}


@dataclass
class CostConfig:
    rate_kwh: float = 8.0  # ₹/kWh — India average electricity rate
    default_calls_per_day: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_CALLS_PER_DAY))


@dataclass
class WattwiseConfig:
    require_manager_approval: bool = True
    max_new_high_blocks: int = 0
    regression_threshold_cost: float = 500.0  # ₹/yr
    block_on_gate_failure: bool = True
    managers: List[str] = field(default_factory=list)
    cost: CostConfig = field(default_factory=CostConfig)


def load_config(repo_path: Optional[str] = None) -> WattwiseConfig:
    """Load .wattwise.yml from repo_path (defaults to GITHUB_WORKSPACE or cwd)."""
    if repo_path is None:
        repo_path = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

    config_path = os.path.join(repo_path, ".wattwise.yml")

    if not os.path.exists(config_path):
        return WattwiseConfig()

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f) or {}

    energy_section = raw.get("energy", {})
    managers_section = raw.get("managers", [])
    cost_section = raw.get("cost", {})

    # Support both old key (aws_rate_kwh) and new key (rate_kwh) for compatibility
    rate = cost_section.get("rate_kwh", cost_section.get("aws_rate_kwh", 8.0))

    cost_cfg = CostConfig(
        rate_kwh=float(rate),
        default_calls_per_day={
            **DEFAULT_CALLS_PER_DAY,
            **{k: int(v) for k, v in cost_section.get("default_calls_per_day", {}).items()},
        },
    )

    return WattwiseConfig(
        require_manager_approval=bool(energy_section.get("require_manager_approval", True)),
        max_new_high_blocks=int(energy_section.get("max_new_high_blocks", 0)),
        regression_threshold_cost=float(energy_section.get("regression_threshold_cost", 500.0)),
        block_on_gate_failure=bool(energy_section.get("block_on_gate_failure", True)),
        managers=[str(m).lstrip("@") for m in managers_section],
        cost=cost_cfg,
    )
