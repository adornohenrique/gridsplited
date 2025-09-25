# core/constants.py
import yaml
from pathlib import Path

# Load YAML defaults if present
_cfg = {}
_cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
if _cfg_path.exists():
    _cfg = yaml.safe_load(_cfg_path.read_text()) or {}

DEFAULTS = _cfg.get("defaults", {
    "PLANT_CAP_MW": 20.0,
    "MIN_LOAD_PCT": 10.0,
    "MAX_LOAD_PCT": 100.0,
    "BREAK_EVEN_EUR_MWH": 50.0,
    "RAMP_LIMIT_MW": 2.0,
    "ALWAYS_ON": True,

    "MWH_PER_TON": 11.0,
    "MEOH_PRICE": 1000.0,
    "CO2_PRICE": 40.0,
    "CO2_INTENSITY": 1.375,
    "MAINT_PCT": 3.0,
    "SGA_PCT": 2.0,
    "INS_PCT": 1.0,
    "WATER_COST_T": 7.3,
    "TRADER_MARGIN_PCT_UI": 10.0,
    "OTHER_OPEX_T": 0.0,
    "TARGET_MARGIN_PCT": 30.0,
})

UI = _cfg.get("ui", {"logo": "logo.png", "theme": "dark"})
BATTERY_DEFAULTS = _cfg.get("battery_defaults", {})
