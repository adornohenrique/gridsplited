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

    Parameters
    ----------
    location : {"main","sidebar"}
        Where to render the toggle button.
    """
    # Separate session state per location
    state_key = f"show_help_{location}"
    if state_key not in st.session_state:
        st.session_state[state_key] = False

    # Unique key for the button widget
    btn_key = f"help_btn_{location}"

    def _button():
        if st.button("📘 How this app works", key=btn_key, use_container_width=True):
            st.session_state[state_key] = not st.session_state[state_key]

    if location == "sidebar":
        with st.sidebar:
            _button()
            if st.session_state[state_key]:
                with st.expander("Close help", expanded=True):
                    st.markdown(HELP_MD)
    else:
        _button()
        if st.session_state[state_key]:
            with st.expander("Close help", expanded=True):
                st.markdown(HELP_MD)
