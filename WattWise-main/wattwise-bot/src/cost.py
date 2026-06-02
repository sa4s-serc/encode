"""
cost.py — converts energy in Joules to estimated annual electricity cost (INR).

Formula:
  cost_per_year = energy_joules * calls_per_day * 365 / 3_600_000 * rate_kwh

Where:
  - 3_600_000 J = 1 kWh
  - calls_per_day is block-type-specific (from .wattwise.yml)
  - rate_kwh is the electricity rate (₹/kWh, default: ₹8/kWh — India average)

CO₂ conversion: 1 kWh ≈ 0.716 kg CO₂ (India grid intensity, CEA 2023)
"""
from __future__ import annotations

from typing import Dict

JOULES_PER_KWH = 3_600_000.0
CO2_KG_PER_KWH = 0.716  # India grid intensity (CEA 2023)

DEFAULT_CALLS_PER_DAY: Dict[str, int] = {
    "FunctionDef": 10_000,
    "For": 50_000,
    "While": 20_000,
    "If": 100_000,
    "Try": 5_000,
    "With": 10_000,
}


def compute_cost_per_year(
    energy_joules: float,
    block_type: str,
    rate_kwh: float = 8.0,
    calls_per_day: Dict[str, int] | None = None,
) -> float:
    """Return estimated annual electricity cost in INR for a single block."""
    if calls_per_day is None:
        calls_per_day = DEFAULT_CALLS_PER_DAY
    daily_calls = calls_per_day.get(block_type, 10_000)
    energy_per_year_joules = energy_joules * daily_calls * 365
    energy_per_year_kwh = energy_per_year_joules / JOULES_PER_KWH
    return energy_per_year_kwh * rate_kwh


def compute_co2_delta_kg(cost_delta_inr: float, rate_kwh: float = 8.0) -> float:
    """Return kg CO₂ delta corresponding to a cost delta (INR)."""
    kwh_delta = cost_delta_inr / rate_kwh
    return kwh_delta * CO2_KG_PER_KWH
