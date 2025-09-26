# core/battery.py
from __future__ import annotations
import numpy as np
import pandas as pd

DT_HOURS = 0.25

def run_battery_strategy(
    df_prices: pd.DataFrame,
    e_mwh: float,
    p_ch_mw: float,
    p_dis_mw: float,
    eff_ch: float,
    eff_dis: float,
    soc_min: float,
    soc_max: float,
    price_low: float,
    price_high: float,
    degradation_eur_per_mwh: float = 0.0,
    soc0: float | None = None,
) -> pd.DataFrame:
    ts = df_prices["timestamp"].to_numpy()
    price = df_prices["price"].to_numpy(dtype=float)

    soc = np.empty_like(price, dtype=float)  # MWh
    ch  = np.zeros_like(price, dtype=float)  # MW (+grid->batt)
    dis = np.zeros_like(price, dtype=float)  # MW (+batt->grid)

    e_lo = e_mwh * soc_min
    e_hi = e_mwh * soc_max
    e = e_lo if soc0 is None else np.clip(soc0 * e_mwh, e_lo, e_hi)

    for i in range(price.shape[0]):
        if price[i] <= price_low and e < e_hi:  # charge
            ch[i] = min(p_ch_mw, (e_hi - e) / (eff_ch * DT_HOURS))
            e += ch[i] * eff_ch * DT_HOURS
            dis[i] = 0.0
        elif price[i] >= price_high and e > e_lo:  # discharge
            dis[i] = min(p_dis_mw, (e - e_lo) * eff_dis / DT_HOURS)
            e -= (dis[i] / eff_dis) * DT_HOURS
            ch[i] = 0.0
        else:
            ch[i] = 0.0; dis[i] = 0.0
        soc[i] = e

    e_in  = ch * DT_HOURS
    e_out = dis * DT_HOURS
    throughput = e_in + e_out
    revenue = float((price * e_out).sum())
    cost    = float((price * e_in).sum() + degradation_eur_per_mwh * throughput.sum())
    pnl     = revenue - cost

    df = pd.DataFrame({
        "timestamp": ts,
        "price": price,
        "batt_soc_mwh": soc,
        "batt_charge_mw": ch,
        "batt_discharge_mw": dis,
        "e_in_mwh": e_in,
        "e_out_mwh": e_out,
    })
    df.attrs["battery_summary"] = {"revenue": revenue, "cost": cost, "pnl": pnl}
    return df
