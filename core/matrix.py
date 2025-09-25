# core/matrix.py
import numpy as np
import pandas as pd
from typing import Dict, Any, Iterable, Tuple
from .optimizer import run_dispatch

def _as_range(start: float, stop: float, step: float) -> Iterable[float]:
    if step == 0:
        return [start]
    n = int(np.floor((stop - start) / step)) + 1
    return [round(start + i * step, 10) for i in range(max(n, 1))]

def run_param_matrix(
    df: pd.DataFrame,
    base: Dict[str, Any],
    x_param: str, x_range: Tuple[float,float,float],
    y_param: str, y_range: Tuple[float,float,float],
) -> pd.DataFrame:
    """
    Sweep 2 parameters and compute a KPI grid (profit by default).
    Returns a long DataFrame with columns: x_param, y_param, kpi
    """
    xs = _as_range(*x_range)
    ys = _as_range(*y_range)
    out = []

    for xv in xs:
        for yv in ys:
            p = dict(base)
            p[x_param] = xv
            p[y_param] = yv
            results, kpis = run_dispatch(
                df=df,
                plant_capacity_mw=p["plant_capacity_mw"],
                min_load_pct=p["min_load_pct"],
                max_load_pct=p["max_load_pct"],
                break_even_eur_per_mwh=p["break_even_eur_per_mwh"],
                ramp_limit_mw_per_step=p["ramp_limit_mw_per_step"],
                always_on=p["always_on"],
                dispatch_threshold_eur_per_mwh=p["dispatch_threshold_eur_per_mwh"],
                mwh_per_ton=p["mwh_per_ton"],
                methanol_price_eur_per_ton=p["methanol_price_eur_per_ton"],
                co2_price_eur_per_ton=p["co2_price_eur_per_ton"],
                co2_t_per_ton_meoh=p["co2_t_per_ton_meoh"],
                maintenance_pct_of_revenue=p["maintenance_pct_of_revenue"],
                sga_pct_of_revenue=p["sga_pct_of_revenue"],
                insurance_pct_of_revenue=p["insurance_pct_of_revenue"],
                target_margin_fraction=p["target_margin_fraction"],
                margin_method=p["margin_method"],
            )
            out.append({x_param: xv, y_param: yv, "total_true_profit_eur": kpis.get("total_true_profit_eur", None)})

    return pd.DataFrame(out)
