# core/economics.py
from typing import Tuple, Optional, Dict, Any

def benchmark_power_price(
    p_methanol: float,
    p_co2: float,
    water_cost_eur_per_t: float = 7.3,
    trader_margin_pct: float = 0.0,
    power_mwh_per_t: float = 11.2,
    co2_t_per_t: float = 1.3,
) -> float:
    trader_margin_abs = (trader_margin_pct / 100.0) * p_methanol
    numerator = p_methanol - co2_t_per_t * p_co2 - water_cost_eur_per_t - trader_margin_abs
    return max(0.0, numerator / power_mwh_per_t)

def compute_price_cap(
    margin_method: str,
    target_margin_pct: float,
    break_even_eur_per_mwh: float,
    maint_pct: float,
    sga_pct: float,
    ins_pct: float,
    mwh_per_ton: float,
    methanol_price: float,
    co2_price: float,
    co2_intensity: float,
) -> Tuple[Optional[float], str, Optional[str]]:
    p = float(target_margin_pct) / 100.0
    if margin_method.startswith("Power"):
        return max(0.0, (1.0 - p) * break_even_eur_per_mwh), "power-only", None

    o = float(maint_pct or 0) + float(sga_pct or 0) + float(ins_pct or 0)
    if mwh_per_ton <= 0:
        return None, "full-econ", "Full-economics margin requires Electricity per ton (MWh/t) > 0."
    cap = (methanol_price * (1.0 - p - o) - co2_price * co2_intensity) / mwh_per_ton
    return max(0.0, cap), "full-econ", None

def build_kpis_view(
    kpis: Dict[str, Any],
    break_even: float,
    mwh_per_ton: float,
    co2_price: float,
    co2_intensity: float,
    water_cost_t: float,
    other_opex_per_t: float,
) -> Dict[str, Any]:
    show_cols = [
        "dispatch_threshold_eur_per_mwh",
        "target_margin_fraction",
        "margin_method",
        "total_energy_mwh",
        "weighted_avg_price_eur_per_mwh",
        "total_power_cost_eur",
        "total_tons",
        "total_methanol_revenue_eur",
        "total_co2_cost_eur",
        "total_opex_misc_eur",
        "total_true_profit_eur",
        "total_profit_proxy_eur",
    ]
    view = {k: kpis.get(k, None) for k in show_cols}

    power_cost_at_BE_per_t = float(break_even) * float(mwh_per_ton)
    co2_cost_per_t         = float(co2_price) * float(co2_intensity)
    non_power_opex_per_t   = water_cost_t + float(other_opex_per_t or 0)
    total_variable_cost_BE = power_cost_at_BE_per_t + co2_cost_per_t + non_power_opex_per_t

    view["power_cost_at_BE_eur_per_t"] = round(power_cost_at_BE_per_t, 2)
    view["co2_cost_eur_per_t"] = round(co2_cost_per_t, 2)
    view["non_power_opex_eur_per_t"] = round(non_power_opex_per_t, 2)
    view["total_variable_cost_BE_eur_per_t"] = round(total_variable_cost_BE, 2)
    return view
