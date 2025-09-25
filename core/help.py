# core/help.py
import streamlit as st

def render_help():
    st.title("How this app works")

    st.markdown("""
This app **maximizes profit** for a flexible plant on **15-minute power prices**.  
It decides, interval by interval, how much to run (between your min–max load), 
optionally respecting ramp limits, and applies your **economic settings** to
calculate **KPIs, cashflows and downloads**.

---

## 1) What you need to provide
- **15-min price file** (CSV or Excel).  
  The app auto-detects timestamp & price columns.  
  If not detected, please provide headers: `timestamp, price_eur_per_mwh`.

---

## 2) Inputs — Operations (Sidebar)
- **Plant capacity (MW)**  
  Nameplate power of the plant at 100% load.

- **Min load (%) / Max load (%)**  
  The allowable operating range (e.g., a plant may be ≥10% even at low prices).

- **Break-even power price (€/MWh)**  
  The floor price for “power-only” profitability. Below this, the model will not
  buy power unless you also enable economic logic that justifies it.

- **Ramp limit (MW per 15-min)** *(optional)*  
  Max change in output between consecutive intervals. Leave 0 to ignore.

- **Always on (≥ min load)**  
  Forces the plant to **never drop below min-load**. Untick if you allow 0% during low prices.

---

## 3) Inputs — Production & Economics (Sidebar)
- **Electricity per ton (MWh/t)**  
  How many MWh you need to produce one tonne of product.

- **Methanol price (€/t)**  
  Sales price of your product (if using “Full-economics” margin).

- **CO₂ price (€/t)** & **CO₂ needed (t/t)**  
  Variable CO₂ cost per tonne of product and the intensity per t of product.

- **Maintenance / SG&A / Insurance (% of revenue)**  
  Variable percentages of revenue to include in OPEX for “Full-economics”.

---

## 4) Target Margin & Price Cap
- **Margin method**
  - **Power-only (vs BE):**  
    We cap the dispatch price at `(1 − margin%) × break-even`.
  - **Full-economics:**  
    We back-solve a price cap so that the achieved margin **after** sales price,
    CO₂, and % OPEX equals your target.

- **Target margin (%)**  
  The minimum profit margin you want the dispatch to achieve.

---

## 5) Results and Downloads
- **KPIs table** summarises total energy, production (t), revenues, costs & true profit.  
- **Dispatch table** shows the interval schedule (first 200 rows).  
- **Downloads** provide full Excel and CSV of the results.

---

## 6) Tips
- If parsing fails, save your data as CSV (UTF-8) with headers `timestamp, price_eur_per_mwh`.
- Use **Always on** for assets that must maintain minimum technical load.
- Add a **ramp limit** only if your process is actually constrained (it slows optimization).
- Use **Full-economics** when you want the dispatch to respect your target project margin.
    """)

    with st.expander("Glossary", expanded=False):
        st.markdown("""
- **BE (Break-even)** — Power price at which running yields zero contribution (or as you define).
- **Price cap** — Maximum price used for dispatch, computed from your target margin.
- **True profit** — Revenue − (All variable costs incl. power, CO₂, and % OPEX).
- **Dispatch** — The power output (MW) chosen for each 15-min interval.
        """)
