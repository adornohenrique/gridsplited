# core/economics.py
from typing import Optional

def benchmark_power_price(
    p_methanol: float,
    p_co2: float,
    water_cost_eur_per_t: float = 7.3,
    trader_margin_pct: float = 0.0,
    power_mwh_per_t: float = 11.2,
    co2_t_per_t: float = 1.3,
) -> float:
    """A reference break-even power price."""
    trader_margin_abs = (trader_margin_pct / 100.0) * p_methanol
    numerator = p_methanol - co2_t_per_t * p_co2 - water_cost_eur_per_t - trader_margin_abs
    return max(0.0, numerator / power_mwh_per_t)
