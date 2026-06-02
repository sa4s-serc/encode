from __future__ import annotations

INR_PER_USD = 84.0
AWS_RATE_KWH_USD = 0.096
AWS_RATE_KWH = AWS_RATE_KWH_USD * INR_PER_USD  # INR/kWh
CO2_KG_PER_KWH = 0.4
JOULES_PER_KWH = 3_600_000.0

DEFAULT_CALLS_PER_DAY = {
    "FunctionDef": 10_000,
    "For": 50_000,
    "While": 20_000,
    "If": 100_000,
    "Try": 5_000,
    "With": 10_000,
}


def annual_kwh(energy_j: float, calls_per_day: int) -> float:
    return energy_j * calls_per_day * 365 / JOULES_PER_KWH


def annual_cost_usd(energy_j: float, calls_per_day: int, aws_rate_kwh: float = AWS_RATE_KWH) -> float:
    return annual_kwh(energy_j, calls_per_day) * aws_rate_kwh


def annual_co2_kg(energy_j: float, calls_per_day: int, co2_kg_per_kwh: float = CO2_KG_PER_KWH) -> float:
    return annual_kwh(energy_j, calls_per_day) * co2_kg_per_kwh
