# core/economics.py
from __future__ import annotations
import pandas as pd

def compute_kpis(
    disp: pd.DataFrame,
    mwh_per_ton: float,
    meoh_price_eur_per_ton: float,
    co2_price_eur_per_ton: float,
    co2_t_per_ton_meoh: float,
    maint_pct: float,
    sga_pct: float,
    ins_pct: float,
    water_cost_eur_per_ton: float,
    other_opex_eur_per_ton: float,
    break_even_eur_per_mwh: float,
) -> dict:
    total_mwh = float(disp["mwh"].sum())
    avg_price = float((disp["price"] * disp["mwh"]).sum() / max(total_mwh, 1e-9))
    tons = (total_mwh / mwh_per_ton) if mwh_per_ton > 0 else 0.0

    revenue_meoh = tons * meoh_price_eur_per_ton
    power_cost = (disp["price"] * disp["mwh"]).sum()
    co2_cost = tons * co2_t_per_ton_meoh * co2_price_eur_per_ton
    overheads = revenue_meoh * (maint_pct + sga_pct + ins_pct) / 100.0
    other_opex = tons * (water_cost_eur_per_ton + other_opex_eur_per_ton)
    ebitda_full = revenue_meoh - power_cost - co2_cost - overheads - other_opex

    profit_proxy = float(disp["proxy_profit_eur"].sum())

    return {
        "total_mwh": total_mwh,
        "avg_price": avg_price,
        "total_tons": tons,
        "revenue_meoh": revenue_meoh,
        "power_cost": float(power_cost),
        "co2_cost": co2_cost,
        "overheads": overheads,
        "other_opex": other_opex,
        "ebitda_full": ebitda_full,
        "profit_proxy": profit_proxy,
        "break_even": break_even_eur_per_mwh,
    }
