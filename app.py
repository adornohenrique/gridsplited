# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

from core import ui, io, economics, optimizer, constants
from core.help import show_help_panel
from core.battery import BatteryParams
from core.tolling import TollingParams, price_cap_tolling, build_tolling_timeline_and_kpis

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# Header
ui.display_logo(constants.UI.get("logo","logo.png"))
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")
show_help_panel()

tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads"])

with tabs[0]:
    params = ui.sidebar()
    st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")

    # Apply optional benchmark (ignored if tolling mode active)
    break_even = params.break_even
    if (not params.TOLLING_ENABLED) and params.use_bench_as_break_even:
        break_even = economics.benchmark_power_price(
            p_methanol=params.methanol_price,
            p_co2=params.co2_price,
            water_cost_eur_per_t=params.water_cost_t,
            trader_margin_pct=params.trader_margin_pct_ui,
            power_mwh_per_t=float(params.mwh_per_ton),
            co2_t_per_t=float(params.co2_intensity),
        )

    # Compute dispatch threshold (price cap)
    if params.TOLLING_ENABLED:
        # ---------------- TOLLING price cap ----------------
        price_cap = price_cap_tolling(
            target_margin_pct=float(params.TARGET_MARGIN_PCT),
            variable_fee_eur_per_mwh=float(params.toll_var_fee),
            maint_pct=float(params.maint_pct),
            sga_pct=float(params.sga_pct),
            ins_pct=float(params.ins_pct),
            other_var_cost_eur_per_mwh=float(params.toll_other_mwh),
        )
        method_tag = "tolling"
        err = None
    else:
        # ---------------- Original price cap ----------------
        price_cap, method_tag, err = economics.compute_price_cap(
            margin_method=str(params.MARGIN_METHOD),
            target_margin_pct=float(params.TARGET_MARGIN_PCT),
            break_even_eur_per_mwh=float(break_even),
            maint_pct=float(params.maint_pct),
            sga_pct=float(params.sga_pct),
            ins_pct=float(params.ins_pct),
            mwh_per_ton=float(params.mwh_per_ton),
            methanol_price=float(params.methanol_price),
            co2_price=float(params.co2_price),
            co2_t_per_t=float(params.co2_intensity),
        )
    if err:
        st.error(err)
        st.stop()

    # Prepare BatteryParams
    bat = BatteryParams(
        enabled=bool(params.bat_en),
        e_mwh=float(params.e_mwh),
        p_ch_mw=float(params.p_ch),
        p_dis_mw=float(params.p_dis),
        eff_ch=float(params.eff_ch),
        eff_dis=float(params.eff_dis),
        soc_min=float(params.soc_min),
        soc_max=float(params.soc_max),
        price_low=float(params.price_low),
        price_high=float(params.price_high),
        degradation_eur_per_mwh=float(params.degr),
    )

    # Prepare TollingParams
    toll = TollingParams(
        enabled=bool(params.TOLLING_ENABLED),
        contracted_mw=float(params.contracted_mw),
        capacity_fee_eur_per_mw_month=float(params.toll_cap_fee),
        variable_fee_eur_per_mwh=float(params.toll_var_fee),
        other_var_cost_eur_per_mwh=float(params.toll_other_mwh),
        maint_pct=float(params.maint_pct),
        sga_pct=float(params.sga_pct),
        ins_pct=float(params.ins_pct),
    )

    # Run
    if params.run:
        if params.uploaded is None:
            st.error("Please upload a CSV/Excel with timestamp and price.")
            st.stop()
        try:
            df = io.load_prices(params.uploaded)
        except Exception as e:
            st.exception(e)
            st.stop()

        plant_res, plant_kpis, bat_df, bat_kpis = optimizer.run_dispatch(
            df=df,
            plant_capacity_mw=params.plant_capacity_mw,
            min_load_pct=params.min_load_pct,
            max_load_pct=params.max_load_pct,
            break_even_eur_per_mwh=float(break_even),
            ramp_limit_mw_per_step=(params.ramp_limit if params.ramp_limit > 0 else None),
            always_on=params.always_on,
            dispatch_threshold_eur_per_mwh=float(price_cap),
            mwh_per_ton=float(params.mwh_per_ton),
            methanol_price_eur_per_ton=float(params.methanol_price),
            co2_price_eur_per_ton=float(params.co2_price),
            co2_t_per_ton_meoh=float(params.co2_intensity),
            maintenance_pct_of_revenue=float(params.maint_pct),
            sga_pct_of_revenue=float(params.sga_pct),
            insurance_pct_of_revenue=float(params.ins_pct),
            target_margin_fraction=float(params.TARGET_MARGIN_PCT)/100.0,
            margin_method=method_tag,
            battery_params=bat
        )

        # ---------------- TOLLING KPIs & timeline ----------------
        toll_timeline, toll_kpis = build_tolling_timeline_and_kpis(
            plant_results=plant_res,
            toll=toll,
            contracted_mw_cap=min(params.contracted_mw, params.plant_capacity_mw),
        )

        # Save for other tabs
        st.session_state["last_results"] = plant_res
        st.session_state["last_kpis"] = plant_kpis
        st.session_state["last_bat_df"] = bat_df
        st.session_state["last_bat_kpis"] = bat_kpis
        st.session_state["last_toll_df"] = toll_timeline
        st.session_state["last_toll_kpis"] = toll_kpis
        st.session_state["last_method"] = method_tag
        st.success("Optimization complete. See Results / Charts / Downloads tabs.")

with tabs[1]:
    res = st.session_state.get("last_results")
    kpis = st.session_state.get("last_kpis", {})
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    bat_kpis = st.session_state.get("last_bat_kpis", {})
    toll_df = st.session_state.get("last_toll_df", pd.DataFrame())
    toll_kpis = st.session_state.get("last_toll_kpis", {"tolling_enabled": False})
    method_tag = st.session_state.get("last_method", "")

    if res is None:
        st.info("No results yet. Run an optimization first.")
    else:
        st.subheader("KPIs — Plant (product economics)")
        st.dataframe(pd.DataFrame([kpis]))

        if toll_kpis.get("tolling_enabled"):
            st.subheader("KPIs — Tolling")
            st.dataframe(pd.DataFrame([toll_kpis]))

        if bat_kpis.get("battery_enabled"):
            st.subheader("KPIs — Battery")
            st.dataframe(pd.DataFrame([bat_kpis]))

        # Combined project profit
        # If tolling enabled, use tolling_total_profit_eur instead of product profit
        plant_profit = kpis.get("total_true_profit_eur")
        if toll_kpis.get("tolling_enabled"):
            plant_profit = toll_kpis.get("tolling_total_profit_eur", 0.0)
        elif plant_profit is None:
            plant_profit = kpis.get("total_profit_proxy_eur", 0.0)

        total_project_profit = float(plant_profit or 0.0) + float(bat_kpis.get("battery_profit_eur", 0.0))
        st.metric("Total Project Profit (Plant + Battery)", f"€{total_project_profit:,.0f}")

        st.subheader("Dispatch (first 200 rows)")
        st.dataframe(res.head(200))

        if not toll_df.empty:
            st.subheader("Tolling timeline (first 200 rows)")
            st.dataframe(toll_df.head(200))

with tabs[2]:
    res = st.session_state.get("last_results")
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    toll_df = st.session_state.get("last_toll_df", pd.DataFrame())

    if res is None:
        st.info("Run an optimization to populate charts.")
    else:
        tmp = res.copy()
        if "timestamp" in tmp.columns:
            tmp["timestamp"] = pd.to_datetime(tmp["timestamp"])
        price_col = "price_eur_per_mwh"
        y_cols = [c for c in tmp.columns if c in (price_col, "dispatch_mw", "mw")]
        if "dispatch_mw" in tmp.columns:
            st.plotly_chart(px.line(tmp, x="timestamp", y=[price_col, "dispatch_mw"], title="Price vs Dispatch (MW)"), use_container_width=True)
        elif "mw" in tmp.columns:
            st.plotly_chart(px.line(tmp, x="timestamp", y=[price_col, "mw"], title="Price vs Dispatch (MW)"), use_container_width=True)

        if "true_profit_eur" in tmp.columns:
            daily = tmp.groupby(tmp["timestamp"].dt.date)["true_profit_eur"].sum().reset_index(name="profit")
            st.plotly_chart(px.bar(daily, x="timestamp", y="profit", title="Daily Profit (product mode)"), use_container_width=True)

        if not toll_df.empty:
            daily_toll = toll_df.copy()
            daily_toll["date"] = pd.to_datetime(daily_toll["timestamp"]).dt.date
            dsum = daily_toll.groupby("date")["toll_profit_eur"].sum().reset_index()
            st.plotly_chart(px.bar(dsum, x="date", y="toll_profit_eur", title="Daily Profit (tolling mode)"), use_container_width=True)

        if not bat_df.empty and "bat_soc" in bat_df.columns:
            st.plotly_chart(px.line(bat_df, x="timestamp", y="bat_soc", title="Battery SOC"), use_container_width=True)

with tabs[3]:
    res = st.session_state.get("last_results")
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    toll_df = st.session_state.get("last_toll_df", pd.DataFrame())

    if res is None:
        st.info("Run an optimization first.")
    else:
        st.download_button("⬇️ Download dispatch CSV",
                           data=res.to_csv(index=False).encode("utf-8"),
                           file_name="dispatch_plan.csv",
                           mime="text/csv",
                           use_container_width=True)

        if not bat_df.empty:
            st.download_button("⬇️ Download battery CSV",
                               data=bat_df.to_csv(index=False).encode("utf-8"),
                               file_name="battery_schedule.csv",
                               mime="text/csv",
                               use_container_width=True)

        if not toll_df.empty:
            st.download_button("⬇️ Download tolling timeline CSV",
                               data=toll_df.to_csv(index=False).encode("utf-8"),
                               file_name="tolling_timeline.csv",
                               mime="text/csv",
                               use_container_width=True)
