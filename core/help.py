# core/help.py
import streamlit as st

HELP_MD = """
# 📘 How this app works

This app builds a **profit-maximizing dispatch plan** for your plant using **15-minute power prices**, and (optionally) runs a **battery arbitrage** on the same timeline.

---

## 1) What you provide
- **A 15-minute price file** (CSV or Excel). The app auto-detects the time and price columns.
- **Plant & operations**: Capacity (MW), min/max load (%), ramp limit (MW per 15-min), and “Always on”.
- **Economics**: Electricity per tonne (MWh/t), Methanol price (€/t), CO₂ price (€/t), CO₂ need (t/t), and % for Maintenance / SG&A / Insurance.
- **Optional Battery**: Energy capacity (MWh), charge/discharge MW, efficiencies, SoC limits, low/high price bands, and optional degradation cost (€/MWh throughput).

---

## 2) Price floor (threshold) from your margin target
The app converts your settings into a **dispatch price threshold**:
- **Power-only (vs break-even)**: Sets a floor around your break-even (€/MWh) and target margin.
- **Full-economics**: Uses product economics (MeOH revenue − CO₂ & other selected costs) ÷ (MWh/t) to get a floor in €/MWh.

> In practice: **“only run when price ≥ threshold”** (and never below break-even).

---

## 3) Plant dispatch logic (every 15 minutes)
For each interval, it:
1. Reads the market price.
2. Applies constraints: min/max load, ramp limit, and “Always on” (min load).
3. If price is **high enough**, it runs higher; otherwise it turns down (respecting limits).
4. Calculates money:
   - **Power cost** = price × energy.
   - **Production** = energy ÷ (MWh/t) → tonnes.
   - **Revenue** = tonnes × methanol price.
   - **CO₂ cost** = tonnes × CO₂ need × CO₂ price.
   - **Other OPEX** = (Maintenance + SG&A + Insurance) × revenue.
   - **Profit** = revenue − power − CO₂ − other OPEX.

---

## 4) Optional battery arbitrage
If enabled, a simple **price-band strategy** runs alongside:
- **Charge** when price ≤ *low* band.
- **Discharge** when price ≥ *high* band.
- Respects power, energy capacity, efficiencies, and SoC bounds.
- Economics: pay for charging energy, earn from discharging, subtract optional **degradation** (€/MWh throughput).

Outputs a **battery timeline** and **KPIs** (profit, revenue, cost, degradation, SoC).

---

## 5) Results you see
- **KPIs**: total energy, average price, power cost, tonnes, revenue, CO₂ cost, OPEX, plant profit.
- **Battery KPIs** (if enabled): battery profit, revenues/costs, degradation, throughput, SoC.
- **Total project profit** = **plant profit + battery profit**.
- **Tables**: first 200 rows of dispatch and (if enabled) battery timeline.
- **Downloads**:
  - Dispatch plan: Excel + CSV
  - Battery schedule: CSV (if enabled)

---

## 6) Optional “Benchmark break-even”
Checkbox can compute a break-even **€/MWh** from:
**(MeOH price − CO₂ need×CO₂ price − water − margin%×MeOH price) ÷ (MWh/t)**  
and use it as the dispatch break-even.

---

## Assumptions
- Time step = **15 minutes**.
- No start-up costs/min up-down time (ramp + min load are enforced).
- Battery uses a robust **band strategy** (not MILP/solver).
- Fixed costs (capex, fixed O&M) are not included unless you model them via margins or OPEX.

---

**Typical flow**  
1) Upload prices → 2) Set plant/economics → 3) Choose margin method & target →  
4) (Optional) Enable battery → 5) Run → 6) Read KPIs & download files.
"""

def show_help_panel():
    """
    Renders a button that toggles a full help panel.
    """
    # Toggle state
    if "show_help" not in st.session_state:
        st.session_state.show_help = False

    cols = st.columns([1, 1, 1, 1, 1])
    with cols[-1]:
        if st.button("📘 How this app works", use_container_width=True):
            st.session_state.show_help = not st.session_state.show_help

    if st.session_state.show_help:
        with st.expander("Close help", expanded=True):
            st.markdown(HELP_MD)
