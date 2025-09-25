# core/help.py
import streamlit as st

HELP_MD = """
# How this app works

This app solves a **quarter-hour dispatch optimization**: given prices, technical limits, and (optionally) a battery,
it finds the **profit-maximizing** operation subject to constraints.

---

## 1) Inputs
- **Power prices (€/MWh)** at 15-min resolution (CSV/Excel).
- **Plant parameters**: min/max load, ramps, efficiency.
- **Economics**: product price, variable costs, CO₂ price.
- **Battery (optional)**: capacity, power, efficiency, SOC limits.

---

## 2) Outputs
- Dispatch profile (MW per 15-min).
- Methanol production (tons).
- Revenues & profit KPIs.
- Charts & CSV downloads.
- Guidance on whether a battery is required.
"""

def render_help_button(location: str = "main") -> None:
    """
    Renders a button that toggles a full 'How this app works' panel.

    Parameters
    ----------
    location : {"main","sidebar"}
        Where to render the toggle button.
    """
    if "show_help" not in st.session_state:
        st.session_state.show_help = False

    # Assign a unique key per location
    btn_key = f"help_btn_{location}"

    def _button():
        if st.button("📘 How this app works", key=btn_key, use_container_width=True):
            st.session_state.show_help = not st.session_state.show_help

    if location == "sidebar":
        with st.sidebar:
            _button()
            if st.session_state.show_help:
                with st.expander("Close help", expanded=True):
                    st.markdown(HELP_MD)
    else:
        _button()
        if st.session_state.show_help:
            with st.expander("Close help", expanded=True):
                st.markdown(HELP_MD)
