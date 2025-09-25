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
    # NEW:
    prefer_self_supply: bool = True           # use battery to supply plant (esp. min load) when price < threshold
    dispatch_threshold_eur_per_mwh: Optional[float] = None  # pass the cap for smarter decisions


def simulate_price_band(df: pd.DataFrame, p: BatteryParams) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Legacy simple band strategy (kept for compatibility)."""
    if not p.enabled:
        return pd.DataFrame(), {"battery_enabled": False, "battery_profit_eur": 0.0}

    step_h = 0.25
    n = len(df)
    price = df["price_eur_per_mwh"].to_numpy()

    ch = np.zeros(n)
    dis = np.zeros(n)
    soc = np.zeros(n)
    e = 0.5 * p.e_mwh

    for t in range(n):
        if price[t] <= p.price_low - 1e-9:
            ch[t] = min(p.p_ch_mw, (p.soc_max * p.e_mwh - e) / step_h)
        elif price[t] >= p.price_high + 1e-9:
            dis[t] = min(p.p_dis_mw, (e - p.soc_min * p.e_mwh) / step_h)

        e += ch[t] * p.eff_ch * step_h
        e -= dis[t] / p.eff_dis * step_h
        e = min(max(e, p.soc_min * p.e_mwh), p.soc_max * p.e_mwh)
        soc[t] = e / p.e_mwh

    dfb = df[["timestamp", "price_eur_per_mwh"]].copy()
    dfb["bat_charge_mw"] = ch
    dfb["bat_discharge_mw"] = dis
    dfb["bat_soc"] = soc

    energy_ch = (ch * step_h).sum()
    energy_dis = (dis * step_h).sum()
    cost_energy = (ch * step_h * price).sum()
    revenue_energy = (dis * step_h * price).sum()
    degr = p.degradation_eur_per_mwh * (energy_ch + energy_dis)
    profit = revenue_energy - cost_energy - degr

    kpis = dict(
        battery_enabled=True,
        battery_trading_profit_eur=float(profit),
        battery_grid_cost_savings_eur=0.0,
        battery_profit_eur=float(profit),
        battery_energy_ch_mwh=float(energy_ch),
        battery_energy_dis_mwh=float(energy_dis),
        battery_degradation_eur=float(degr),
        battery_avg_soc=float(soc.mean()),
        battery_final_soc=float(soc[-1] if len(soc) else 0.0),
        strategy="band",
    )
    return dfb, kpis


def simulate_hybrid_self_supply(
    prices_df: pd.DataFrame,
    plant_df: pd.DataFrame,
    p: BatteryParams
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Smart hybrid strategy:
      1) If price < threshold (cap) and plant is running, DISCHARGE to supply plant load
         (prioritise min-load coverage), reducing grid imports.
      2) Else if price >= high band, discharge to grid (arbitrage).
      3) If price <= low band, charge from grid.
    Economics:
      - Savings from self-supply reduce grid purchases (not revenue).
      - Revenues from discharge-to-grid.
      - Costs from charging + degradation on all throughput.
    Requires plant_df to contain at least: ['timestamp','price_eur_per_mwh', 'mw' or 'dispatch_mw'].
    """
    if not p.enabled:
        return pd.DataFrame(), {
            "battery_enabled": False,
            "battery_profit_eur": 0.0,
            "battery_grid_cost_savings_eur": 0.0,
            "strategy": "hybrid_self_supply(disabled)"
        }

    # Inputs
    df = prices_df[["timestamp", "price_eur_per_mwh"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    dfp = plant_df.copy()
    dfp["timestamp"] = pd.to_datetime(dfp["timestamp"])
    df = df.merge(dfp, on="timestamp", how="left")

    # Figure dispatch column
    disp_col = "dispatch_mw" if "dispatch_mw" in df.columns else ("mw" if "mw" in df.columns else None)
    if disp_col is None:
        raise ValueError("Plant results missing 'dispatch_mw' or 'mw' column for battery hybrid simulation.")

    step_h = 0.25
    n = len(df)

    price = df["price_eur_per_mwh"].to_numpy()
    mw_plant = df[disp_col].fillna(0.0).to_numpy()

    # Infer min load (approx) from plant_df if present; else 0
    # If plant core exported a 'min_mw' per step, use that; else take min positive dispatch as a proxy.
    if "min_mw" in df.columns:
        min_mw = df["min_mw"].fillna(0.0).to_numpy()
    else:
        min_val = float(np.nanmin(mw_plant[mw_plant > 0])) if np.any(mw_plant > 0) else 0.0
        min_mw = np.full(n, min_val)

    threshold = p.dispatch_threshold_eur_per_mwh if p.dispatch_threshold_eur_per_mwh is not None else p.price_low

    # State arrays
    ch = np.zeros(n)
    dis_to_plant = np.zeros(n)
    dis_to_grid = np.zeros(n)
    soc = np.zeros(n)
    grid_import_mw = mw_plant.copy()  # will be reduced by self-supply
    action = np.full(n, "", dtype=object)

    e = 0.5 * p.e_mwh

    for t in range(n):
        # 1) SELF-SUPPLY if cheap (price below threshold) and plant is running
        if p.prefer_self_supply and price[t] < threshold - 1e-9 and mw_plant[t] > 0:
            # try to cover at least min load from battery
            target_ss = min(min_mw[t], mw_plant[t])  # lower bound to keep plant at min
            # maximum we can discharge this step given SoC and power limit
            max_dis = min(p.p_dis_mw, (e - p.soc_min * p.e_mwh) / step_h)
            ss = max(0.0, min(target_ss, max_dis))
            if ss > 0:
                dis_to_plant[t] = ss
                grid_import_mw[t] = max(0.0, mw_plant[t] - ss)
                e -= (ss / p.eff_dis) * step_h
                e = max(e, p.soc_min * p.e_mwh)
                action[t] = "self-supply"

        # 2) If high price, DISCHARGE to grid (after self-supply)
        # Only if power remains and SoC available
        max_dis_now = min(p.p_dis_mw - dis_to_plant[t], (e - p.soc_min * p.e_mwh) / step_h)
        if price[t] >= p.price_high + 1e-9 and max_dis_now > 0:
            dis_to_grid[t] = max_dis_now
            e -= (dis_to_grid[t] / p.eff_dis) * step_h
            e = max(e, p.soc_min * p.e_mwh)
            action[t] = (action[t] + "+") if action[t] else ""
            action[t] += "arb-discharge"

        # 3) If low price, CHARGE (if power and headroom available)
        max_ch = min(p.p_ch_mw, (p.soc_max * p.e_mwh - e) / step_h)
        if price[t] <= p.price_low - 1e-9 and max_ch > 0:
            ch[t] = max_ch
            e += ch[t] * p.eff_ch * step_h
            e = min(e, p.soc_max * p.e_mwh)
            action[t] = (action[t] + "+") if action[t] else ""
            action[t] += "charge"

        soc[t] = e / p.e_mwh

    # Economics
    energy_ch = (ch * step_h).sum()
    energy_dis_to_grid = (dis_to_grid * step_h).sum()
    energy_dis_to_plant = (dis_to_plant * step_h).sum()

    cost_charge = float((ch * step_h * price).sum())
    revenue_dis_grid = float((dis_to_grid * step_h * price).sum())

    # Grid cost savings from self-supply:
    savings = float((dis_to_plant * step_h * price).sum())

    degr = float(p.degradation_eur_per_mwh * (energy_ch + energy_dis_to_grid + energy_dis_to_plant))

    trading_profit = revenue_dis_grid - cost_charge - degr
    total_profit = trading_profit + savings

    out = prices_df[["timestamp", "price_eur_per_mwh"]].copy()
    out["bat_charge_mw"] = ch
    out["bat_discharge_mw_to_plant"] = dis_to_plant
    out["bat_discharge_mw_to_grid"] = dis_to_grid
    out["bat_soc"] = soc
    out["grid_import_mw_after_battery"] = grid_import_mw
    out["battery_action"] = action

    kpis = dict(
        battery_enabled=True,
        strategy="hybrid_self_supply",
        battery_energy_charge_mwh=float(energy_ch),
        battery_energy_discharge_to_plant_mwh=float(energy_dis_to_plant),
        battery_energy_discharge_to_grid_mwh=float(energy_dis_to_grid),
        battery_degradation_eur=degr,
        battery_trading_profit_eur=trading_profit,
        battery_grid_cost_savings_eur=savings,
        battery_profit_eur=total_profit,
        battery_avg_soc=float(soc.mean()),
        battery_final_soc=float(soc[-1] if len(soc) else 0.0),
    )
    return out, kpis
