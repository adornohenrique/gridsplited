# core/optimizer.py
import os
from typing import Dict, Any, Tuple, Optional
import pandas as pd
from dispatch_core import optimize_dispatch
from .battery import BatteryParams, simulate_price_band

def run_dispatch(
    *,
    df: pd.DataFrame,
    plant_capacity_mw: float,
    min_load_pct: float,
    max_load_pct: float,
    break_even_eur_per_mwh: float,
    ramp_limit_mw_per_step: Optional[float],
    always_on: bool,
    dispatch_threshold_eur_per_mwh: float,
    mwh_per_ton: float,
    methanol_price_eur_per_ton: float,
    co2_price_eur_per_ton: float,
    co2_t_per_ton_meoh: float,
    maintenance_pct_of_revenue: float,
    sga_pct_of_revenue: float,
    insurance_pct_of_revenue: float,
    target_margin_fraction: float,
    margin_method: str,
    battery_params: Optional[BatteryParams] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame, Dict[str, Any]]:
    """
    Runs plant dispatch (core MILP inside dispatch_core.py) and, if battery enabled,
    runs battery band simulation alongside.
    Returns: (plant_results_df, plant_kpis, battery_df, battery_kpis)
    """
    tmp_csv = "/tmp/_prices.csv"
    df.to_csv(tmp_csv, index=False)
    out_xlsx = "/tmp/dispatch_output.xlsx"

    plant_results, plant_kpis = optimize_dispatch(
        input_csv=tmp_csv,
        output_xlsx=out_xlsx,
        plant_capacity_mw=plant_capacity_mw,
        min_load_pct=min_load_pct,
        max_load_pct=max_load_pct,
        break_even_eur_per_mwh=break_even_eur_per_mwh,
        ramp_limit_mw_per_step=ramp_limit_mw_per_step,
        always_on=always_on,
        dispatch_threshold_eur_per_mwh=dispatch_threshold_eur_per_mwh,
        mwh_per_ton=mwh_per_ton,
        methanol_price_eur_per_ton=methanol_price_eur_per_ton,
        co2_price_eur_per_ton=co2_price_eur_per_ton,
        co2_t_per_ton_meoh=co2_t_per_ton_meoh,
        maintenance_pct_of_revenue=maintenance_pct_of_revenue,
        sga_pct_of_revenue=sga_pct_of_revenue,
        insurance_pct_of_revenue=insurance_pct_of_revenue,
        target_margin_fraction=target_margin_fraction,
        margin_method=margin_method,
    )

    # Battery
    bat_df, bat_kpis = (pd.DataFrame(), {"battery_enabled": False})
    if battery_params and battery_params.enabled:
        bat_df, bat_kpis = simulate_price_band(df, battery_params)

    return plant_results, plant_kpis, bat_df, bat_kpis
