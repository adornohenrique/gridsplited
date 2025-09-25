# dispatch_core.py
"""
Simple quarter-hour dispatch optimizer.

Rule-based optimizer:
- Decide dispatch MW each 15-min step using a price threshold.
- Enforce min/max load and (optional) ramp limits.
- If `always_on=True`, the plant never goes below min load.
- Costs/revenue:
    * Power cost = price * MWh
    * If mwh_per_ton is provided, production tons = MWh / mwh_per_ton
      - Revenue = tons * methanol_price
      - CO2 cost = tons * co2_t_per_ton_meoh * co2_price
      - Maintenance/SG&A/Insurance = % of revenue
    * Profit (true) = revenue - power - CO2 - other % costs
    * Profit (proxy) = (price - break-even) * MWh  (for power-only view)

Returns:
- results: pd.DataFrame with row-by-row dispatch and economics
- kpis: dict with useful totals
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict, Any

import math
import pandas as pd
import numpy as np


def _read_input_prices(input_csv: str) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    # Normalize column names
    cols_map = {str(c).strip().lower(): c for c in df.columns}
    ts = cols_map.get("timestamp", None)
    pr = cols_map.get("price_eur_per_mwh", None)
    if ts is None or pr is None:
        raise ValueError(
            "Input CSV must have columns: 'timestamp', 'price_eur_per_mwh'. "
            f"Columns found: {list(df.columns)}"
        )
    out = df[[ts, pr]].copy()
    out.columns = ["timestamp", "price_eur_per_mwh"]
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out = out.dropna(subset=["timestamp", "price_eur_per_mwh"]).reset_index(drop=True)
    out = out.sort_values("timestamp")
    return out


def _apply_ramp(prev_mw: float, target_mw: float, ramp_limit: Optional[float]) -> float:
    if ramp_limit is None or ramp_limit <= 0:
        return target_mw
    delta = target_mw - prev_mw
    if delta > ramp_limit:
        return prev_mw + ramp_limit
    if delta < -ramp_limit:
        return prev_mw - ramp_limit
    return target_mw


def _dispatch_series(
    prices: pd.Series,
    min_mw: float,
    max_mw: float,
    break_even: float,
    threshold: float,
    always_on: bool,
    ramp_limit: Optional[float],
) -> np.ndarray:
    """
    Very simple rule:
      - Above price >= max(break_even, threshold) => run at max_mw
      - Else => baseline where baseline = min_mw if always_on else 0
    Then apply ramp limits step to step.
    """
    baseline = min_mw if always_on else 0.0
    trigger = max(float(break_even), float(threshold))
    p = prices.to_numpy(dtype=float)

    target = np.where(p >= trigger, max_mw, baseline)

    # Enforce ramp limits sequentially
    dispatch = np.empty_like(target, dtype=float)
    if len(target) == 0:
        return dispatch

    dispatch[0] = target[0]
    if ramp_limit is None or ramp_limit <= 0:
        return target

    for i in range(1, len(target)):
        dispatch[i] = _apply_ramp(dispatch[i - 1], target[i], ramp_limit)

        # keep inside [baseline (if always_on) or 0, max_mw] and >= min when "on"
        dispatch[i] = min(dispatch[i], max_mw)
        if always_on:
            dispatch[i] = max(dispatch[i], min_mw)
        else:
            dispatch[i] = max(dispatch[i], 0.0)

    return dispatch


def optimize_dispatch(
    *,
    input_csv: str,
    output_xlsx: str,
    plant_capacity_mw: float,
    min_load_pct: float,
    max_load_pct: float,
    break_even_eur_per_mwh: float,
    ramp_limit_mw_per_step: Optional[float],
    always_on: bool,
    dispatch_threshold_eur_per_mwh: float,
    # Economics (optional for "full-econ" margin mode)
    mwh_per_ton: Optional[float] = None,
    methanol_price_eur_per_ton: float = 0.0,
    co2_price_eur_per_ton: float = 0.0,
    co2_t_per_ton_meoh: float = 0.0,
    maintenance_pct_of_revenue: float = 0.0,
    sga_pct_of_revenue: float = 0.0,
    insurance_pct_of_revenue: float = 0.0,
    # Info-only, saved into KPIs
    target_margin_fraction: float = 0.0,
    margin_method: str = "power-only",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Main entry called by the UI. Returns (results_df, kpis_dict).
    Also writes an Excel to output_xlsx.
    """
    # 1) Read prices
    df = _read_input_prices(input_csv)  # columns: timestamp, price_eur_per_mwh

    # 2) Limits in MW
    plant_capacity_mw = float(plant_capacity_mw)
    min_mw = float(plant_capacity_mw) * float(min_load_pct)
    max_mw = float(plant_capacity_mw) * float(max_load_pct)

    # Safety
    min_mw = max(0.0, min(min_mw, plant_capacity_mw))
    max_mw = max(min_mw, min(max_mw, plant_capacity_mw))

    # 3) Dispatch
    dispatch_mw = _dispatch_series(
        prices=df["price_eur_per_mwh"],
        min_mw=min_mw,
        max_mw=max_mw,
        break_even=float(break_even_eur_per_mwh),
        threshold=float(dispatch_threshold_eur_per_mwh),
        always_on=bool(always_on),
        ramp_limit=ramp_limit_mw_per_step,
    )

    # 4) Energy per 15-min slot (MWh)
    step_hours = 0.25
    energy_mwh = dispatch_mw * step_hours

    # 5) Economics
    price = df["price_eur_per_mwh"].to_numpy(dtype=float)
    power_cost_eur = energy_mwh * price

    # Production-based metrics (optional)
    tons = None
    revenue_eur = None
    co2_cost_eur = None
    maint_eur = None
    sga_eur = None
    ins_eur = None
    other_pct_sum = float(maintenance_pct_of_revenue or 0) + float(sga_pct_of_revenue or 0) + float(insurance_pct_of_revenue or 0)

    if mwh_per_ton and mwh_per_ton > 0:
        tons = energy_mwh / float(mwh_per_ton)
        revenue_eur = tons * float(methanol_price_eur_per_ton)
        co2_cost_eur = tons * float(co2_t_per_ton_meoh) * float(co2_price_eur_per_ton)
        maint_eur = revenue_eur * float(maintenance_pct_of_revenue or 0)
        sga_eur = revenue_eur * float(sga_pct_of_revenue or 0)
        ins_eur = revenue_eur * float(insurance_pct_of_revenue or 0)
        other_pct_costs_eur = maint_eur + sga_eur + ins_eur
        true_profit_eur = revenue_eur - power_cost_eur - co2_cost_eur - other_pct_costs_eur
    else:
        # If no production model is given, we don't compute true profit.
        tons = np.zeros_like(energy_mwh)
        revenue_eur = np.zeros_like(energy_mwh)
        co2_cost_eur = np.zeros_like(energy_mwh)
        maint_eur = np.zeros_like(energy_mwh)
        sga_eur = np.zeros_like(energy_mwh)
        ins_eur = np.zeros_like(energy_mwh)
        true_profit_eur = np.zeros_like(energy_mwh)

    # Profit proxy vs break-even (useful even in power-only mode)
    proxy_profit_eur = (price - float(break_even_eur_per_mwh)) * energy_mwh

    # 6) Assemble results dataframe
    results = pd.DataFrame(
        {
            "timestamp": df["timestamp"].values,
            "price_eur_per_mwh": price,
            "dispatch_mw": dispatch_mw,
            "energy_mwh": energy_mwh,
            "tons": tons,
            "revenue_eur": revenue_eur,
            "power_cost_eur": power_cost_eur,
            "co2_cost_eur": co2_cost_eur,
            "maint_cost_eur": maint_eur,
            "sga_cost_eur": sga_eur,
            "insurance_cost_eur": ins_eur,
            "true_profit_eur": true_profit_eur,
            "profit_proxy_eur": proxy_profit_eur,
        }
    )

    # 7) KPIs
    total_energy = float(results["energy_mwh"].sum())
    weighted_avg_price = (
        float((results["price_eur_per_mwh"] * results["energy_mwh"]).sum()) / total_energy
        if total_energy > 0
        else float(np.nan)
    )

    kpis: Dict[str, Any] = {
        # Inputs echoed
        "plant_capacity_mw": plant_capacity_mw,
        "min_load_pct": float(min_load_pct),
        "max_load_pct": float(max_load_pct),
        "break_even_eur_per_mwh": float(break_even_eur_per_mwh),
        "ramp_limit_mw_per_step": float(ramp_limit_mw_per_step or 0.0),
        "always_on": bool(always_on),
        "dispatch_threshold_eur_per_mwh": float(dispatch_threshold_eur_per_mwh),
        "mwh_per_ton": float(mwh_per_ton or 0.0),
        "methanol_price_eur_per_ton": float(methanol_price_eur_per_ton),
        "co2_price_eur_per_ton": float(co2_price_eur_per_ton),
        "co2_t_per_ton_meoh": float(co2_t_per_ton_meoh),
        "maintenance_pct_of_revenue": float(maintenance_pct_of_revenue or 0),
        "sga_pct_of_revenue": float(sga_pct_of_revenue or 0),
        "insurance_pct_of_revenue": float(insurance_pct_of_revenue or 0),
        "target_margin_fraction": float(target_margin_fraction or 0.0),
        "margin_method": str(margin_method or "power-only"),
        # Aggregates
        "total_energy_mwh": total_energy,
        "weighted_avg_price_eur_per_mwh": weighted_avg_price,
        "total_power_cost_eur": float(results["power_cost_eur"].sum()),
        "total_tons": float(results["tons"].sum()) if mwh_per_ton and mwh_per_ton > 0 else None,
        "total_methanol_revenue_eur": float(results["revenue_eur"].sum()) if mwh_per_ton and mwh_per_ton > 0 else None,
        "total_co2_cost_eur": float(results["co2_cost_eur"].sum()) if mwh_per_ton and mwh_per_ton > 0 else None,
        "total_opex_misc_eur": float(results["maint_cost_eur"].sum() + results["sga_cost_eur"].sum() + results["insurance_cost_eur"].sum())
        if mwh_per_ton and mwh_per_ton > 0
        else 0.0,
        "total_true_profit_eur": float(results["true_profit_eur"].sum()) if mwh_per_ton and mwh_per_ton > 0 else None,
        "total_profit_proxy_eur": float(results["profit_proxy_eur"].sum()),
    }

    # 8) Write Excel
    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        results.to_excel(writer, index=False, sheet_name="dispatch")
        # KPIs sheet
        kpi_df = pd.DataFrame({"metric": list(kpis.keys()), "value": list(kpis.values())})
        kpi_df.to_excel(writer, index=False, sheet_name="kpis")

    return results, kpis
