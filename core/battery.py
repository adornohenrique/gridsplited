# core/battery.py
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

@dataclass
class BatteryParams:
    enabled: bool = False
    e_mwh: float = 10.0
    p_ch_mw: float = 5.0
    p_dis_mw: float = 5.0
    eff_ch: float = 0.95
    eff_dis: float = 0.95
    soc_min: float = 0.10
    soc_max: float = 0.90
    price_low: float = 30.0
    price_high: float = 90.0
    degradation_eur_per_mwh: float = 0.0

def simulate_price_band(df: pd.DataFrame, p: BatteryParams) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Heuristic battery: band strategy."""
    if not p.enabled:
        return pd.DataFrame(), {"battery_enabled": False, "battery_profit_eur": 0.0}

    step_h = 0.25  # 15 minutes
    n = len(df)
    price = df["price_eur_per_mwh"].to_numpy()

    ch = np.zeros(n)
    dis = np.zeros(n)
    soc = np.zeros(n)
    e = 0.5 * p.e_mwh  # start half-full

    for t in range(n):
        if price[t] <= p.price_low - 1e-9:
            # charge
            ch[t] = min(p.p_ch_mw, (p.soc_max * p.e_mwh - e) / step_h)
        elif price[t] >= p.price_high + 1e-9:
            # discharge
            dis[t] = min(p.p_dis_mw, (e - p.soc_min * p.e_mwh) / step_h)
        # update energy
        e += ch[t] * p.eff_ch * step_h
        e -= dis[t] / p.eff_dis * step_h
        e = min(max(e, p.soc_min * p.e_mwh), p.soc_max * p.e_mwh)
        soc[t] = e / p.e_mwh

    dfb = df[["timestamp", "price_eur_per_mwh"]].copy()
    dfb["bat_charge_mw"] = ch
    dfb["bat_discharge_mw"] = dis
    dfb["bat_soc"] = soc

    # economics
    energy_ch = (ch * step_h).sum()  # MWh
    energy_dis = (dis * step_h).sum()
    cost_energy = (ch * step_h * price).sum()
    revenue_energy = (dis * step_h * price).sum()
    degr = p.degradation_eur_per_mwh * (energy_ch + energy_dis)
    profit = revenue_energy - cost_energy - degr

    kpis = dict(
        battery_enabled=True,
        battery_profit_eur=float(profit),
        battery_energy_ch_mwh=float(energy_ch),
        battery_energy_dis_mwh=float(energy_dis),
        battery_degradation_eur=float(degr),
        battery_avg_soc=float(soc.mean()),
        battery_final_soc=float(soc[-1] if len(soc) else 0.0),
    )
    return dfb, kpis
