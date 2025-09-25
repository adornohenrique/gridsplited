# core/ui.py
import streamlit as st

def display_logo(path: str):
    try:
        st.image(path, width=220)
    except Exception:
        pass

def how_it_works_expander():
    st.markdown("### How this app works")
    with st.expander("Open details"):
        st.markdown(
            """
**Input:** quarter-hour price series with columns `timestamp` and `price` (€/MWh).  
**Pipeline:**  
1) Load & normalize columns  
2) Enforce strict 15-minute cadence (fills gaps with forward-fill)  
3) Apply plant constraints (min/max, ramp, always-on)  
4) Greedy dispatch: run at Pmax when price ≥ threshold (break-even), else Pmin or 0  
5) Economics:  
   - **Power proxy**: Σ[(Price − Break-even) × MWh]  
   - **Full MeOH**: Revenue (t × €/t) − Power − CO₂ − (Maint+SG&A+Ins) − Water − Other OPEX
            """
        )

def show_kpis(kpis: dict):
    cols = st.columns(3)
    cols[0].metric("Total MWh", f"{kpis['total_mwh']:,.0f}")
    cols[1].metric("Total tons MeOH", f"{kpis['total_tons']:,.0f}")
    cols[2].metric("Power cost (€/MWh avg)", f"{kpis['avg_price']:,.2f}")

    st.markdown("#### Financials")
    c = st.columns(3)
    c[0].metric("Revenue (MeOH)", f"€{kpis['revenue_meoh']:,.0f}")
    c[1].metric("Power cost", f"€{kpis['power_cost']:,.0f}")
    c[2].metric("CO₂ cost", f"€{kpis['co2_cost']:,.0f}")

    c = st.columns(3)
    c[0].metric("Maint + SG&A + Ins", f"€{kpis['overheads']:,.0f}")
    c[1].metric("Other OPEX", f"€{kpis['other_opex']:,.0f}")
    c[2].metric("EBITDA (full)", f"€{kpis['ebitda_full']:,.0f}")

    st.markdown("#### Proxy profit (power only)")
    st.metric("Σ[(Price − Break-even) × MWh]", f"€{kpis['profit_proxy']:,.0f}")
