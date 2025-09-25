# core/optimizer.py
import numpy as np
import pandas as pd

def run_dispatch(
    df: pd.DataFrame,
    plant_capacity_mw: float,
    min_load_pct: float,
    max_load_pct: float,
    break_even_eur_per_mwh: float,
    ramp_limit_mw_per_step: float | None,
    always_on: bool,
    dispatch_threshold_eur_per_mwh: float,
    mwh_per_ton: float | None,
    methanol_price_eur_per_ton: float,
    co2_price_eur_per_ton: float,
    co2_t_per_ton_meoh: float,
    maintenance_pct_of_revenue: float,
    sga_pct_of_revenue: float,
    insurance_pct_of_revenue: float,
    target_margin_fraction: float,
    margin_method: str,
):
    """
    Simple profit-max logic for an electricity-consuming plant (e.g., eMeOH):
    - Run more when power price is low (<= price cap).
    - Honor min/max load and optional ramp constraint.
    - If ALWAYS_ON, never go below min load; otherwise can go to zero when price is too high.
    """

    df = df.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    # bounds
    min_mw = (min_load_pct / 100.0) * plant_capacity_mw
    max_mw = (max_load_pct / 100.0) * plant_capacity_mw

    # Decision rule: consume max when price <= threshold, else consume min/0
    def target_mw(price):
        if price <= dispatch_threshold_eur_per_mwh:
            return max_mw
        else:
            return min_mw if always_on else 0.0

    df["target_mw"] = df["price_eur_per_mwh"].apply(target_mw)

    # Apply ramp if provided (per 15-min step)
    dispatch = []
    prev = min_mw if always_on else 0.0
    for mw in df["target_mw"]:
        if ramp_limit_mw_per_step is not None:
            upper = prev + ramp_limit_mw_per_step
            lower = prev - ramp_limit_mw_per_step
            mw = max(lower, min(upper, mw))
        mw = max(min_mw if always_on else 0.0, min(mw, max_mw))
        dispatch.append(mw)
        prev = mw

    df["dispatch_mw"] = dispatch

    # Energy per quarter-hour
    df["energy_mwh"] = df["dispatch_mw"] * 0.25

    # Costs & production
    df["power_cost_eur"] = df["energy_mwh"] * df["price_eur_per_mwh"]

    if mwh_per_ton and mwh_per_ton > 0:
        df["tons"] = df["energy_mwh"] / float(mwh_per_ton)
    else:
        df["tons"] = 0.0

    # Revenues & other costs (if mwh_per_ton given)
    df["revenue_eur"] = df["tons"] * float(methanol_price_eur_per_ton)
    df["co2_cost_eur"] = df["tons"] * float(co2_price_eur_per_ton) * float(co2_t_per_ton_meoh)

    revenue = df["revenue_eur"].sum()
    other_pct = float(maintenance_pct_of_revenue or 0) + float(sga_pct_of_revenue or 0) + float(insurance_pct_of_revenue or 0)
    other_costs_eur = revenue * other_pct

    # Profit (true)
    total_power_cost = df["power_cost_eur"].sum()
    total_co2_cost = df["co2_cost_eur"].sum()
    total_tons = df["tons"].sum()
    true_profit = revenue - total_power_cost - total_co2_cost - other_costs_eur

    # A proxy: “price vs break-even” (not used for decisions, just reported)
    df["price_minus_be"] = df["price_eur_per_mwh"] - float(break_even_eur_per_mwh)
    profit_proxy = (df["energy_mwh"] * (-df["price_minus_be"])).sum()  # lower price vs BE is “better”

    kpis = {
        "total_energy_mwh": float(df["energy_mwh"].sum()),
        "weighted_avg_price_eur_per_mwh": float(
            (df["price_eur_per_mwh"] * df["energy_mwh"]).sum() / max(1e-9, df["energy_mwh"].sum())
        ),
        "total_power_cost_eur": float(total_power_cost),
        "total_tons": float(total_tons),
        "total_methanol_revenue_eur": float(revenue),
        "total_co2_cost_eur": float(total_co2_cost),
        "total_opex_misc_eur": float(other_costs_eur),
        "total_true_profit_eur": float(true_profit),
        "total_profit_proxy_eur": float(profit_proxy),
        "dispatch_threshold_eur_per_mwh": float(dispatch_threshold_eur_per_mwh),
        "target_margin_fraction": float(target_margin_fraction),
        "margin_method": str(margin_method),
    }

    results = df[[
        "timestamp", "price_eur_per_mwh", "dispatch_mw", "energy_mwh",
        "power_cost_eur", "tons", "revenue_eur", "co2_cost_eur"
    ]].copy()

    return results, kpis
