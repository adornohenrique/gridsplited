# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from core import ui, io, economics, optimizer, constants
from core.help import show_help_panel
from core.battery import BatteryParams
from core.tolling import TollingParams, price_cap_tolling, build_tolling_timeline_and_kpis

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# -------------------------- Header --------------------------
ui.display_logo(constants.UI.get("logo", "logo.png"))
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")
show_help_panel()

# ---------------------------- Tabs ---------------------------
tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

# ======================== Inputs & Run ========================
with tabs[0]:
    params = ui.sidebar()
    st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")

    # Optional benchmark (ignored if Tolling enabled)
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

    # Dispatch threshold (price cap)
    if params.TOLLING_ENABLED:
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

    # Battery params
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

    # Tolling params
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

        # Tolling timeline/KPIs (if enabled)
        toll_timeline, toll_kpis = build_tolling_timeline_and_kpis(
            plant_results=plant_res,
            toll=toll,
            contracted_mw_cap=min(params.contracted_mw, params.plant_capacity_mw),
        )

        # Save context for other tabs (incl. matrix snapshots)
        st.session_state["last_df_prices"] = df
        st.session_state["last_results"] = plant_res
        st.session_state["last_kpis"] = plant_kpis
        st.session_state["last_bat_df"] = bat_df
        st.session_state["last_bat_kpis"] = bat_kpis
        st.session_state["last_toll_df"] = toll_timeline
        st.session_state["last_toll_kpis"] = toll_kpis
        st.session_state["last_method"] = method_tag

        # Snapshot of key inputs for matrix reuse
        st.session_state["last_params_snapshot"] = {
            "break_even": float(break_even),
            "MARGIN_METHOD": str(params.MARGIN_METHOD),
            "maint_pct": float(params.maint_pct),
            "sga_pct": float(params.sga_pct),
            "ins_pct": float(params.ins_pct),
            "mwh_per_ton": float(params.mwh_per_ton),
            "co2_price": float(params.co2_price),
            "co2_intensity": float(params.co2_intensity),
            "plant_capacity_mw": float(params.plant_capacity_mw),
            "min_load_pct": float(params.min_load_pct),
            "max_load_pct": float(params.max_load_pct),
            "ramp_limit": float(params.ramp_limit),
            "always_on": bool(params.always_on),
            "use_bench_as_break_even": bool(params.use_bench_as_break_even),
            # Tolling
            "tolling_enabled": bool(params.TOLLING_ENABLED),
            "contracted_mw": float(params.contracted_mw),
            "toll_cap_fee": float(params.toll_cap_fee),
            "toll_var_fee": float(params.toll_var_fee),
            "toll_other_mwh": float(params.toll_other_mwh),
        }

        st.success("Optimization complete. See Results / Charts / Downloads / Matrix tabs.")

# ========================= Results ==========================
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

# ========================== Charts ==========================
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

        # Price vs Dispatch
        if "dispatch_mw" in tmp.columns:
            st.plotly_chart(px.line(tmp, x="timestamp", y=[price_col, "dispatch_mw"], title="Price vs Dispatch (MW)"), use_container_width=True)
        elif "mw" in tmp.columns:
            st.plotly_chart(px.line(tmp, x="timestamp", y=[price_col, "mw"], title="Price vs Dispatch (MW)"), use_container_width=True)

        # Daily profit (product mode)
        if "true_profit_eur" in tmp.columns:
            daily = tmp.groupby(tmp["timestamp"].dt.date)["true_profit_eur"].sum().reset_index(name="profit")
            st.plotly_chart(px.bar(daily, x="timestamp", y="profit", title="Daily Profit (product mode)"), use_container_width=True)

        # Daily profit (tolling)
        if not toll_df.empty:
            daily_toll = toll_df.copy()
            daily_toll["date"] = pd.to_datetime(daily_toll["timestamp"]).dt.date
            dsum = daily_toll.groupby("date")["toll_profit_eur"].sum().reset_index()
            st.plotly_chart(px.bar(dsum, x="date", y="toll_profit_eur", title="Daily Profit (tolling mode)"), use_container_width=True)

        # Battery SOC
        if not bat_df.empty and "bat_soc" in bat_df.columns:
            st.plotly_chart(px.line(bat_df, x="timestamp", y="bat_soc", title="Battery SOC"), use_container_width=True)

# ======================== Downloads =========================
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

# =================== Matrix & Portfolio =====================
with tabs[4]:
    st.subheader("Scenario matrix (sensitivity)")
    st.caption("Uses the last uploaded price series & inputs. Run a base case first.")

    last_df = st.session_state.get("last_df_prices", None)
    snap = st.session_state.get("last_params_snapshot", None)

    if last_df is None or snap is None:
        st.info("Run a base case first in 'Inputs & Run' to seed the matrix.")
        st.stop()

    # Two sub-tabs for matrices
    mtab_product, mtab_toll = st.tabs(["🧪 Product matrix", "🧾 Tolling matrix"])

    # ---------------------- PRODUCT MATRIX ----------------------
    with mtab_product:
        if snap.get("tolling_enabled", False):
            st.warning("Product matrix uses PRODUCT mode. Disable Tolling and run a base case, then come back.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                meoh_min = st.number_input("MeOH min (€/t)", value=800.0)
                meoh_max = st.number_input("MeOH max (€/t)", value=1400.0)
            with col2:
                meoh_step = st.number_input("MeOH step", value=100.0)
                margin_min = st.number_input("Margin min (%)", value=10.0)
            with col3:
                margin_max = st.number_input("Margin max (%)", value=50.0)
                margin_step = st.number_input("Margin step", value=10.0)

            run_matrix_prod = st.button("Run product matrix")

            if run_matrix_prod:
                meoh_vals = np.arange(meoh_min, meoh_max + 0.0001, meoh_step)
                margin_vals = np.arange(margin_min, margin_max + 0.0001, margin_step)

                rows = []
                for p_meoh in meoh_vals:
                    for m_pct in margin_vals:
                        # recompute BE if benchmark was used; else keep snapshot BE
                        if snap.get("use_bench_as_break_even", False):
                            be_local = economics.benchmark_power_price(
                                p_methanol=float(p_meoh),
                                p_co2=float(snap["co2_price"]),
                                water_cost_eur_per_t=constants.DEFAULTS.get("WATER_COST_T", 7.3),
                                trader_margin_pct=constants.DEFAULTS.get("TRADER_MARGIN_PCT_UI", 10.0),
                                power_mwh_per_t=float(snap["mwh_per_ton"]),
                                co2_t_per_t=float(snap["co2_intensity"]),
                            )
                        else:
                            be_local = float(snap["break_even"])

                        cap_local, method_tag_local, err_local = economics.compute_price_cap(
                            margin_method=str(snap["MARGIN_METHOD"]),
                            target_margin_pct=float(m_pct),
                            break_even_eur_per_mwh=float(be_local),
                            maint_pct=float(snap["maint_pct"]),
                            sga_pct=float(snap["sga_pct"]),
                            ins_pct=float(snap["ins_pct"]),
                            mwh_per_ton=float(snap["mwh_per_ton"]),
                            methanol_price=float(p_meoh),
                            co2_price=float(snap["co2_price"]),
                            co2_t_per_t=float(snap["co2_intensity"]),
                        )
                        if err_local:
                            continue

                        plant_res, plant_kpis, _, _ = optimizer.run_dispatch(
                            df=last_df,
                            plant_capacity_mw=float(snap["plant_capacity_mw"]),
                            min_load_pct=float(snap["min_load_pct"]),
                            max_load_pct=float(snap["max_load_pct"]),
                            break_even_eur_per_mwh=float(be_local),
                            ramp_limit_mw_per_step=(float(snap["ramp_limit"]) if float(snap["ramp_limit"]) > 0 else None),
                            always_on=bool(snap["always_on"]),
                            dispatch_threshold_eur_per_mwh=float(cap_local),
                            mwh_per_ton=float(snap["mwh_per_ton"]),
                            methanol_price_eur_per_ton=float(p_meoh),
                            co2_price_eur_per_ton=float(snap["co2_price"]),
                            co2_t_per_ton_meoh=float(snap["co2_intensity"]),
                            maintenance_pct_of_revenue=float(snap["maint_pct"]),
                            sga_pct_of_revenue=float(snap["sga_pct"]),
                            insurance_pct_of_revenue=float(snap["ins_pct"]),
                            target_margin_fraction=float(m_pct)/100.0,
                            margin_method=str(method_tag_local),
                            battery_params=None,
                        )

                        plant_profit = plant_kpis.get("total_true_profit_eur")
                        if plant_profit is None:
                            plant_profit = plant_kpis.get("total_profit_proxy_eur", 0.0)

                        rows.append({
                            "mode": "product",
                            "methanol_price_eur_per_t": p_meoh,
                            "target_margin_pct": m_pct,
                            "break_even_eur_per_mwh": be_local,
                            "dispatch_threshold_eur_per_mwh": cap_local,
                            "total_energy_mwh": plant_kpis.get("total_energy_mwh"),
                            "total_tons": plant_kpis.get("total_tons"),
                            "total_revenue_eur": plant_kpis.get("total_methanol_revenue_eur"),
                            "total_power_cost_eur": plant_kpis.get("total_power_cost_eur"),
                            "total_co2_cost_eur": plant_kpis.get("total_co2_cost_eur"),
                            "total_opex_misc_eur": plant_kpis.get("total_opex_misc_eur"),
                            "plant_profit_eur": plant_profit,
                        })

                if len(rows) == 0:
                    st.warning("No matrix points computed (check inputs).")
                else:
                    mat_df = pd.DataFrame(rows)
                    st.session_state["last_matrix_df_product"] = mat_df

                    st.subheader("Product matrix — Results")
                    st.dataframe(mat_df)

                    try:
                        pivot = mat_df.pivot(index="methanol_price_eur_per_t",
                                             columns="target_margin_pct",
                                             values="plant_profit_eur").sort_index()
                        fig = px.imshow(pivot,
                                        labels=dict(x="Target margin (%)", y="MeOH price (€/t)", color="Profit (€)"),
                                        aspect="auto")
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        st.caption("Heatmap not available — showing table only.")

                    st.download_button("⬇️ Download product matrix CSV",
                                       data=mat_df.to_csv(index=False).encode("utf-8"),
                                       file_name="matrix_product_results.csv",
                                       mime="text/csv",
                                       use_container_width=True)

    # ----------------------- TOLLING MATRIX -----------------------
    with mtab_toll:
        if not snap.get("tolling_enabled", False):
            st.warning("Tolling matrix uses TOLLING mode. Enable Tolling and run a base case, then come back.")
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                var_min = st.number_input("Variable fee min (€/MWh)", value=max(0.0, snap.get("toll_var_fee", 0.0)))
                var_max = st.number_input("Variable fee max (€/MWh)", value=max(10.0, snap.get("toll_var_fee", 0.0) + 50.0))
            with col2:
                var_step = st.number_input("Variable fee step", value=10.0, min_value=1.0)
                margin_min_t = st.number_input("Margin min (%)", value=10.0)
            with col3:
                margin_max_t = st.number_input("Margin max (%)", value=50.0)
                margin_step_t = st.number_input("Margin step", value=10.0)

            cap_fee_fixed = st.number_input("Capacity fee (€/MW-month) — fixed for sweep", value=float(snap.get("toll_cap_fee", 0.0)))
            contracted_mw = st.number_input("Contracted MW — fixed for sweep",
                                            value=float(snap.get("contracted_mw", 0.0)),
                                            min_value=0.0,
                                            max_value=float(snap.get("plant_capacity_mw", 1e6)),
                                            step=0.5)
            other_var_cost = st.number_input("Other variable cost (€/MWh)", value=float(snap.get("toll_other_mwh", 0.0)))

            run_matrix_toll = st.button("Run tolling matrix")

            if run_matrix_toll:
                var_vals = np.arange(var_min, var_max + 0.0001, var_step)
                margin_vals_t = np.arange(margin_min_t, margin_max_t + 0.0001, margin_step_t)

                rows_t = []
                for vfee in var_vals:
                    for m_pct in margin_vals_t:
                        # Tolling price cap for dispatch
                        cap_local = price_cap_tolling(
                            target_margin_pct=float(m_pct),
                            variable_fee_eur_per_mwh=float(vfee),
                            maint_pct=float(snap["maint_pct"]),
                            sga_pct=float(snap["sga_pct"]),
                            ins_pct=float(snap["ins_pct"]),
                            other_var_cost_eur_per_mwh=float(other_var_cost),
                        )

                        plant_res, plant_kpis, _, _ = optimizer.run_dispatch(
                            df=last_df,
                            plant_capacity_mw=float(snap["plant_capacity_mw"]),
                            min_load_pct=float(snap["min_load_pct"]),
                            max_load_pct=float(snap["max_load_pct"]),
                            break_even_eur_per_mwh=float(snap["break_even"]),  # unused in tolling economics, but needed by engine
                            ramp_limit_mw_per_step=(float(snap["ramp_limit"]) if float(snap["ramp_limit"]) > 0 else None),
                            always_on=bool(snap["always_on"]),
                            dispatch_threshold_eur_per_mwh=float(cap_local),
                            mwh_per_ton=float(snap["mwh_per_ton"]),  # not used by tolling KPIs
                            methanol_price_eur_per_ton=0.0,          # don't mix with product revenue
                            co2_price_eur_per_ton=0.0,
                            co2_t_per_ton_meoh=float(snap["co2_intensity"]),
                            maintenance_pct_of_revenue=float(snap["maint_pct"]),
                            sga_pct_of_revenue=float(snap["sga_pct"]),
                            insurance_pct_of_revenue=float(snap["ins_pct"]),
                            target_margin_fraction=float(m_pct)/100.0,
                            margin_method="tolling",
                            battery_params=None,
                        )

                        # Compute tolling KPIs for this case
                        toll_tmp = TollingParams(
                            enabled=True,
                            contracted_mw=float(contracted_mw),
                            capacity_fee_eur_per_mw_month=float(cap_fee_fixed),
                            variable_fee_eur_per_mwh=float(vfee),
                            other_var_cost_eur_per_mwh=float(other_var_cost),
                            maint_pct=float(snap["maint_pct"]),
                            sga_pct=float(snap["sga_pct"]),
                            ins_pct=float(snap["ins_pct"]),
                        )
                        toll_timeline_tmp, toll_kpis_tmp = build_tolling_timeline_and_kpis(
                            plant_results=plant_res,
                            toll=toll_tmp,
                            contracted_mw_cap=float(contracted_mw),
                        )

                        rows_t.append({
                            "mode": "tolling",
                            "variable_fee_eur_per_mwh": float(vfee),
                            "target_margin_pct": float(m_pct),
                            "dispatch_threshold_eur_per_mwh": float(cap_local),
                            "contracted_mw": float(contracted_mw),
                            "capacity_fee_eur_per_mw_month": float(cap_fee_fixed),
                            "other_var_cost_eur_per_mwh": float(other_var_cost),
                            "toll_capacity_revenue_total_eur": toll_kpis_tmp.get("tolling_capacity_revenue_total_eur", 0.0),
                            "toll_variable_revenue_total_eur": toll_kpis_tmp.get("tolling_variable_revenue_total_eur", 0.0),
                            "toll_power_cost_total_eur": toll_kpis_tmp.get("tolling_power_cost_total_eur", 0.0),
                            "toll_other_var_cost_total_eur": toll_kpis_tmp.get("tolling_other_var_cost_total_eur", 0.0),
                            "toll_pct_costs_total_eur": toll_kpis_tmp.get("tolling_pct_costs_total_eur", 0.0),
                            "toll_profit_eur": toll_kpis_tmp.get("tolling_total_profit_eur", 0.0),
                        })

                if len(rows_t) == 0:
                    st.warning("No matrix points computed (check inputs).")
                else:
                    mat_t = pd.DataFrame(rows_t)
                    st.session_state["last_matrix_df_toll"] = mat_t

                    st.subheader("Tolling matrix — Results")
                    st.dataframe(mat_t)

                    # Heatmap: profit vs variable fee & margin
                    try:
                        pivot_t = mat_t.pivot(index="variable_fee_eur_per_mwh",
                                              columns="target_margin_pct",
                                              values="toll_profit_eur").sort_index()
                        fig_t = px.imshow(pivot_t,
                                          labels=dict(x="Target margin (%)", y="Variable fee (€/MWh)", color="Profit (€)"),
                                          aspect="auto")
                        st.plotly_chart(fig_t, use_container_width=True)
                    except Exception:
                        st.caption("Heatmap not available — showing table only.")

                    st.download_button("⬇️ Download tolling matrix CSV",
                                       data=mat_t.to_csv(index=False).encode("utf-8"),
                                       file_name="matrix_tolling_results.csv",
                                       mime="text/csv",
                                       use_container_width=True)
