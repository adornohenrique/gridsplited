# app.py
import os
import sys
import yaml
import numpy as np
import pandas as pd
import streamlit as st
import importlib
from pathlib import Path

# -------------------------------------------------------------------
# Robust module import shim — works if your modules are in:
#   - ./core/*.py                (next to app.py)
#   - ../core/*.py               (one level up)
#   - ./*.py or ../*.py          (no 'core' folder)
# -------------------------------------------------------------------
def _load_modules():
    base = Path(__file__).resolve().parent
    candidates = [
        base / "core",
        base,
        base.parent / "core",
        base.parent,
    ]
    # Put candidates at the FRONT of sys.path so imports resolve here first
    for p in candidates:
        p = str(p)
        if p not in sys.path:
            sys.path.insert(0, p)

    # Try as a proper package first
    try:
        from core import ui, io, optimizer, economics, battery, report  # type: ignore
        return ui, io, optimizer, economics, battery, report
    except Exception:
        pass

    # Fallback: import root-level modules
    mods = {}
    missing = []
    for name in ["ui", "io", "optimizer", "economics", "battery", "report"]:
        try:
            mods[name] = importlib.import_module(name)
        except Exception:
            mods[name] = None
            missing.append(name)

    # Inline minimal report if absent
    if mods.get("report") is None:
        from io import BytesIO
        def _inline_build_report(prices_aligned, dispatch_df=None, kpis=None, battery_df=None) -> bytes:
            bio = BytesIO()
            with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
                (prices_aligned or pd.DataFrame()).to_excel(xw, sheet_name="Prices", index=False)
                if dispatch_df is not None and not getattr(dispatch_df, "empty", True):
                    dispatch_df.to_excel(xw, sheet_name="Dispatch", index=False)
                if kpis:
                    pd.DataFrame([kpis]).to_excel(xw, sheet_name="KPIs", index=False)
                if battery_df is not None and not getattr(battery_df, "empty", True):
                    battery_df.to_excel(xw, sheet_name="Battery", index=False)
                pd.DataFrame({"Info":[
                    "All steps are 15-minute intervals.",
                    "Prices aligned to quarter-hours (edges expanded, gaps filled).",
                    "Dispatch uses parameters set at run time.",
                ]}).to_excel(xw, sheet_name="README", index=False)
            bio.seek(0)
            return bio.getvalue()
        class _ReportShim:  # simple namespace
            build_report = staticmethod(_inline_build_report)
        mods["report"] = _ReportShim()

    # Ensure the required ones exist
    for req in ["ui", "io", "optimizer", "economics", "battery"]:
        if mods.get(req) is None:
            raise ModuleNotFoundError(
                f"Could not import '{req}'. Fix by EITHER:\n"
                f"  1) Place your modules inside a folder named 'core' NEXT TO app.py and add core/__init__.py\n"
                f"  2) Or place ui.py, io.py, optimizer.py, economics.py, battery.py next to app.py\n"
                f"  3) Or if your modules are one level up, keep them in ../core and this shim will find them."
            )
    return mods["ui"], mods["io"], mods["optimizer"], mods["economics"], mods["battery"], mods["report"]

ui, io, optimizer, economics, battery, report = _load_modules()
# -------------------------------------------------------------------

# --------------------- Custom dispatch logic (inline) ---------------------
def _detect_price_col(df: pd.DataFrame) -> str:
    for c in ["price", "Price", "price_eur_mwh", "Price_EUR_MWh"]:
        if c in df.columns:
            return c
    # try case-insensitive
    lowers = {c.lower(): c for c in df.columns}
    for c in ["price", "price_eur_mwh"]:
        if c in lowers:
            return lowers[c]
    raise ValueError("No price column found. Expected one of: price, Price, price_eur_mwh, Price_EUR_MWh.")

def _dispatch_consumer(
    df_prices: pd.DataFrame,
    capacity_mw: float,
    breakeven_eur_per_mwh: float,
    must_run_frac: float,
    dt_hours: float = 0.25,
    battery_enabled: bool = False,
    battery_kwargs: dict | None = None,
    import_cap_mw: float | None = None,
    charge_at_low_price: bool = True,
) -> pd.DataFrame:
    """
    Consumer plant (electrolyzer/eMeOH) rule:
      - price < breakeven: run 100% capacity (optionally charge battery)
      - price ≥ breakeven: run at must_run_frac*capacity and DISCHARGE battery to cover that min load
    Battery only offsets grid import; never exports.
    """
    price_col = _detect_price_col(df_prices)
    df = df_prices.copy()
    price = df[price_col].to_numpy(dtype=float)
    n = len(df)

    # Target plant load per rule
    plant_target_mw = np.where(price < breakeven_eur_per_mwh, capacity_mw, must_run_frac * capacity_mw)

    # Battery params
    if not battery_enabled or not battery_kwargs:
        bat = None
    else:
        bat = dict(
            e_mwh=float(battery_kwargs.get("e_mwh", 0.0)),
            p_ch_mw=float(battery_kwargs.get("p_ch_mw", 0.0)),
            p_dis_mw=float(battery_kwargs.get("p_dis_mw", 0.0)),
            eta_c=float(battery_kwargs.get("eta_c", 0.95)),
            eta_d=float(battery_kwargs.get("eta_d", 0.95)),
            soc_min_frac=float(battery_kwargs.get("soc_min_frac", 0.10)),
            soc_max_frac=float(battery_kwargs.get("soc_max_frac", 0.90)),
            soc0_frac=float(battery_kwargs.get("soc0_frac", 0.50)),
        )
        # clamp
        bat["soc_min_frac"] = max(0.0, min(1.0, bat["soc_min_frac"]))
        bat["soc_max_frac"] = max(0.0, min(1.0, bat["soc_max_frac"]))
        if bat["soc0_frac"] < bat["soc_min_frac"] or bat["soc0_frac"] > bat["soc_max_frac"]:
            bat["soc0_frac"] = 0.5 * (bat["soc_min_frac"] + bat["soc_max_frac"])

    # Arrays
    bat_ch_mw   = np.zeros(n)
    bat_dis_mw  = np.zeros(n)
    bat_ch_mwh  = np.zeros(n)
    bat_dis_mwh = np.zeros(n)
    soc_mwh     = np.zeros(n)
    grid_import_mw = np.zeros(n)

    if bat is not None and bat["e_mwh"] > 0:
        E   = bat["e_mwh"]
        Pch = bat["p_ch_mw"]
        Pds = bat["p_dis_mw"]
        etac = bat["eta_c"]
        etad = bat["eta_d"]
        soc_min = bat["soc_min_frac"] * E
        soc_max = bat["soc_max_frac"] * E
        soc = float(np.clip(bat["soc0_frac"] * E, soc_min, soc_max))
    else:
        E = Pch = Pds = etac = etad = soc_min = soc_max = 0.0
        soc = np.nan
        bat = None  # treat as disabled

    # Loop over time steps
    for t in range(n):
        p = price[t]
        load_mw = float(plant_target_mw[t])
        ch_mw = 0.0
        dis_mw = 0.0

        if bat is not None:
            room_mwh  = max(soc_max - soc, 0.0)
            avail_mwh = max(soc - soc_min, 0.0)
            if p < breakeven_eur_per_mwh:
                if charge_at_low_price and room_mwh > 1e-12:
                    max_ch_mwh   = etac * Pch * dt_hours
                    allow_ch_mwh = min(max_ch_mwh, room_mwh)
                    ch_mw = (allow_ch_mwh / etac) / dt_hours if allow_ch_mwh > 0 else 0.0
                    if import_cap_mw is not None:
                        max_extra = max(import_cap_mw - load_mw, 0.0)
                        ch_mw = min(ch_mw, max_extra)
            else:
                if avail_mwh > 1e-12 and load_mw > 0:
                    max_dis_mwh   = Pds * dt_hours / etad
                    allow_dis_mwh = min(max_dis_mwh, avail_mwh)
                    dis_mw = min((allow_dis_mwh * etad) / dt_hours, load_mw)  # no export

        gi_mw = load_mw + ch_mw - dis_mw
        if import_cap_mw is not None and gi_mw > import_cap_mw:
            overflow = gi_mw - import_cap_mw
            reduce_ch = min(overflow, ch_mw)
            ch_mw -= reduce_ch
            gi_mw = load_mw + ch_mw - dis_mw
            if gi_mw > import_cap_mw + 1e-9:
                gi_mw = import_cap_mw

        grid_import_mw[t] = max(gi_mw, 0.0)
        bat_ch_mw[t]   = ch_mw
        bat_dis_mw[t]  = dis_mw
        bat_ch_mwh[t]  = ch_mw * dt_hours
        bat_dis_mwh[t] = dis_mw * dt_hours

        if bat is not None:
            soc = soc + (etac * bat_ch_mwh[t]) - (bat_dis_mwh[t] / etad)
            soc = float(np.clip(soc, soc_min, soc_max))
            soc_mwh[t] = soc
        else:
            soc_mwh[t] = np.nan

    # Energy + costs
    mwh = plant_target_mw * dt_hours
    grid_import_mwh = grid_import_mw * dt_hours
    energy_cost_eur = price * grid_import_mwh
    batt_arb_eur    = price * (bat_dis_mwh - bat_ch_mwh)
    net_energy_cost_eur = energy_cost_eur

    # Output
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
# -------------------------------------------------------------------

st.set_page_config(page_title="Quarter-hour Dispatch Optimizer", layout="wide")

# ---------- Config ----------
def load_config(path="config.yaml"):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

CFG  = load_config()
D    = (CFG.get("defaults") or {})
BDEF = (CFG.get("battery_defaults") or {})
UI_C = (CFG.get("ui") or {})

# ---------- Header ----------
ui.display_logo(UI_C.get("logo", "logo.png"))
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")
ui.how_it_works_expander()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### Controls")

    st.markdown("#### 1) Price file")
    uploaded = st.file_uploader(
        "Upload CSV/XLSX with columns for time & price (any reasonable headers)",
        type=["csv", "xlsx", "xls"],
    )

    st.markdown("#### 2) Plant parameters")
    cap       = st.number_input("Plant capacity (MW)", 0.0, 1_000_000.0, float(D.get("PLANT_CAP_MW", 20.0)), 0.1)
    min_pct   = st.number_input("Min load (% of cap)", 0.0, 100.0, float(D.get("MIN_LOAD_PCT", 10.0)), 1.0)
    max_pct   = st.number_input("Max load (% of cap)", 0.0, 100.0, float(D.get("MAX_LOAD_PCT", 100.0)), 1.0)
    be        = st.number_input("Break-even (€/MWh)", -10_000.0, 10_000.0, float(D.get("BREAK_EVEN_EUR_MWH", 50.0)), 1.0)
    ramp      = st.number_input("Ramp limit per 15-min (MW)", 0.0, 1_000_000.0, float(D.get("RAMP_LIMIT_MW", 2.0)), 0.1)
    always_on = st.toggle("Always keep ≥ Min load", value=bool(D.get("ALWAYS_ON", True)))

    st.markdown("#### 3) Economics (MeOH)")
    mwh_per_ton   = st.number_input("MWh per ton MeOH", 0.0, 100_000.0, float(D.get("MWH_PER_TON", 11.0)), 0.1)
    meoh_price    = st.number_input("MeOH price (€/t)", 0.0, 1_000_000.0, float(D.get("MEOH_PRICE", 1000.0)), 1.0)
    co2_price     = st.number_input("CO₂ price (€/t)", 0.0, 1_000_000.0, float(D.get("CO2_PRICE", 40.0)), 1.0)
    co2_intensity = st.number_input("CO₂ intensity (t/t MeOH)", 0.0, 1000.0, float(D.get("CO2_INTENSITY", 1.375)), 0.001)
    maint_pct     = st.number_input("Maintenance (% revenue)", 0.0, 100.0, float(D.get("MAINT_PCT", 3.0)), 0.1)
    sga_pct       = st.number_input("SG&A (% revenue)", 0.0, 100.0, float(D.get("SGA_PCT", 2.0)), 0.1)
    ins_pct       = st.number_input("Insurance (% revenue)", 0.0, 100.0, float(D.get("INS_PCT", 1.0)), 0.1)
    water_cost_t  = st.number_input("Water cost (€/t MeOH)", 0.0, 1_000_000.0, float(D.get("WATER_COST_T", 7.3)), 0.1)
    other_opex_t  = st.number_input("Other OPEX (€/t MeOH)", 0.0, 1_000_000.0, float(D.get("OTHER_OPEX_T", 0.0)), 0.1)

    st.markdown("#### 4) Battery (optional)")
    use_batt = st.toggle("Enable battery", value=bool(BDEF.get("enabled", False)))
    if use_batt:
        e_mwh    = st.number_input("Energy capacity (MWh)", 0.0, 1_000_000.0, float(BDEF.get("e_mwh", 10.0)), 0.1)
        p_ch     = st.number_input("Charge power limit (MW)", 0.0, 1_000_000.0, float(BDEF.get("p_ch_mw", 5.0)), 0.1)
        p_dis    = st.number_input("Discharge power limit (MW)", 0.0, 1_000_000.0, float(BDEF.get("p_dis_mw", 5.0)), 0.1)
        eff_ch   = st.number_input("Charge efficiency (0–1)", 0.0, 1.0, float(BDEF.get("eff_ch", 0.95)), 0.01)
        eff_dis  = st.number_input("Discharge efficiency (0–1)", 0.0, 1.0, float(BDEF.get("eff_dis", 0.95)), 0.01)
        soc_min  = st.number_input("SOC min (0–1)", 0.0, 1.0, float(BDEF.get("soc_min", 0.10)), 0.01)
        soc_max  = st.number_input("SOC max (0–1)", 0.0, 1.0, float(BDEF.get("soc_max", 0.90)), 0.01)
        # Initial SoC defaults mid-band
        st.caption("Initial SoC uses midpoint between min & max.")

# ---------- Data loaders ----------
@st.cache_data(show_spinner=False)
def load_and_align(file):
    raw = io.load_prices(file)
    aligned = io.ensure_quarter_hour(raw, method="pad", expand_edges=True)
    return raw, aligned

tabs = st.tabs(["Data", "Dispatch", "Economics", "Battery", "Matrix & Portfolio"])

df_raw = df_prices = None
if uploaded:
    try:
        df_raw, df_prices = load_and_align(uploaded)
        issues = io.sanity_checks(df_prices)
        if issues:
            ui.show_data_quality(issues)
        ui.show_row_counts(len(df_raw), len(df_prices))
    except Exception as e:
        st.error(f"Failed to load prices: {e}")

with tabs[0]:
    st.subheader("Prices")
    if df_prices is None:
        st.info("Upload a file in the sidebar to begin.")
    else:
        st.write(f"Full dataset length: {len(df_prices):,} rows at 15-min cadence.")
        st.dataframe(df_prices.head(96), use_container_width=True)

with tabs[1]:
    st.subheader("Dispatch")
    if df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Run optimization", use_container_width=True):
            with st.spinner("Optimizing…"):
                out = _dispatch_consumer(
                    df_prices=df_prices,
                    capacity_mw=cap,
                    breakeven_eur_per_mwh=be,
                    must_run_frac=min_pct/100.0,
                    dt_hours=0.25,
                    battery_enabled=use_batt,
                    battery_kwargs=(dict(
                        e_mwh=e_mwh,
                        p_ch_mw=p_ch,
                        p_dis_mw=p_dis,
                        eta_c=eff_ch,
                        eta_d=eff_dis,
                        soc_min_frac=soc_min,
                        soc_max_frac=soc_max,
                        soc0_frac=(soc_min + soc_max)/2.0,
                    ) if use_batt else None),
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["dispatch_df"] = out
            st.write(f"Computed rows: {len(out):,}")
            st.success("Done.")
            st.dataframe(out.head(96), use_container_width=True)
            st.download_button(
                "Download CSV (dispatch)",
                data=out.to_csv(index=False).encode("utf-8"),
                file_name="dispatch.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tabs[2]:
    st.subheader("Economics")
    if df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Compute methanol economics", use_container_width=True):
            with st.spinner("Calculating…"):
                disp = _dispatch_consumer(
                    df_prices=df_prices,
                    capacity_mw=cap,
                    breakeven_eur_per_mwh=be,
                    must_run_frac=min_pct/100.0,
                    dt_hours=0.25,
                    battery_enabled=use_batt,
                    battery_kwargs=(dict(
                        e_mwh=e_mwh,
                        p_ch_mw=p_ch,
                        p_dis_mw=p_dis,
                        eta_c=eff_ch,
                        eta_d=eff_dis,
                        soc_min_frac=soc_min,
                        soc_max_frac=soc_max,
                        soc0_frac=(soc_min + soc_max)/2.0,
                    ) if use_batt else None),
                )
                kpis = economics.compute_kpis(
                    disp,
                    mwh_per_ton=mwh_per_ton,
                    meoh_price_eur_per_ton=meoh_price,
                    co2_price_eur_per_ton=co2_price,
                    co2_t_per_ton_meoh=co2_intensity,
                    maint_pct=maint_pct,
                    sga_pct=sga_pct,
                    ins_pct=ins_pct,
                    water_cost_eur_per_ton=water_cost_t,
                    other_opex_eur_per_ton=other_opex_t,
                    break_even_eur_per_mwh=be,
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["dispatch_df"] = disp
            st.session_state["kpis"] = kpis
            ui.show_kpis(kpis)
            st.success("Done.")

with tabs[3]:
    st.subheader("Battery")
    if df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Run with battery", use_container_width=True):
            with st.spinner("Optimizing with battery…"):
                res = battery.run_battery_strategy(
                    df_prices,
                    e_mwh=e_mwh, p_ch_mw=p_ch, p_dis_mw=p_dis,
                    eff_ch=eff_ch, eff_dis=eff_dis,
                    soc_min=soc_min, soc_max=soc_max,
                    price_low=ui.safe_number(BDEF.get("price_low", 30.0)),
                    price_high=ui.safe_number(BDEF.get("price_high", 90.0)),
                    degradation_eur_per_mwh=ui.safe_number(BDEF.get("degradation_eur_per_mwh", 0.0)),
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["battery_df"]    = res
            st.success("Done.")
            st.dataframe(res.head(96), use_container_width=True)
            st.download_button(
                "Download CSV (battery)",
                data=res.to_csv(index=False).encode("utf-8"),
                file_name="battery.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Coming soon: batch scenarios & portfolio view.")

# ---------- Report download on sidebar ----------
try:
    report_bytes = report.build_report(
        prices_aligned=st.session_state.get("prices_aligned"),
        dispatch_df=st.session_state.get("dispatch_df"),
        kpis=st.session_state.get("kpis"),
        battery_df=st.session_state.get("battery_df"),
    )
    st.sidebar.download_button(
        "Download Excel report",
        data=report_bytes,
        file_name="dispatch_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
except Exception as e:
    st.sidebar.error(f"Report build failed: {e}")
