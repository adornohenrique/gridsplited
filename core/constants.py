# core/constants.py

DEFAULTS = {
    # Plant operations
    "PLANT_CAP_MW": 20.0,
    "MIN_LOAD_PCT": 10.0,
    "MAX_LOAD_PCT": 100.0,
    "BREAK_EVEN_EUR_MWH": 50.0,
    "RAMP_LIMIT_MW": 2.0,
    "ALWAYS_ON": True,

    # Production & economics
    "MWH_PER_TON": 11.0,
    "MEOH_PRICE": 1000.0,
    "CO2_PRICE": 40.0,
    "CO2_INTENSITY": 1.375,
    "MAINT_PCT": 3.0,
    "SGA_PCT": 2.0,
    "INS_PCT": 1.0,

    # Margin control
    "TARGET_MARGIN_PCT": 30.0,
    "MARGIN_METHOD": "Power-only (vs BE)",

    # Battery defaults (new)
    "BATTERY_ENERGY_MWH": 40.0,    # capacity
    "BATTERY_POWER_MW": 10.0,      # max charge/discharge
    "BATTERY_EFF_CHG": 0.95,       # charging efficiency (fraction)
    "BATTERY_EFF_DIS": 0.95,       # discharging efficiency (fraction)
    "SOC_INIT_PCT": 50.0,          # initial state of charge (% of capacity)
    "SOC_MIN_PCT": 10.0,           # min allowed SOC
    "SOC_MAX_PCT": 95.0,           # max allowed SOC
    "DEADBAND_FRAC": 0.05,         # 5% deadband around price cap to reduce chatter
}
