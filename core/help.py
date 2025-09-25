# core/help.py
import streamlit as st

HELP_MD = """
# How this app works

This app solves a **quarter-hour dispatch optimization**: given prices, technical limits, and (optionally) a battery,
it finds the **profit-maximizing** operation subject to constraints.

---

## 1) Inputs

**Power prices (€/MWh or chosen currency/MWh)**
- Upload or paste a time series at 15-minute resolution.  
- Columns supported: a single “price” column, or a datetime + price format.  
- If you only have hourly prices, the app will repeat each hour across the four 15-min slots (if enabled).

**Plant / process parameters**
- **Min/Max Power (MW)**: feasible operating window each interval.
- **Ramp limits (MW/interval)**: optional; restricts how quickly setpoints change between intervals.
- **Start/Stop penalties**: optional; costs applied when the unit turns on/off.
- **Efficiency / Yield**: used to map power to product output (for economics).

**Economics**
- **Product price (e.g., methanol €/t)** and **variable costs**.
- **Tolling mode** (optional): app computes margin under a tolling arrangement.
- Currency shown is cosmetic; optimization uses the numeric values you provide.

---

## 2) Battery (optional)

If enabled, the optimizer co-optimizes the plant and the battery.

- **Energy capacity (MWh)** and **Power (MW)**: battery size and charge/discharge limits.
- **Round-trip efficiency (%)**: overall efficiency (or split efficiency if configured).
- **Max SOC (%)**: maximum allowed state-of-charge relative to capacity.
- **Min SOC (%)**: minimum allowed state-of-charge.
- **SOC initial / final (%)**: optional targets for the first and/or last interval.
- **Price deadband (%)**: ignore arbitrage opportunities smaller than this percentage difference to reduce churn.
  - Example: deadband = 2% → tiny price swings won’t trigger charge/discharge.

> Tip: If you **don’t** want battery behavior, just disable the battery (toggle off).

---

## 3) Optimizer

We formulate a linear/mixed-integer program (via `pulp`) that maximizes **total profit**:
- **Revenue** from selling to the market (and/or product output pricing)
- **Minus** variable costs, start/stop penalties, and battery losses
- Subject to: operating bounds, ramps, SOC bounds, and inter-temporal constraints

If integer variables are enabled (e.g., on/off status), the problem is MILP; otherwise LP.

---

## 4) Outputs

- **Dispatch profile (MW)** per 15-min interval
- **Battery operation**: charge/discharge and SOC (if enabled)
- **KPIs**: total profit, energy bought/sold, operating hours, starts/stops
- **Charts**: prices vs. dispatch; SOC trajectory
- **Download**: CSV of results when enabled

---

## 5) Matrix & Portfolio

These sections will display **batch scenarios** and **portfolio aggregation** once configured.
If you see “Coming soon,” it means the feature is intentionally not yet enabled in this build.

---

## 6) Files / IO

- **Load scenario**: read a scenario from CSV/JSON (if enabled).
- **Save scenario**: export your current settings and results.

> If you removed “load/save” features for performance, this help still applies to the active UI elements.

---

## 7) Common pitfalls

- **Missing dependencies**: ensure `requirements.txt` includes: `streamlit`, `pandas`, `numpy`, `plotly`, `PyYAML`, `pulp`.
- **Timezone / parsing**: make sure your datetime column parses correctly (UTC or local consistently).
- **Stalls / lag**: very long horizons (many weeks at 15-min) can be heavy. Reduce horizon or disable integers.
- **Units**: keep prices and capacities consistent (€/MWh, MW, MWh). Profit will be in your currency.

---

**Need more?** Ping us which field is unclear and we’ll add a one-liner right here so your team has it in-app.
"""

def render_help_button(location: str = "main"):
    """
    Renders a button that toggles a full 'How this app works' panel.

    Parameters
    ----------
    location : {"main","sidebar"}
        Where to render the toggle button. "main" (default) draws it in
        the page body; "sidebar" draws it inside the sidebar.
    """
    if "show_help" not in st.session_state:
        st.session_state.show_help = False

    def _button():
        if st.button("📘 How this app works", use_container_width=True):
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
