# core/help.py
import streamlit as st

def render_help():
    st.title("How this app works")

    st.markdown("""
This app **maximizes profit** for a flexible plant on **15-minute power prices**.  
It chooses an interval-by-interval dispatch (between min–max load), optionally with
ramp limits, and applies your **economic settings** to compute **KPIs, cashflows, and downloads**.

---

## 1) What you provide
- **15-min price file** (CSV or Excel).  
  The app auto-detects `timestamp` & `price` columns. If it can’t, save CSV with headers:
  `timestamp, price_eur_per_mwh`.

---

## 2) Inputs — Operations (Sidebar)
- **Plant capacity (MW)** — nameplate power at 100% load.  
- **Min/Max load (%)** — allowable operating range.  
- **Break-even power price (€/MWh)** — “power-only” BE used by the Power-only margin mode.  
- **Ramp limit (MW per 15-min)** — maximum change per interval (0 = ignore).  
- **Always on (≥ min load)** — if checked, output never drops below Min load.

---

## 3) Inputs — Production & Economics
- **Electricity per ton (MWh/t)** — energy to produce one tonne.  
- **Methanol price (€/t)** — product price (used by Full-economics).  
- **CO₂ price (€/t)** & **CO₂ needed (t/t)** — variable CO₂ cost and intensity.  
- **Maintenance / SG&A / Insurance (% of revenue)** — variable % OPEX over revenue.

---

## 4) Target margin & price cap
- **Margin method**
  - **Power-only (vs BE):** price cap = `(1 − margin%) × break-even`.
  - **Full-economics:** back-solves a price cap so post-revenue margin ≥ target.
- **Target margin (%)** — your desired minimum margin.

---

## 5) Results & Downloads
- **KPIs** — energy, tons, revenue, costs, true profit.  
- **Dispatch table** — schedule per interval (first 200 rows in the UI).  
- **Downloads** — full CSV/Excel results.

**Tips**
- If parsing fails, export as CSV UTF-8 with `timestamp, price_eur_per_mwh`.
- Use **Always on** for plants that must maintain technical minimum.
- Add a **ramp limit** only if truly constrained (it slows optimization).
- Prefer **Full-economics** when you want dispatch to honor a project margin target.
    """)
