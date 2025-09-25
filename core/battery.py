# core/battery.py
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
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

    # NEW: hybrid controls
    use_for_min_load: bool = True
    price_threshold_eur_per_mwh: Optional[float] = None  # pass the dispatch price cap used by the plant


def simulate_price_band(df: pd.DataFrame, p: BatteryParams) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Legacy band-only (kept for compatibility)."""
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
    dfb["bat_mode"] = np.where(dis > 0, "arbitrage_dis",
                        np.where(ch > 0, "arbitrage_ch", "idle"))

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


def simulate_hybrid_support_minload(
    plant_df: pd.DataFrame,
    *,
    p: BatteryParams,
    min_mw: float,
    price_threshold_eur_per_mwh: Optional[float],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Hybrid battery:
      1) If price < threshold and plant is at (or near) min load, DISCHARGE to cover min-load consumption (reduce grid draw).
      2) Otherwise run classic price-band arbitrage.

    Inputs:
      plant_df requires columns:
        - 'timestamp'
        - 'price_eur_per_mwh'
        - 'dispatch_mw' or 'mw' (plant power)
      min_mw: numeric (constant min load in MW)
    """
    if not p.enabled:
        return pd.DataFrame(), {"battery_enabled": False, "battery_profit_eur": 0.0}

    df = plant_df.copy()
    if "dispatch_mw" in df.columns:
        mw_col = "dispatch_mw"
    elif "mw" in df.columns:
        mw_col = "mw"
    else:
        raise ValueError("plant_df must contain 'dispatch_mw' or 'mw' column.")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    price = df["price_eur_per_mwh"].to_numpy()
    mw = df[mw_col].to_numpy()
    n = len(df)
    step_h = 0.25

    thresh = price_threshold_eur_per_mwh if (price_threshold_eur_per_mwh is not None) else p.price_low

    ch = np.zeros(n)
    dis = np.zeros(n)
    soc = np.zeros(n)
    mode = np.array(["idle"] * n, dtype=object)

    e = 0.5 * p.e_mwh  # start half-full

    for t in range(n):
        # 1) Support min-load if price below threshold and plant is near min load
        did_support = False
        if p.use_for_min_load and price[t] < thresh - 1e-9 and mw[t] > 0.0:
            # heuristically consider "near min" within ±2% absolute of min_mw
            if mw[t] <= max(min_mw * 1.02, min_mw + 0.01):
                desire = min(mw[t], min_mw)  # MW we'd like to cover from battery
                max_dis_by_energy = (e - p.soc_min * p.e_mwh) / step_h
                dis_support = max(0.0, min(p.p_dis_mw, desire, max_dis_by_energy))
                if dis_support > 0:
                    dis[t] = dis_support
                    did_support = True
                    mode[t] = "support_min"

        # 2) If not supporting min-load this step, use band strategy
        if not did_support:
            # discharge high
            if price[t] >= p.price_high + 1e-9:
                max_dis_by_energy = (e - p.soc_min * p.e_mwh) / step_h
                dis[t] = max(0.0, min(p.p_dis_mw, max_dis_by_energy))
                if dis[t] > 0:
                    mode[t] = "arbitrage_dis"
            # charge low
            elif price[t] <= p.price_low - 1e-9:
                max_ch_by_space = (p.soc_max * p.e_mwh - e) / step_h
                ch[t] = max(0.0, min(p.p_ch_mw, max_ch_by_space))
                if ch[t] > 0:
                    mode[t] = "arbitrage_ch"
            # else idle (mode already 'idle')

        # Update SoE
        e += ch[t] * p.eff_ch * step_h
        e -= dis[t] / p.eff_dis * step_h
        e = min(max(e, p.soc_min * p.e_mwh), p.soc_max * p.e_mwh)
        soc[t] = e / p.e_mwh

    out = df[["timestamp", "price_eur_per_mwh"]].copy()
    out["plant_mw"] = mw
    out["bat_charge_mw"] = ch
    out["bat_discharge_mw"] = dis
    out["bat_soc"] = soc
    out["bat_mode"] = mode

    # Economics
    energy_ch = (ch * step_h).sum()
    energy_dis = (dis * step_h).sum()

    # Charging is a cost at price[t]
    cost_energy = float((ch * step_h * price).sum())
    # Discharging offsets grid purchases or sells energy — value at price[t]
    revenue_energy = float((dis * step_h * price).sum())

    # Count how much discharge went to min-load support
    support_mask = (mode == "support_min").astype(float)
    energy_dis_support = float((dis * step_h * support_mask).sum())

    degr = float(p.degradation_eur_per_mwh) * float(energy_ch + energy_dis)
    profit = revenue_energy - cost_energy - degr

    kpis = dict(
        battery_enabled=True,
        battery_profit_eur=float(profit),
        battery_energy_ch_mwh=float(energy_ch),
        battery_energy_dis_mwh=float(energy_dis),
        battery_energy_dis_support_min_mwh=float(energy_dis_support),
        battery_degradation_eur=float(degr),
        battery_avg_soc=float(np.mean(soc) if len(soc) else 0.0),
        battery_final_soc=float(soc[-1] if len(soc) else 0.0),
    )
    return out, kpis
