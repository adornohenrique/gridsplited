# core/help.py
import streamlit as st

HELP_MD = """
# 📘 How this app works

This tool helps you decide **when and how hard to run your plant** (every 15 minutes) to **maximize profit**, not just output.  
It uses your **price file**, **plant constraints**, and **economics**, and can optionally add a **battery** strategy.

---

## 🚀 Quick start (2 minutes)

1. **Upload your price file** (CSV or Excel) in the sidebar.  
   The app detects **timestamp** and **price** automatically.
2. Set **Plant — Operations**: Capacity, Min/Max load, Ramp limit, and “Always on”.
3. Set **Production & Economics**: MWh/t, MeOH price, CO₂ price, CO₂ need, and OPEX % (Maintenance, SG&A, Insurance).
4. Choose **Target margin** method:
   - **Power-only (vs BE):** target margin on top of your break-even €/MWh.
   - **Full-economics:** uses MeOH revenue & variable costs to compute a €/MWh floor.
5. (Optional) Enable **Battery** and fill its fields (capacity, power, efficiencies, price bands).
6. Click **Run Optimization**.  
   Review the **KPIs**, **tables**, **charts**, and **download** the results.

---

## 📥 Inputs (sidebar)

### 1) Operations
- **Plant capacity (MW):** your nameplate or operational cap.
- **Min/Max load (%):** flexibility range (e.g., 10%–100%).
- **Break-even (€/MWh):** your power cost at zero margin.  
  *Tip:* Enable **Benchmark** below if you want the app to compute a BE from MeOH/CO₂/Water/Margin.
- **Ramp limit (MW/15-min):** max change between consecutive steps.
- **Always on:** if checked, the plant never goes below **Min load**.

### 2) Production & Economics
- **Electricity per ton (MWh/t):** intensity to convert MWh → tonnes MeOH.
- **Methanol price (€/t):** revenue per tonne.
- **CO₂ price (€/t)** and **CO₂ needed (t/t):** variable CO₂ cost per tonne.
- **Maintenance / SG&A / Insurance (% of revenue):** variable OPEX adders.

### 3) Optional — Benchmark & OPEX
- **Water cost (€/t)** and **Trader margin (% of MeOH revenue):** used by the **Benchmark formula**:  
  \n*(pMeOH − CO₂_need×pCO₂ − water − margin%×pMeOH) / (MWh/t)*  
- **Use Benchmark as Break-even:** toggles the app to replace your BE with the computed one.

### 4) Target Margin control
- **Margin method:**  
  - **Power-only (vs BE):** price floor = (1 − target%) × Break-even.  
  - **Full-economics:** price floor derived from MeOH revenue minus variable costs.
- **Target margin (%):** your required margin.

### 5) Battery (optional)
- **Energy (MWh), Charge/Discharge power (MW).**
- **Efficiencies** (charge & discharge).
- **SOC limits (0–1)**: minimum and maximum state of charge as fractions.
- **Charge when price ≤** / **Discharge when price ≥**: simple price bands.
- **Degradation (€/MWh throughput)**: optional cost per cycled energy.

---

## 🧠 What the optimizer does

### Step 1 — Build a **price floor** (threshold)
From your **Target margin** and chosen **method**, the app computes a price floor (€/MWh).  
**Interpretation:** *Only run more when the market price ≥ this threshold (and never below break-even).*

### Step 2 — Quarter-hour **dispatch**
For each 15-min interval:
- Apply **Min/Max load**, **Ramp limit**, and **Always on**.
- Compare market price vs **threshold**.  
  - If price is high → run higher (toward Max load).  
  - If price is low → run lower (down to Min or 0, per “Always on”).
- Compute **economics per step**:
  - **Power cost** = price × energy.
  - **Production (t)** = energy ÷ (MWh/t).
  - **Revenue** = production × MeOH price.
  - **CO₂ cost** = production × CO₂ need × CO₂ price.
  - **Other OPEX** = (Maint + SG&A + Insurance) × revenue.
  - **Profit** = revenue − power − CO₂ − other OPEX.

### Step 3 — Battery (if enabled)
A robust **price-band** strategy runs in parallel:
- **Charge** when price ≤ low band; **Discharge** when price ≥ high band.
- Obeys **power**, **energy**, **efficiency**, and **SOC** limits.
- Battery **profit** = discharge revenue − charge cost − degradation.

---

## 📊 Reading the results

- **KPIs (project overview):**  
  Energy, weighted avg price, total power cost, total tonnes, revenue, CO₂ cost, OPEX, **profit**.
- **Battery KPIs (if enabled):**  
  Profit, energy charged/discharged, degradation cost, average/final SOC.
- **Total project profit** = plant profit **+** battery profit.
- **Tables:** the first 200 rows of dispatch and (if enabled) battery timeline.
- **Charts (if enabled in the app):**
  - Price vs Dispatch (MW)
  - Daily Profit
  - Battery SOC over time
- **Downloads:**  
  - `dispatch_plan.csv` and/or Excel  
  - `battery_schedule.csv` (if battery enabled)

---

## 💡 Tips

- **Target margin up → run fewer hours** but chase better prices.  
- **Always on** keeps a floor (e.g., 10%) even in low-price periods.  
- If your file isn’t exactly 15-min data, the app will warn you.
- Use **Scenario Download / Load** (if enabled) to save and share exact inputs.

---

## 🛠️ Troubleshooting

- **“Please upload a CSV/Excel…”** — Upload a file with **timestamp** and **price** columns.  
  Common names work (e.g., `time`, `datetime`, `lmp`, `€/MWh`).
- **Excel error (“openpyxl”)** — Make sure `openpyxl` is in `requirements.txt` and redeploy.
- **Logo not showing** — Place `logo.png` in the same folder as `app.py`.
- **Streamlit generic error** — Click **Manage app → Logs** to see the real traceback.  
  Usual causes: a typo in imports, missing dependency, or wrong Python version.

---

## ❓FAQ

**Q: Power-only vs Full-economics — which should I use?**  
**A:** Power-only is simpler and uses your break-even directly. Full-economics is more complete; it converts product revenue & variable costs into a €/MWh floor using your MWh/t.

**Q: Where do fixed costs (capex, fixed O&M) go?**  
**A:** They’re not explicitly modeled. You can reflect them by increasing the **Target margin** or adding them into OPEX % if they scale with production.

**Q: Do you model start-up costs or min up/down times?**  
**A:** Not in the basic rule. We limit ramping and min load. For full unit-commitment behavior, ask us about a MILP version.

**Q: Battery bands feel simple — can I co-optimize plant + battery?**  
**A:** Yes, a MILP co-optimization can replace the band heuristic. It’s heavier but yields the best combined schedule.

---

**That’s it!**  
Upload prices → set constraints & economics → pick margin method → (optional) battery → **Run** → read KPIs and download the schedules.
"""

def show_help_panel():
    """
    Renders a button that toggles a full help panel.
    """
    if "show_help" not in st.session_state:
        st.session_state.show_help = False

    cols = st.columns([1, 1, 1, 1, 1])
    with cols[-1]:
        if st.button("📘 How this app works", use_container_width=True):
            st.session_state.show_help = not st.session_state.show_help

    if st.session_state.show_help:
        with st.expander("Close help", expanded=True):
            st.markdown(HELP_MD)
