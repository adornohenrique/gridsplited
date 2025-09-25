# core/battery.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import numpy as np
import pandas as pd


@dataclass
class BatteryParams:
    dt_hours: float = 0.25               # 15 min steps
    cap_mwh: float = 10.0               # energy capacity
    p_charge_mw: float = 5.0            # max charge power (grid -> battery)
    p_discharge_mw: float = 5.0         # max discharge power (battery -> grid)
    eta_charge: float = 0.95            # charging efficiency (fraction)
    eta_discharge: float = 0.95         # discharging efficiency (fraction)
    soc_init_frac: float = 0.5          # initial SoC as fraction of cap
    soc_min_frac: float = 0.05
    soc_max_frac: float = 0.95
    low_price_eur_per_mwh: float = 40.0 # charge when price <= low
    high_price_eur_per_mwh: float = 80.0# discharge when price >= high
    degr_cost_eur_per_mwh: float = 0.0  # degradation cost per MWh throughput
    enforce_final_soc: bool = False     # if True, end SoC == start SoC


def simulate_price_band(
    df_prices: pd.DataFrame,
    params: BatteryParams,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Greedy, stable strategy:
      - If price <= low  -> charge
      - If price >= high -> discharge
      - Else hold
    Respects power limits, energy capacity, efficiencies, SoC bounds.

    Conventions:
      * Positive action_mw = discharge to grid (sell)
      * Negative action_mw = charge from grid (buy)
    """
    ts = pd.to_datetime(df_prices["timestamp"])
    price = df_prices["price_eur_per_mwh"].astype(float).to_numpy()

    n = len(price)
    dt = float(params.dt_hours)

    soc = np.zeros(n, dtype=float)  # MWh
    soc_min = params.soc_min_frac * params.cap_mwh
    soc_max = params.soc_max_frac * params.cap_mwh
    soc0 = params.soc_init_frac * params.cap_mwh
    soc_prev = np.clip(soc0, soc_min, soc_max)

    action_mw = np.zeros(n, dtype=float)      # + discharge, - charge
    charge_mw = np.zeros(n, dtype=float)
    discharge_mw = np.zeros(n, dtype=float)

    cost_eur = np.zeros(n, dtype=float)       # buy energy
    revenue_eur = np.zeros(n, dtype=float)    # sell energy
    degr_eur = np.zeros(n, dtype=float)       # degradation on throughput (|charge|+|disch|)
    profit_eur = np.zeros(n, dtype=float)

    for i in range(n):
        p = price[i]

        # Plan action
        target_charge = 0.0
        target_discharge = 0.0

        if p <= params.low_price_eur_per_mwh:
            # Charge limited by power and headroom in SoC:
            # SoC increase = eta_charge * P_charge * dt <= soc_max - soc_prev
            max_by_soc = max(0.0, (soc_max - soc_prev) / (params.eta_charge * dt))
            target_charge = min(params.p_charge_mw, max_by_soc)
        elif p >= params.high_price_eur_per_mwh:
            # Discharge limited by power and energy available:
            # SoC decrease = (P_discharge / eta_discharge) * dt <= soc_prev - soc_min
            max_by_soc = max(0.0, (soc_prev - soc_min) * params.eta_discharge / dt)
            target_discharge = min(params.p_discharge_mw, max_by_soc)

        # Optionally reserve energy near the end to return to initial SoC
        if params.enforce_final_soc and i == n - 1:
            # force back to initial SoC (do nothing on last step)
            target_charge = 0.0
            target_discharge = 0.0

        # Apply
        charge = float(target_charge)
        discharge = float(target_discharge)
        delta_soc = params.eta_charge * charge * dt - (discharge / params.eta_discharge) * dt
        soc_now = np.clip(soc_prev + delta_soc, soc_min, soc_max)

        # Recompute if clipping changed the feasible action (rare edge)
        if soc_now in (soc_min, soc_max):
            # adjust actions to exactly land on boundary
            if delta_soc > 0 and soc_prev < soc_max:  # charging
                charge = max(0.0, (soc_max - soc_prev) / (params.eta_charge * dt))
                delta_soc = params.eta_charge * charge * dt
                discharge = 0.0
            elif delta_soc < 0 and soc_prev > soc_min:  # discharging
                discharge = max(0.0, (soc_prev - soc_min) * params.eta_discharge / dt)
                delta_soc = -(discharge / params.eta_discharge) * dt
                charge = 0.0
            soc_now = np.clip(soc_prev + delta_soc, soc_min, soc_max)

        # Economics (grid-facing energy)
        e_in_mwh  = charge * dt                      # from grid
        e_out_mwh = discharge * dt                   # to grid
        cost = p * e_in_mwh
        rev  = p * e_out_mwh
        throughput = e_in_mwh + e_out_mwh
        degr = params.degr_cost_eur_per_mwh * throughput
        profit = rev - cost - degr

        # Save step
        soc[i] = soc_now
        charge_mw[i] = charge
        discharge_mw[i] = discharge
        action_mw[i] = discharge - charge
        cost_eur[i] = cost
        revenue_eur[i] = rev
        degr_eur[i] = degr
        profit_eur[i] = profit

        soc_prev = soc_now

    results = pd.DataFrame({
        "timestamp": ts,
        "price_eur_per_mwh": price,
        "batt_action_mw": action_mw,       # +discharge, -charge
        "batt_soc_mwh": soc,
        "batt_charge_mw": charge_mw,
        "batt_discharge_mw": discharge_mw,
        "batt_cost_eur": cost_eur,
        "batt_revenue_eur": revenue_eur,
        "batt_degradation_eur": degr_eur,
        "batt_profit_eur": profit_eur,
    })

    kpis = {
        "batt_total_profit_eur": float(results["batt_profit_eur"].sum()),
        "batt_total_revenue_eur": float(results["batt_revenue_eur"].sum()),
        "batt_total_cost_eur": float(results["batt_cost_eur"].sum()),
        "batt_total_degradation_eur": float(results["batt_degradation_eur"].sum()),
        "batt_avg_soc_mwh": float(results["batt_soc_mwh"].mean()),
        "batt_final_soc_mwh": float(results["batt_soc_mwh"].iloc[-1]),
        "batt_initial_soc_mwh": float(soc0),
        "batt_energy_throughput_mwh": float((results["batt_charge_mw"] + results["batt_discharge_mw"]).sum() * params.dt_hours),
    }

    return results, kpis
