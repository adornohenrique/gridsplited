# core/optimizer.py
from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

DT_HOURS = 0.25  # 15-min steps

def _apply_ramp(prev: float, target: float, ramp: Optional[float]) -> float:
    if ramp is None or not np.isfinite(ramp):
        return target
    hi = prev + float(ramp)
    lo = prev - float(ramp)
    if target > hi: return hi
    if target < lo: return lo
    return target

def run_dispatch(
    df_prices: pd.DataFrame,
    plant_capacity_mw: float,
    min_load_pct: float,
    max_load_pct: float,
    break_even_eur_per_mwh: float,
    ramp_limit_mw_per_step: Optional[float] = None,
    always_on: bool = True,
) -> pd.DataFrame:
    ts = df_prices["timestamp"].to_numpy()
    price = df_prices["price"].to_numpy(dtype=float)

    pmin = plant_capacity_mw * min_load_pct / 100.0
    pmax = plant_capacity_mw * max_load_pct / 100.0
    thr = break_even_eur_per_mwh

    out = np.empty_like(price, dtype=float)
    prev = pmin if always_on else 0.0

    for i in range(price.shape[0]):
        tgt = pmax if price[i] >= thr else (pmin if always_on else 0.0)
        out[i] = _apply_ramp(prev, tgt, ramp_limit_mw_per_step)
        out[i] = min(max(out[i], (pmin if always_on and price[i] < thr else 0.0)), pmax)
        prev = out[i]

    mwh = out * DT_HOURS
    df = pd.DataFrame({"timestamp": ts, "price": price, "dispatch_mw": out, "mwh": mwh})
    df["proxy_profit_eur"] = (price - thr) * df["mwh"]
    return df
