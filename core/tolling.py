# core/tolling.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np


@dataclass
class TollingParams:
    enabled: bool = False
    contracted_mw: float = 0.0                          # MW under tolling
    capacity_fee_eur_per_mw_month: float = 0.0          # €/MW-month received
    variable_fee_eur_per_mwh: float = 0.0               # €/MWh received when running
    other_var_cost_eur_per_mwh: float = 0.0             # extra €/MWh cost (e.g., reagents)
    maint_pct: float = 0.0                               # as fraction of variable toll revenue
    sga_pct: float = 0.0
    ins_pct: float = 0.0


def price_cap_tolling(
    target_margin_pct: float,
    variable_fee_eur_per_mwh: float,
    maint_pct: float,
    sga_pct: float,
    ins_pct: float,
    other_var_cost_eur_per_mwh: float = 0.0,
) -> float:
    """
    Tolling 'run' condition (€/MWh):
      price_cap = variable_fee * (1 - margin - (maint+sga+ins)) - other_var_cost_per_MWh
    Run when market price <= price_cap (since price is a cost).
    We keep the same shape as the rest of the app (dispatch threshold),
    so the app compares price >= threshold by flipping the sign below.
    """
    p = float(target_margin_pct) / 100.0
    o = float(maint_pct or 0) + float(sga_pct or 0) + float(ins_pct or 0)
    cap = variable_fee_eur_per_mwh * (1.0 - p - o) - float(other_var_cost_eur_per_mwh or 0.0)
    return max(0.0, cap)


def build_tolling_timeline_and_kpis(
    plant_results: pd.DataFrame,
    toll: TollingParams,
    contracted_mw_cap: float,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Inputs:
      plant_results: DataFrame with at least ['timestamp','energy_mwh','power_cost_eur'] (from dispatch_core)
      toll: TollingParams
      contracted_mw_cap: (usually toll.contracted_mw), bounded by plant capacity

    Returns:
      timeline_df: per-step tolling economics
      kpis: totals for capacity revenue, variable revenue, costs, and profit
    """
    if not toll.enabled or plant_results is None or plant_results.empty:
        return pd.DataFrame(), {
            "tolling_enabled": False,
            "tolling_total_profit_eur": 0.0,
        }

    df = plant_results.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Step length (hours)
    if len(df) >= 2:
        step_h = (df["timestamp"].iloc[1] - df["timestamp"].iloc[0]).total_seconds() / 3600.0
    else:
        step_h = 0.25  # fallback to 15 min

    total_hours = step_h * len(df)
    # Approx. months in data (pro-rated): 1 month = 30.4375 days average
    months = total_hours / (24.0 * 30.4375)

    # Capacity revenue pro-rated over the window
    contracted_mw = max(0.0, float(min(contracted_mw_cap, toll.contracted_mw)))
    cap_rev_total = contracted_mw * float(toll.capacity_fee_eur_per_mw_month) * months
    cap_rev_per_step = cap_rev_total / len(df) if len(df) else 0.0

    # Variable toll revenue: €/MWh * MWh dispatched
    energy_mwh = df.get("energy_mwh", pd.Series(np.zeros(len(df))))
    price_eur_mwh = df.get("price_eur_per_mwh", pd.Series(np.zeros(len(df))))
    power_cost_eur = df.get("power_cost_eur", price_eur_mwh * energy_mwh)

    var_rev_eur = float(toll.variable_fee_eur_per_mwh) * energy_mwh
    other_var_cost_eur = float(toll.other_var_cost_eur_per_mwh or 0.0) * energy_mwh

    # % costs on variable revenue
    pct_cost_eur = var_rev_eur * (float(toll.maint_pct or 0) + float(toll.sga_pct or 0) + float(toll.ins_pct or 0))

    # Profit per step
    profit_step = cap_rev_per_step + var_rev_eur - power_cost_eur - other_var_cost_eur - pct_cost_eur

    timeline = pd.DataFrame({
        "timestamp": df["timestamp"],
        "toll_capacity_revenue_eur": np.full(len(df), cap_rev_per_step),
        "toll_variable_revenue_eur": var_rev_eur,
        "toll_power_cost_eur": power_cost_eur,
        "toll_other_var_cost_eur": other_var_cost_eur,
        "toll_pct_costs_eur": pct_cost_eur,
        "toll_profit_eur": profit_step,
        "energy_mwh": energy_mwh,
        "price_eur_per_mwh": price_eur_mwh,
    })

    kpis = {
        "tolling_enabled": True,
        "tolling_capacity_mw": contracted_mw,
        "tolling_capacity_fee_eur_per_mw_month": float(toll.capacity_fee_eur_per_mw_month),
        "tolling_variable_fee_eur_per_mwh": float(toll.variable_fee_eur_per_mwh),
        "tolling_other_var_cost_eur_per_mwh": float(toll.other_var_cost_eur_per_mwh),
        "tolling_maint_pct": float(toll.maint_pct or 0),
        "tolling_sga_pct": float(toll.sga_pct or 0),
        "tolling_ins_pct": float(toll.ins_pct or 0),
        "tolling_capacity_revenue_total_eur": float(cap_rev_total),
        "tolling_variable_revenue_total_eur": float(var_rev_eur.sum()),
        "tolling_power_cost_total_eur": float(power_cost_eur.sum()),
        "tolling_other_var_cost_total_eur": float(other_var_cost_eur.sum()),
        "tolling_pct_costs_total_eur": float(pct_cost_eur.sum()),
        "tolling_total_profit_eur": float(profit_step.sum()),
    }
    return timeline, kpis
