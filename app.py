# app.py
"""
Main Streamlit app — wired to the new UPPERCASE fields returned by core/ui.sidebar().
Works with:
- core/ui.py  (the JSON-safe version with scenario save/load)
- core/io.py  (CSV/Excel loader)
- core/optimizer.py (run_dispatch)
- core/constants.py (defaults)
- core/economics.py (only used for benchmark shown in sidebar)
"""

import os
import streamlit as st
import pandas as pd

from core import ui, io, optimizer, constants


# ---------------------------------------------------------
# Page setup
# ---------------------------------------------------------
st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# Optional logo (place logo.png next to app.py)
ui.display_logo("logo.png")

st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

# Tabs for structure
tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])


# ---------------------------------------------------------
# Helpers (kept here to avoid mismatches)
# ---------------------------------------------------------
def _compute_price_cap_from_params(p) -> tuple[float, str]:
    """
    Compute dispatch price cap based on the selected margin method.

    Returns
    -------
    cap : float
        Price threshold in €/MWh.
    tag : str
        "power-only" or "full-econ".
    """
    # Choose base break-even (sidebar may request using benchmark)
    break_even = p.BENCHMARK_BE if p.USE_BENCH_AS_BREAK_EVEN else p.BREAK_EVEN_EUR_MWH

    target = float(p.TARGET_MARGIN_PCT) / 100.0

    if str(p.MARGIN_METHOD).lower().startswith("power"):
        cap = max(0.0, (1.0 - target) * float(break_even))
        return cap, "power-only"

    # full-economics
    opex_pct = float(p.MAINT_PCT or 0) + float(p.SGA_PCT or 0) + float(p.INS_PCT or 0)
    opex_pct = opex_pct / 100.0

    if float(p.MWH_PER_TON) <= 0:
        st.error("Full-economics margin requires Electricity per ton (MWh/t) > 0.")
        return 0.0, "full-econ"

    cap = (
        p.MEOH_PRICE * (1.0 - target - opex_pct)
        - p.CO2_PRICE * p.CO2_INTENSITY
    ) / p.MWH_PER_TON

    return max(0.0, float(cap)), "full-econ"


def _nice_number(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return x


# ---------------------------------------------------------
# Tab 1: Inputs & Run
# ---------------------------------------------------------
with tabs[0]:
    st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")

    # Collect all sidebar inputs (UPPERCASE names)
    params = ui.sidebar()

    # Compute price cap from margin choices
    price_cap, method_tag = _compute_price_cap_from_params(params)

    if params.run:
        # Validate file
        if params.uploaded is None:
            st.error("Please upload a CSV or Excel with timestamp and price.")
            st.stop()

        # Load / standardize prices
        try:
            df_prices = io.load_prices(params.uploaded)
        except Exception as e:
            st.exception(e)
            st.stop()

        # Persist the inputs to temp files for the optimizer (if it needs files)
        tmp_csv = "/tmp/_prices.csv"
        out_xlsx = "/tmp/dispatch_output.xlsx"
        try:
            df_prices.to_csv(tmp_csv, index=False)
        except Exception:
            # Some platforms disallow /tmp; fallback to current dir
            tmp_csv = "prices_tmp.csv"
            out_xlsx = "dispatch_output.xlsx"
            df_prices.to_csv(tmp_csv, index=False)

        # Run dispatch
        results, kpis = optimizer.run_dispatch(
            df=df_prices,
            plant_capacity_mw=params.PLANT_CAP_MW,
            min_load_pct=params.MIN_LOAD_PCT,
            max_load_pct=params.MAX_LOAD_PCT,
            break_even_eur_per_mwh=(
                params.BENCHMARK_BE if params.USE_BENCH_AS_BREAK_EVEN else params.BREAK_EVEN_EUR_MWH
            ),
            ramp_limit_mw_per_step=(params.RAMP_LIMIT_MW if params.RAMP_LIMIT_MW > 0 else None),
            always_on=params.ALWAYS_ON,
            dispatch_threshold_eur_per_mwh=price_cap,
            mwh_per_ton=(params.MWH_PER_TON if params.MWH_PER_TON > 0 else None),
            methanol_price_eur_per_ton=params.MEOH_PRICE,
            co2_price_eur_per_ton=params.CO2_PRICE,
            co2_t_per_ton_meoh=params.CO2_INTENSITY,
            maintenance_pct_of_revenue=params.MAINT_PCT / 100.0,
            sga_pct_of_revenue=params.SGA_PCT / 100.0,
            insurance_pct_of_revenue=params.INS_PCT / 100.0,
            # The optimizer can ignore these next two, but we keep them consistent:
            target_margin_fraction=float(params.TARGET_MARGIN_PCT) / 100.0,
            margin_method=method_tag,
        )

        st.success("Optimization complete.")
        st.session_state["__results__"] = results
        st.session_state["__kpis__"] = kpis
        st.session_state["__out_xlsx__"] = out_xlsx

        st.info(
            f"Applied dispatch price cap: **{_nice_number(price_cap)} €/MWh**  "
            f"(method: {method_tag}, target margin: {params.TARGET_MARGIN_PCT:.1f}%)"
        )

        # Quick KPIs preview
        if isinstance(kpis, dict):
            preview = {
                "price_cap_eur_per_mwh": price_cap,
                "method": method_tag,
                "total_energy_mwh": kpis.get("total_energy_mwh"),
                "weighted_avg_price_eur_per_mwh": kpis.get("weighted_avg_price_eur_per_mwh"),
                "total_power_cost_eur": kpis.get("total_power_cost_eur"),
                "total_tons": kpis.get("total_tons"),
                "total_methanol_revenue_eur": kpis.get("total_methanol_revenue_eur"),
                "total_true_profit_eur": kpis.get("total_true_profit_eur"),
                "total_profit_proxy_eur": kpis.get("total_profit_proxy_eur"),
            }
            st.subheader("KPIs (preview)")
            st.dataframe(pd.DataFrame([preview]))


# ---------------------------------------------------------
# Tab 2: Results
# ---------------------------------------------------------
with tabs[1]:
    st.subheader("Results")
    results = st.session_state.get("__results__")
    kpis = st.session_state.get("__kpis__")
    if results is None:
        st.info("Run an optimization first.")
    else:
        st.dataframe(results.head(300), use_container_width=True)
        if isinstance(kpis, dict):
            st.markdown("### KPIs (full)")
            st.json(kpis)


# ---------------------------------------------------------
# Tab 3: Charts (simple example)
# ---------------------------------------------------------
with tabs[2]:
    st.subheader("Charts")
    results = st.session_state.get("__results__")
    if results is None:
        st.info("Run an optimization first.")
    else:
        # If your results include 'timestamp', 'price_eur_per_mwh', 'dispatch_mw'
        # you can plot quickly. Guard for missing cols.
        cols = results.columns
        if "timestamp" in cols and "price_eur_per_mwh" in cols:
            st.line_chart(
                results.set_index("timestamp")[["price_eur_per_mwh"]],
                use_container_width=True,
            )
        if "timestamp" in cols and "dispatch_mw" in cols:
            st.line_chart(
                results.set_index("timestamp")[["dispatch_mw"]],
                use_container_width=True,
            )


# ---------------------------------------------------------
# Tab 4: Downloads
# ---------------------------------------------------------
with tabs[3]:
    st.subheader("Downloads")
    results = st.session_state.get("__results__")
    out_xlsx = st.session_state.get("__out_xlsx__")

    if results is None:
        st.info("Run an optimization first.")
    else:
        st.download_button(
            "Download CSV (full results)",
            data=results.to_csv(index=False).encode("utf-8"),
            file_name="dispatch_plan.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # If your optimizer wrote an Excel file to out_xlsx, expose it:
        if out_xlsx and os.path.exists(out_xlsx):
            with open(out_xlsx, "rb") as fh:
                st.download_button(
                    "Download Excel (full results)",
                    data=fh.read(),
                    file_name="dispatch_plan.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        else:
            st.caption("Excel export not found (depends on optimizer settings).")


# ---------------------------------------------------------
# Tab 5: Matrix & Portfolio (placeholder)
# ---------------------------------------------------------
with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Add your matrix/portfolio tools here. (This tab is a placeholder.)")
