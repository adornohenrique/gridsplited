# core/portfolio.py
import pandas as pd
from typing import Dict, Any, List, Tuple
from .optimizer import run_dispatch
from .io import load_prices

def run_portfolio(
    files: List,  # list of UploadedFile objects
    base: Dict[str, Any],
) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:
    """
    Run the same parameters on multiple price files.
    Returns a summary DataFrame + list of per-file result DataFrames.
    """
    summaries = []
    results_list = []

    for f in files:
        df = load_prices(f)
        results, kpis = run_dispatch(
            df=df,
            plant_capacity_mw=base["plant_capacity_mw"],
            min_load_pct=base["min_load_pct"],
            max_load_pct=base["max_load_pct"],
            break_even_eur_per_mwh=base["break_even_eur_per_mwh"],
            ramp_limit_mw_per_step=base["ramp_limit_mw_per_step"],
            always_on=base["always_on"],
            dispatch_threshold_eur_per_mwh=base["dispatch_threshold_eur_per_mwh"],
            mwh_per_ton=base["mwh_per_ton"],
            methanol_price_eur_per_ton=base["methanol_price_eur_per_ton"],
            co2_price_eur_per_ton=base["co2_price_eur_per_ton"],
            co2_t_per_ton_meoh=base["co2_t_per_ton_meoh"],
            maintenance_pct_of_revenue=base["maintenance_pct_of_revenue"],
            sga_pct_of_revenue=base["sga_pct_of_revenue"],
            insurance_pct_of_revenue=base["insurance_pct_of_revenue"],
            target_margin_fraction=base["target_margin_fraction"],
            margin_method=base["margin_method"],
        )
        results_list.append(results.assign(source_file=f.name))
        summaries.append({
            "file": f.name,
            "total_true_profit_eur": kpis.get("total_true_profit_eur"),
            "total_energy_mwh": kpis.get("total_energy_mwh"),
            "total_tons": kpis.get("total_tons"),
            "weighted_avg_price_eur_per_mwh": kpis.get("weighted_avg_price_eur_per_mwh"),
        })

    return pd.DataFrame(summaries), results_list
