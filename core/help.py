# core/help.py
how_it_works_md = """
### How this app works

**Input:** a quarter-hour price time series with columns `timestamp` and `price` (€/MWh, UTC or timezone-aware).

**Pipeline**
1) Load & normalize columns
2) Enforce strict 15-minute cadence (fills gaps by forward-fill)
3) Apply plant constraints (min/max, ramp, always-on)
4) Greedy dispatch: run at Pmax when price ≥ threshold (break-even), else Pmin or 0
5) Compute:
   - **Proxy profit**: Σ[(Price − Break-even) × MWh]
   - **Full MeOH economics** (if you provide MWh/t and prices)
"""

def show_help_panel(location: str = "main"):
    import streamlit as st
    with (st.sidebar if location == "sidebar" else st.container()):
        with st.expander("How this app works"):
            st.markdown(how_it_works_md)
