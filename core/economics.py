# core/economics.py
from __future__ import annotations

import math
from typing import Any, Dict
import pandas as pd


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first matching column name (case-insensitive)."""
    for c in candidates:
        if c in df.columns:
            return c
    lowers = {c.lower(): c for c in df.columns}
    for c in candidates:
        lc = c.lower()
        if lc in lowers:
            return lowers[lc]
    return None


def compute_kpis(
    dispatch_df: pd.DataFrame,
    mwh_per_ton: float,
    meoh_price_eur_per_ton: float,
    co2_price_eur_per_ton: float,
    co2_t_per_ton_meoh: float,
    maint_pct: float = 0.0,           # % of revenue
    sga_pct: float = 0.0,             # % of revenue
    ins_pct: float = 0.0,             # % of revenue
    water_cost_eur_per_ton: float = 0.0,
    other_opex_eur_per_ton: float = 0.0,
    break_even_eur_per_mwh: float | None = None,
) -> Dict[str, Any]:
    """
    Compatible with the new dispatcher:
      expects at least a price column and one energy column.
      Prefers 'grid_import_mwh' for energy cost; falls back to 'mwh'.
    """
    if dispatch_df is None or len(dispatch_df) == 0:
        raise ValueError("compute_kpis: dispatch_df is empty.")

    df = dispatch_df

    price_col = _find_col(df, ["price", "Price", "price_eur_mwh", "Price_EUR_MWh"])
    if not price_col:
        raise KeyError("compute_kpis: price column not found (expected 'price' or similar).")

    # Plant energy per slot (MWh)
    # Your new dispatcher writes 'mwh' (plant load). If absent, try common alternates.
    mwh_col = _find_col(df, ["mwh", "MWh", "gen_mwh", "load_mwh"])
    if not mwh_col:
        raise KeyError("compute_kpis: No energy column found (expected 'mwh' or 'gen_mwh').")

    # What you pay the grid for (imports). Prefer 'grid_import_mwh'.
    grid_mwh_col = _find_col(df, ["grid_import_mwh", "import_mwh"])

    # Total energy consumption and imports
    total_mwh = float(df[mwh_col].sum())
    total_grid_mwh = float(df[grid_mwh_col].sum()) if grid_mwh_col else total_mwh

    # Energy cost: use precomputed column if present; else compute price * imports (or plant mwh)
    cost_col = _find_col(df, ["energy_cost_eur", "EnergyCostEUR"])
    if cost_col:
        energy_cost_series = df[cost_col]
    else:
        base_energy = df[grid_mwh_col] if grid_mwh_col else df[mwh_col]
        energy_cost_series = df[price_col] * base_energy

    total_energy_cost = float(energy_cost_series.sum())

    if mwh_per_ton <= 0:
        raise ValueError("compute_kpis: mwh_per_ton must be > 0.")
    tons_meoh = total_mwh / mwh_per_ton

    revenue = tons_meoh * meoh_price_eur_per_ton
    co2_cost = tons_meoh * co2_t_per_ton_meoh * co2_price_eur_per_ton
    pct_cost = revenue * ((maint_pct + sga_pct + ins_pct) / 100.0)
    var_costs = tons_meoh * (water_cost_eur_per_ton + other_opex_eur_per_ton)

    ebitda = revenue - total_energy_cost - co2_cost - pct_cost - var_costs
    ebitda_per_ton = ebitda / tons_meoh if tons_meoh > 0 else float("nan")
    avg_energy_cost_eur_per_mwh = total_energy_cost / total_grid_mwh if total_grid_mwh > 0 else float("nan")
    avg_allin_cost_per_ton = (
        (total_energy_cost + co2_cost + var_costs + pct_cost) / tons_meoh if tons_meoh > 0 else float("nan")
    )
    ebitda_margin = (ebitda / revenue) if revenue > 0 else float("nan")
    gross_margin = ((revenue - total_energy_cost) / revenue) if revenue > 0 else float("nan")

    # Return a simple dict (works with your report builder and generic UI)
    return {
        "Total MWh (plant load)": round(total_mwh, 3),
        "Grid MWh (imported)": round(total_grid_mwh, 3),
        "Methanol (t)": round(tons_meoh, 3),
        "Revenue (€)": round(revenue, 2),
        "Energy cost (€)": round(total_energy_cost, 2),
        "Avg energy cost (€/MWh)": None if math.isnan(avg_energy_cost_eur_per_mwh) else round(avg_energy_cost_eur_per_mwh, 2),
        "CO₂ cost (€)": round(co2_cost, 2),
        "Variable OPEX (€)": round(var_costs, 2),
        "Pct-based OPEX (€)": round(pct_cost, 2),
        "EBITDA (€)": round(ebitda, 2),
        "EBITDA per t (€/t)": None if math.isnan(ebitda_per_ton) else round(ebitda_per_ton, 2),
        "EBITDA margin": None if math.isnan(ebitda_margin) else round(ebitda_margin, 4),
        "All-in cost (€/t)": None if math.isnan(avg_allin_cost_per_ton) else round(avg_allin_cost_per_ton, 2),
        "Breakeven (€/MWh, input)": break_even_eur_per_mwh,
    }
