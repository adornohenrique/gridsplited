# core/optimizer.py
from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass
class BatteryCfg:
    e_mwh: float                 # Energy capacity (MWh)
    p_ch_mw: float               # Max charge power (MW)
    p_dis_mw: float              # Max discharge power (MW)
    eta_c: float = 0.95          # Charge efficiency
    eta_d: float = 0.95          # Discharge efficiency
    soc_min_frac: float = 0.10   # Min SoC (fraction of E)
    soc_max_frac: float = 0.90   # Max SoC (fraction of E)
    soc0_frac: float = 0.50      # Initial SoC (fraction of E)

def _require_price_col(df: pd.DataFrame, price_col: str | None) -> str:
    if price_col and price_col in df.columns:
        return price_col
    # auto-detect
    for c in ["price", "Price", "price_eur_mwh", "Price_EUR_MWh"]:
        if c in df.columns:
            return c
    raise ValueError("Price column not found. Expected one of: price, Price, price_eur_mwh, Price_EUR_MWh.")

def consumer_dispatch_with_battery(
    df_prices: pd.DataFrame,
    price_col: str,
    capacity_mw: float,                 # plant nominal consumption (MW)
    breakeven_eur_per_mwh: float,       # threshold
    must_run_frac: float,               # min load when price >= breakeven (e.g., 0.10)
    dt_hours: float,                    # e.g., 0.25 for 15-min slots
    battery: BatteryCfg | None,
    import_cap_mw: float | None,        # max grid import (MW); None = no cap
    charge_at_low_price: bool           # if True, also charge when price < breakeven
) -> pd.DataFrame:
    """
    Implements your flipped rule set for a *consumer* plant (electrolyzer/eMeOH):
      - If price < breakeven: run plant at 100% capacity (and optionally charge battery).
      - If price >= breakeven: run plant at must_run_frac * capacity and DISCHARGE battery
        to cover that load (never export; only offset grid import).
    """
    pcol = _require_price_col(df_prices, price_col)
    df = df_prices.copy()
    price = df[pcol].to_numpy(dtype=float)
    n = len(df)

    # Target plant load per rule
    plant_target_mw = np.where(price < breakeven_eur_per_mwh, capacity_mw, must_run_frac * capacity_mw)

    # Battery arrays / SoC
    bat_ch_mw   = np.zeros(n)
    bat_dis_mw  = np.zeros(n)
    bat_ch_mwh  = np.zeros(n)
    bat_dis_mwh = np.zeros(n)
    soc_mwh     = np.zeros(n)

    if battery is not None:
        E = battery.e_mwh
        Pch = battery.p_ch_mw
        Pds = battery.p_dis_mw
        etac = battery.eta_c
        etad = battery.eta_d
        soc_min = battery.soc_min_frac * E
        soc_max = battery.soc_max_frac * E
        soc = float(np.clip(battery.soc0_frac * E, soc_min, soc_max))
    else:
        soc = np.nan

    grid_import_mw = np.zeros(n)

    for t in range(n):
        p = price[t]
        load_mw = float(plant_target_mw[t])

        ch_mw = 0.0
        dis_mw = 0.0

        if battery is not None:
            room_mwh  = max(soc_max - soc, 0.0)
            avail_mwh = max(soc - soc_min, 0.0)

            if p < breakeven_eur_per_mwh:
                # Cheap power: full production. Optionally charge battery (no export; just extra import).
                if charge_at_low_price and room_mwh > 1e-12:
                    max_ch_mwh   = etac * Pch * dt_hours
                    allow_ch_mwh = min(max_ch_mwh, room_mwh)
                    ch_mw = (allow_ch_mwh / etac) / dt_hours if allow_ch_mwh > 0 else 0.0

                    # Respect import cap if present
                    if import_cap_mw is not None:
                        max_extra = max(import_cap_mw - load_mw, 0.0)
                        ch_mw = min(ch_mw, max_extra)

            else:
                # Expensive power: run at min load; DISCHARGE battery to cover as much of that load as possible
                if avail_mwh > 1e-12 and load_mw > 0:
                    max_dis_mwh   = Pds * dt_hours / etad
                    allow_dis_mwh = min(max_dis_mwh, avail_mwh)
                    dis_mw = min((allow_dis_mwh * etad) / dt_hours, load_mw)  # never export

        # Net grid import (no export allowed)
        gi_mw = load_mw + ch_mw - dis_mw
        if import_cap_mw is not None and gi_mw > import_cap_mw:
            # Trim charging first to hit the cap
            overflow = gi_mw - import_cap_mw
            reduce_ch = min(overflow, ch_mw)
            ch_mw -= reduce_ch
            gi_mw = load_mw + ch_mw - dis_mw
            if gi_mw > import_cap_mw + 1e-9:
                # Discharge only helps reduce import; no need to trim in normal conditions
                gi_mw = import_cap_mw

        grid_import_mw[t] = max(gi_mw, 0.0)

        # Commit battery energy + SoC
        bat_ch_mw[t]   = ch_mw
        bat_dis_mw[t]  = dis_mw
        bat_ch_mwh[t]  = ch_mw * dt_hours
        bat_dis_mwh[t] = dis_mw * dt_hours

        if battery is not None:
            soc = soc + (battery.eta_c * bat_ch_mwh[t]) - (bat_dis_mwh[t] / battery.eta_d)
            soc = float(np.clip(soc, soc_min, soc_max))
            soc_mwh[t] = soc
        else:
            soc_mwh[t] = np.nan

    # Energy + cost accounting
    mwh = plant_target_mw * dt_hours
    grid_import_mwh = grid_import_mw * dt_hours
    energy_cost_eur = price * grid_import_mwh
    batt_arb_eur    = price * (bat_dis_mwh - bat_ch_mwh)  # savings sign convention
    net_energy_cost_eur = energy_cost_eur  # what you pay to the grid

    # Build output
    df["dispatch_mw"]      = plant_target_mw
    df["mwh"]              = mwh
    df["bat_ch_mw"]        = bat_ch_mw
    df["bat_dis_mw"]       = bat_dis_mw
    df["bat_ch_mwh"]       = bat_ch_mwh
    df["bat_dis_mwh"]      = bat_dis_mwh
    df["soc_mwh"]          = soc_mwh
    df["grid_import_mw"]   = grid_import_mw
    df["grid_import_mwh"]  = grid_import_mwh
    df["energy_cost_eur"]  = energy_cost_eur
    df["batt_arb_eur"]     = batt_arb_eur
    df["net_energy_cost_eur"] = net_energy_cost_eur
    return df

# ---- Public entry point your app can call ----
def run_dispatch(
    df_prices: pd.DataFrame,
    price_col: str | None = None,
    capacity_mw: float = 200.0,
    breakeven_eur_per_mwh: float = 60.0,
    must_run_frac: float = 0.10,
    dt_hours: float = 0.25,  # 15 min
    battery_enabled: bool = True,
    battery_kwargs: dict | None = None,
    import_cap_mw: float | None = None,
    charge_at_low_price: bool = True,
) -> pd.DataFrame:
    """
    Thin wrapper the Streamlit page calls.
    """
    pcol = _require_price_col(df_prices, price_col)
    bat = None
    if battery_enabled:
        battery_kwargs = battery_kwargs or {}
        bat = BatteryCfg(**battery_kwargs)
    return consumer_dispatch_with_battery(
        df_prices=df_prices,
        price_col=pcol,
        capacity_mw=capacity_mw,
        breakeven_eur_per_mwh=breakeven_eur_per_mwh,
        must_run_frac=must_run_frac,
        dt_hours=dt_hours,
        battery=bat,
        import_cap_mw=import_cap_mw,
        charge_at_low_price=charge_at_low_price,
    )
