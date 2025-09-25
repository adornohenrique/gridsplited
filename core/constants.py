# core/constants.py

DEFAULTS = {
    # ---------- Plant & dispatch ----------
    "PLANT_CAP_MW": 20.0,
    "MIN_LOAD_PCT": 10.0,
    "MAX_LOAD_PCT": 100.0,
    "BREAK_EVEN_EUR_MWH": 50.0,
    "RAMP_LIMIT_MW": 2.0,
    "ALWAYS_ON": True,     # if True, never goes below min load

    # ---------- Production & economics ----------
    "MWH_PER_TON": 11.0,   # electricity per ton MeOH
    "MEOH_PRICE": 1000.0,  # €/t
    "CO2_PRICE": 40.0,     # €/t
    "CO2_INTENSITY": 1.375,# t CO2 per t MeOH
    "MAINT_PCT": 3.0,      # % of revenue
    "SGA_PCT": 2.0,
    "INS_PCT": 1.0,

    # ---------- Optional: benchmark break-even helper ----------
    "WATER_COST_T": 7.3,         # €/t
    "TRADER_MARGIN_PCT_UI": 10.0,# % of MeOH revenue for benchmark only
    "OTHER_OPEX_T": 0.0,

    # ---------- Target margin control ----------
    "TARGET_MARGIN_PCT": 30.0,   # desired margin %
    "MARGIN_METHOD_DEFAULT": "Power-only (vs BE)",  # or "Full-economics"

    # ---------- Battery defaults (optional section) ----------
    "BATTERY_ENABLED": False,
    "BATT_CAP_MWH": 10.0,
    "BATT_P_CHARGE_MW": 5.0,
    "BATT_P_DISCHARGE_MW": 5.0,
    "BATT_ETA_CHARGE": 0.95,
    "BATT_ETA_DISCHARGE": 0.95,
    "BATT_SOC_INIT_PCT": 50.0,
    "BATT_SOC_MIN_PCT": 5.0,
    "BATT_SOC_MAX_PCT": 95.0,
    "BATT_LOW_PRICE": 40.0,     # charge when price <= low
    "BATT_HIGH_PRICE": 80.0,    # discharge when price >= high
    "BATT_DEGR_EUR_PER_MWH": 0.0,
    "BATT_ENFORCE_FINAL_SOC": False,
}
