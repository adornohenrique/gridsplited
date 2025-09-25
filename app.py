# app.py
import streamlit as st
import pandas as pd

from core import ui, io, economics, optimizer, constants
from core.help import render_help
from core.matrix import run_param_matrix
from core.portfolio import run_portfolio

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")
ui.display_logo("logo.png")

st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")
st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")

# ---------------- Sidebar & scenario ----------------
params = ui.sidebar()

# Compute price cap from target margin selection
def _compute_price_cap():
    if params.margin_method.startswith("Power"):
        method_tag = "power-only"
        cap = max(0.0, (1.0 - params.target_margin_pct/100.0) * params.break_even)
        return cap, method_tag, None
    else:
        method_tag = "full-econ"
        cap = economics.compute_price_cap(
            margin_method=method_tag,
            target_margin_pct=params.target_margin_pct,
            break_even_eur_per_mwh=params.break_even,
            maint_pct=params.maint_pct,
            sga_pct=params.sga_pct,
            ins_pct=params.ins_pct,
            mwh_per_ton=params.mwh_per_ton,
            methanol_price=params.methanol_price,
            co2_price=params.co2_price,
            co2_t_per_t=params.co2_intensity,
        )
        return max(0.0, cap), method_tag, None

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio", "Help"]
)

with tab1:
    st.subheader("Inputs & Run")
    if params.run:
        if params.uploaded is None:
            st.error("Please upload a CSV or Excel with timestamp and price.")
        else:
            try:
                df = io.load_prices(params.uploaded)
            except Exception as e:
                st.exception(e)
                df = None

            if df is not None:
                price_cap, method_tag, _ = _compute_price_cap()
                st.info(f"Applied dispatch price cap: **{price_cap:,.2f} €/MWh**  (method: {method_tag}, target margin: {params.target_margin_pct:.1f}%)")

                results, kpis = optimizer.run_dispatch(
                    df=df,
                    plant_capacity_mw=params.plant_capacity_mw,
                    min_load_pct=params.min_load_pct,
                    max_load_pct=params.max_load_pct,
                    break_even_eur_per_mwh=params.break_even,
                    ramp_limit_mw_per_step=(params.ramp_limit if params.ramp_limit > 0 else None),
                    always_on=params.always_on,
                    dispatch_threshold_eur_per_mwh=price_cap,
                    mwh_per_ton=params.mwh_per_ton,
                    methanol_price_eur_per_ton=params.methanol_price,
                    co2_price_eur_per_ton=params.co2_price,
                    co2_t_per_ton_meoh=params.co2_intensity,
                    maintenance_pct_of_revenue=params.maint_pct,
                    sga_pct_of_revenue=params.sga_pct,
                    insurance_pct_of_revenue=params.ins_pct,
                    target_margin_fraction=params.target_margin_pct / 100.0,
                    margin_method=method_tag,
                )

                st.session_state["__results"] = results
                st.session_state["__kpis"] = kpis
                st.success("Optimization complete. See Results/Charts/Downloads tabs.")

with tab2:
    st.subheader("Results")
    kpis = st.session_state.get("__kpis")
    results = st.session_state.get("__results")
    if not kpis or results is None:
        st.info("Run an optimization first.")
    else:
        show_cols = [
            "dispatch_threshold_eur_per_mwh",
            "target_margin_fraction",
            "margin_method",
            "total_energy_mwh",
            "weighted_avg_price_eur_per_mwh",
            "total_power_cost_eur",
            "total_tons",
            "total_methanol_revenue_eur",
            "total_co2_cost_eur",
            "total_opex_misc_eur",
            "total_true_profit_eur",
            "total_profit_proxy_eur",
        ]
        view = {k: kpis.get(k) for k in show_cols}
        st.dataframe(pd.DataFrame([view]))
        st.divider()
        st.caption("Dispatch (first 200 rows)")
        st.dataframe(results.head(200))

with tab3:
    st.subheader("Charts")
    results = st.session_state.get("__results")
    if results is None:
        st.info("Run an optimization first.")
    else:
        # Lightweight charts (no seaborn)
        st.line_chart(results.set_index("timestamp")[["price_eur_per_mwh"]], use_container_width=True)
        st.line_chart(results.set_index("timestamp")[["dispatch_mw"]], use_container_width=True)

with tab4:
    st.subheader("Downloads")
    results = st.session_state.get("__results")
    if results is None:
        st.info("Run an optimization first.")
    else:
        out_csv = results.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV (full results)", out_csv, "dispatch_plan.csv", "text/csv", use_container_width=True)

with tab5:
    st.subheader("Matrix & Portfolio")

    # Build a base dict (re-usable) once user has a valid file
    df_for_batch = None
    if params.uploaded is not None:
        try:
            df_for_batch = io.load_prices(params.uploaded)
        except Exception:
            df_for_batch = None

    price_cap, method_tag, _ = _compute_price_cap()
    base = ui.to_base_params(params, price_cap, method_tag)

    subA, subB = st.tabs(["Parameter matrix", "Portfolio"])

    with subA:
        st.caption("Sweep two parameters and evaluate total profit (simple grid).")
        # Choose parameters to sweep
        options = {
            "break_even_eur_per_mwh": ("Price BE", 10.0, 300.0),
            "min_load_pct": ("Min load (0–1)", 0.0, 1.0),
            "max_load_pct": ("Max load (0–1)", 0.1, 1.0),
            "target_margin_fraction": ("Target margin (0–1)", 0.0, 0.9),
        }
        col1, col2 = st.columns(2)
        with col1:
            x_key = st.selectbox("X parameter", list(options.keys()), index=0)
            x_start = st.number_input("X start", value=base.get(x_key, options[x_key][1]))
            x_stop  = st.number_input("X stop",  value=base.get(x_key, options[x_key][2]))
            x_step  = st.number_input("X step",  value=(x_stop - x_start)/5 if x_stop > x_start else 1.0)
        with col2:
            y_key = st.selectbox("Y parameter", [k for k in options.keys() if k != x_key], index=1)
            y_start = st.number_input("Y start", value=base.get(y_key, options[y_key][1]))
            y_stop  = st.number_input("Y stop",  value=base.get(y_key, options[y_key][2]))
            y_step  = st.number_input("Y step",  value=(y_stop - y_start)/5 if y_stop > y_start else 1.0)

        run_matrix = st.button("Run matrix", use_container_width=True)
        if run_matrix:
            if df_for_batch is None:
                st.error("Upload a valid price file on the sidebar first.")
            else:
                with st.spinner("Running matrix..."):
                    mdf = run_param_matrix(
                        df=df_for_batch,
                        base=base,
                        x_param=x_key, x_range=(float(x_start), float(x_stop), float(x_step)),
                        y_param=y_key, y_range=(float(y_start), float(y_stop), float(y_step)),
                    )
                st.success("Done.")
                st.dataframe(mdf)
                st.download_button("Download matrix CSV", mdf.to_csv(index=False).encode("utf-8"), "matrix.csv", "text/csv", use_container_width=True)

    with subB:
        st.caption("Run the same parameters across multiple price files.")
        multi_files = st.file_uploader("Upload multiple price files", type=["csv","xlsx","xls"], accept_multiple_files=True)
        run_port = st.button("Run portfolio", use_container_width=True)
        if run_port:
            if not multi_files:
                st.error("Please upload at least one file.")
            else:
                with st.spinner("Running portfolio..."):
                    summary, per_file = run_portfolio(multi_files, base)
                st.success("Done.")
                st.dataframe(summary)
                st.download_button("Download portfolio CSV", summary.to_csv(index=False).encode("utf-8"), "portfolio.csv", "text/csv", use_container_width=True)

with tab6:
    render_help()
