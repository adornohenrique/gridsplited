# core/optimizer.py
import numpy as np
import pandas as pd

def run_dispatch_with_battery(
    df: pd.DataFrame,
    # Plant
    plant_capacity_mw: float,
    min_load_pct: float,
    max_load_pct: float,
    break_even_eur_per_mwh: float,
    ramp_limit_mw_per_step: float | None,
    always_on: bool,
    dispatch_threshold_eur_per_mwh: float,
    mwh_per_ton: float | None,
    methanol_price_eur_per_ton: float,
    co2_price_eur_per_ton: float,
    co2_t_per_ton_meoh: float,
    maintenance_pct_of_revenue: float,
    sga_pct_of_revenue: float,
    insurance_pct_of_revenue: float,
    target_margin_fraction: float,
    margin_method: str,
    # Battery
    batt_energy_mwh: float,
    batt_power_mw: float,
    eff_chg: float,
    eff_dis: float,
    soc_init_pct: float,
    soc_min_pct: float,
    soc_max_pct: float,
    deadband_frac: float = 0.05,   # hysteresis around price cap
):
    """
    Profit-max plant with a simple battery policy:
    - Base plant dispatch: run at max when price <= price_cap, else min/0.
    - Battery:
        * Discharge when price >= (1+deadband)*price_cap to replace expensive grid energy
          (especially to meet min load when ALWAYS_ON).
        * Charge when price <= (1-deadband)*price_cap to store cheap energy.
    - Battery power and SOC (MWh) constraints respected. Efficiencies applied to SOC updates.
    - Costs are computed on actual grid draw = dispatch_mw +/- battery power.
    """

    df = df.copy().sort_values("timestamp").reset_index(drop=True)
    dt_h = 0.25  # 15-min steps

    # Plant bounds
    min_mw = (min_load_pct / 100.0) * plant_capacity_mw
    max_mw = (max_load_pct / 100.0) * plant_capacity_mw

    # Base target dispatch rule
    def target_mw(price):
        if price <= dispatch_threshold_eur_per_mwh:
            return max_mw
        else:
            return min_mw if always_on else 0.0

    df["target_mw"] = df["price_eur_per_mwh"].apply(target_mw)

    # Apply ramp limit (optional)
    dispatch = []
    prev = min_mw if always_on else 0.0
    for mw in df["target_mw"].to_numpy():
        if ramp_limit_mw_per_step is not None and ramp_limit_mw_per_step > 0:
            upper = prev + ramp_limit_mw_per_step
            lower = prev - ramp_limit_mw_per_step
            mw = max(lower, min(upper, mw))
        mw = max(min_mw if always_on else 0.0, min(mw, max_mw))
        dispatch.append(mw)
        prev = mw
    df["dispatch_mw"] = np.array(dispatch, dtype=float)

    # ---- Battery policy ----
    price = df["price_eur_per_mwh"].to_numpy(dtype=float)
    base_grid_mw = df["dispatch_mw"].to_numpy(dtype=float)

    cap_mwh   = float(batt_energy_mwh)
    p_max     = float(batt_power_mw)
    soc_min   = cap_mwh * float(soc_min_pct) / 100.0
    soc_max   = cap_mwh * float(soc_max_pct) / 100.0
    soc_init  = np.clip(cap_mwh * float(soc_init_pct) / 100.0, soc_min, soc_max)

    price_cap = float(dispatch_threshold_eur_per_mwh)
    band_low  = price_cap * (1.0 - float(deadband_frac))
    band_high = price_cap * (1.0 + float(deadband_frac))

    # Arrays
    n = len(df)
    charge_mw = np.zeros(n, dtype=float)
    discharge_mw = np.zeros(n, dtype=float)
    soc = np.zeros(n+1, dtype=float)
    soc[0] = soc_init

    for t in range(n):
        p = price[t]
        load_mw = base_grid_mw[t]  # plant electricity needed

        # Try discharge when expensive (>= band_high) to avoid grid purchases.
        if p >= band_high and load_mw > 0:
            # Maximum discharge power limited by battery & by load
            max_dis_by_power = min(p_max, load_mw)
            max_dis_by_energy = max(0.0, (soc[t] - soc_min)) * eff_dis / dt_h  # convert SOC headroom to MW
            d_mw = max(0.0, min(max_dis_by_power, max_dis_by_energy))
            discharge_mw[t] = d_mw
            # SOC update (energy leaving the battery divided by efficiency)
            soc[t+1] = soc[t] - (d_mw * dt_h) / eff_dis

        # Try charge when cheap (<= band_low)
        elif p <= band_low:
            max_chg_by_power = p_max
            max_chg_by_energy = max(0.0, (soc_max - soc[t])) / (eff_chg * dt_h)  # convert SOC room to MW
            c_mw = max(0.0, min(max_chg_by_power, max_chg_by_energy))
            charge_mw[t] = c_mw
            # SOC update (energy entering the battery times efficiency)
            soc[t+1] = soc[t] + (c_mw * dt_h) * eff_chg

        else:
            # Hold
            soc[t+1] = soc[t]

    # Final grid power = plant load + charge - discharge
    grid_mw = base_grid_mw + charge_mw - discharge_mw
    grid_mw = np.maximum(0.0, grid_mw)  # no export modeled

    # Energies
    energy_mwh = df["dispatch_mw"].to_numpy() * dt_h
    energy_grid_mwh = grid_mw * dt_h

    # Costs & production
    power_cost_baseline = (base_grid_mw * dt_h * price).sum()
    power_cost_actual   = (grid_mw * dt_h * price).sum()

    if mwh_per_ton and mwh_per_ton > 0:
        tons = energy_mwh / float(mwh_per_ton)
    else:
        tons = np.zeros(n, dtype=float)

    revenue = (tons * float(methanol_price_eur_per_ton)).sum()
    co2_cost = (tons * float(co2_price_eur_per_ton) * float(co2_t_per_ton_meoh)).sum()

    other_pct = float(maintenance_pct_of_revenue or 0) + float(sga_pct_of_revenue or 0) + float(insurance_pct_of_revenue or 0)
    other_costs = revenue * other_pct

    true_profit = revenue - power_cost_actual - co2_cost - other_costs

    # KPIs
    total_energy = float(energy_mwh.sum())
    wavp = float((price * energy_grid_mwh).sum() / max(1e-9, energy_grid_mwh.sum()))
    savings_eur = float(power_cost_baseline - power_cost_actual)

    kpis = {
        "total_energy_mwh": total_energy,
        "weighted_avg_grid_price_eur_per_mwh": wavp,
        "total_power_cost_eur": float(power_cost_actual),
        "total_power_cost_baseline_eur": float(power_cost_baseline),
        "battery_savings_eur": savings_eur,
        "total_tons": float(tons.sum()),
        "total_methanol_revenue_eur": float(revenue),
        "total_co2_cost_eur": float(co2_cost),
        "total_opex_misc_eur": float(other_costs),
        "total_true_profit_eur": float(true_profit),
        "dispatch_threshold_eur_per_mwh": float(dispatch_threshold_eur_per_mwh),
        "target_margin_fraction": float(target_margin_fraction),
        "margin_method": str(margin_method),
        "battery_cycles_equiv": float((charge_mw.sum() * dt_h) / max(1e-9, batt_energy_mwh)),  # rough measure
        "battery_hours_charging": float((charge_mw > 0).sum() * dt_h),
        "battery_hours_discharging": float((discharge_mw > 0).sum() * dt_h),
        "soc_final_mwh": float(soc[-1]),
    }

    results = pd.DataFrame({
        "timestamp": df["timestamp"],
        "price_eur_per_mwh": price,
        "dispatch_mw": df["dispatch_mw"],
        "energy_mwh": energy_mwh,
        "grid_mw": grid_mw,
        "grid_energy_mwh": energy_grid_mwh,
        "charge_mw": charge_mw,
        "discharge_mw": discharge_mw,
        "soc_mwh": soc[1:],  # align to end-of-interval SOC
        "power_cost_eur": energy_grid_mwh * price,
        "tons": tons,
        "revenue_eur": tons * float(methanol_price_eur_per_ton),
        "co2_cost_eur": tons * float(co2_price_eur_per_ton) * float(co2_t_per_ton_meoh),
    })

    # Also add a plain guidance string
    kpis["battery_guidance"] = (
        f"Charge when price ≤ {band_low:,.2f} €/MWh; "
        f"Discharge when price ≥ {band_high:,.2f} €/MWh "
        f"(deadband {deadband_frac*100:.1f}%)."
    )

    return results, kpis
