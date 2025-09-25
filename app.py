# app.py
import streamlit as st
import pandas as pd
from core import ui, io, economics, optimizer, constants

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# Header
ui.display_logo("logo.png")
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

# Sidebar (collect inputs)
params = ui.sidebar()

# Apply optional benchmark to BE
break_even = params.break_even
if params.use_bench_as_break_even:
    break_even = economics.benchmark_power_price(
        p_methanol=params.methanol_price,
        p_co2=params.co2_price,
        water_cost_eur_per_t=params.water_cost_t,
        trader_margin_pct=params.trader_margin_pct_ui,
        power_mwh_per_t=float(params.mwh_per_ton),
        co2_t_per_t=float(params.co2_intensity),
    )

# Run
if params.run:
    if params.uploaded is None:
        st.error("Please upload a CSV or Excel with timestamp and price.")
        st.stop()

    try:
        df = io.load_prices(params.uploaded)
    except Exception as e:
        st.exception(e)
        st.stop()

    # Compute price cap (target margin)
    price_cap, method_tag, err = economics.compute_price_cap(
        margin_method=params.margin_method,
        target_margin_pct=params.target_margin_pct,
        break_even_eur_per_mwh=break_even,
        maint_pct=params.maint_pct,
        sga_pct=params.sga_pct,
        ins_pct=params.ins_pct,
        mwh_per_ton=params.mwh_per_ton,
        methanol_price=params.methanol_price,
        co2_price=params.co2_price,
        co2_intensity=params.co2_intensity,
    )
    if err:
        st.error(err)
        st.stop()

    st.info(
        f"Applied dispatch price cap: **{price_cap:,.2f} €/MWh**  "
        f"(method: {method_tag}, target margin: {params.target_margin_pct:.1f}%)"
    )

    results, kpis, out_xlsx = optimizer.run_dispatch(
        df=df,
        plant_capacity_mw=params.plant_capacity_mw,
        min_load_pct=params.min_load_pct,
        max_load_pct=params.max_load_pct,
        break_even_eur_per_mwh=break_even,
        ramp_limit_mw_per_step=(params.ramp_limit if params.ramp_limit > 0 else None),
        always_on=params.always_on,
        dispatch_threshold_eur_per_mwh=price_cap,
        mwh_per_ton=(params.mwh_per_ton if params.mwh_per_ton > 0 else None),
        methanol_price_eur_per_ton=params.methanol_price,
        co2_price_eur_per_ton=params.co2_price,
        co2_t_per_ton_meoh=params.co2_intensity,
        maintenance_pct_of_revenue=params.maint_pct,
        sga_pct_of_revenue=params.sga_pct,
        insurance_pct_of_revenue=params.ins_pct,
        target_margin_fraction=float(params.target_margin_pct)/100.0,
        margin_method=method_tag,
    )

    st.success("Optimization complete.")

    # KPIs table (overview)
    st.subheader("KPIs (project overview)")
    kpis_view = economics.build_kpis_view(
        kpis=kpis,
        break_even=break_even,
        mwh_per_ton=params.mwh_per_ton,
        co2_price=params.co2_price,
        co2_intensity=params.co2_intensity,
        water_cost_t=params.water_cost_t,
        other_opex_per_t=params.other_opex_per_t,
    )
    st.dataframe(pd.DataFrame([kpis_view]))

    if kpis.get("total_tons") is not None:
        st.metric("Total production (t)", f"{kpis['total_tons']}")

    st.subheader("Dispatch (first 200 rows)")
    st.dataframe(results.head(200))

    ui.downloads(results, out_xlsx)
else:
    st.info("Upload your 15-min price file and click **Run Optimization**.")
    st.caption("Autodetects CSV/Excel, separators, and comma-decimal formats.")
