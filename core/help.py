# core/help.py
import streamlit as st

HELP_MD = """
# How this app works

This app solves a **quarter-hour dispatch optimization**: given prices, technical limits, and (optionally) a battery,
it finds the **profit-maximizing** operation subject to constraints.

---

## Inputs
- **Power prices (€/MWh)** at 15-min resolution (CSV/Excel).
- **Plant parameters**: min/max load, ramps, efficiency.
- **Economics**: product price, variable costs, CO₂ price.
- **Battery (optional)**: capacity, power, efficiency, SOC limits.

---

## Outputs
- Dispatch profile (MW per 15-min).
- Methanol production (tons).
- Revenues & profit KPIs.
- Charts & CSV downloads.
- Guidance on whether a battery is required.
"""

def render_help_button(location: str = "main") -> None:
    """
    Renders a button that toggles a full 'How this app works' panel.
    Only used in the main header.
    """
    if "show_help" not in st.session_state:
        st.session_state["show_help"] = False

    if st.button("📘 How this app works", key="help_btn_main", use_container_width=True):
        st.session_state["show_help"] = not st.session_state["show_help"]

    if st.session_state["show_help"]:
        with st.expander("Close help", expanded=True):
            st.markdown(HELP_MD)
