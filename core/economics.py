# core/economics.py
from typing import Tuple, Optional

def benchmark_power_price(
    p_methanol: float,
    p_co2: float,
    water_cost_eur_per_t: float = 7.3,
    trader_margin_pct: float = 0.0,
    power_mwh_per_t: float = 11.2,
    co2_t_per_t: float = 1.3,
) -> float:
    """
    Break-even power price (€/MWh) including trader margin as % of revenue.
    Formula: (pMeOH − CO2_need * pCO2 − water − margin% * pMeOH) / MWh_per_t
    """
    trader_margin_abs = (trader_margin_pct / 100.0) * p_methanol
    numerator = p_methanol - co2_t_per_t * p_co2 - water_cost_eur_per_t - trader_margin_abs
    return max(0.0, numerator / power_mwh_per_t)


def compute_price_cap(
    *,
    margin_method: str,
    target_margin_pct: float,
    break_even_eur_per_mwh: float,
    maint_pct: float,
    sga_pct: float,
    ins_pct: float,
    mwh_per_ton: float,
    methanol_price: float,
    co2_price: float,
    co2_t_per_t: float,
) -> Tuple[float, str, Optional[str]]:
    """
    Returns (price_cap_eur_per_mwh, method_tag, error_message_or_None).

    margin_method:
      - "Power-only (vs BE)"   -> cap = (1 - p) * break_even
      - "Full-economics"       -> cap = (pMeOH * (1 - p - o) - pCO2 * CO2_need) / MWh_per_t
         where o = maint_pct + sga_pct + ins_pct (all as fractions, e.g. 0.03)
    """
    p = float(target_margin_pct) / 100.0
    method_tag = "power-only" if str(margin_method).lower().startswith("power") else "full-econ"

    if method_tag == "power-only":
        cap = max(0.0, (1.0 - p) * float(break_even_eur_per_mwh))
        return cap, method_tag, None

    # full-economics branch
    if mwh_per_ton is None or float(mwh_per_ton) <= 0:
        return 0.0, "full-econ", "Full-economics margin requires Electricity per ton (MWh/t) > 0."

    o = float(maint_pct or 0) + float(sga_pct or 0) + float(ins_pct or 0)
    cap = (float(methanol_price) * (1.0 - p - o) - float(co2_price) * float(co2_t_per_t)) / float(mwh_per_ton)
    return max(0.0, cap), method_tag, None
