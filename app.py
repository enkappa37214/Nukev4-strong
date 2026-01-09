import streamlit as st
import math

# ==========================================================
# STREAMLIT CONFIG (Must be first)
# ==========================================================
st.set_page_config(
    page_title="Nukeproof Mega v4 Calculator",
    page_icon="⚙️",
    layout="centered"
)

# ==========================================================
# COLORS / CSS
# ==========================================================
COLORS = {
    "petrol_blue": "#005F60",
    "matte_black": "#0E1117",
    "panel_grey": "#262730",
    "brushed_silver": "#FAFAFA",
    "gold_bronze": "#D4AF37",
    "slate_grey": "#4A4D4F"
}

st.markdown(f"""
<style>
/* ================= GLOBAL ================= */
.stApp {{
    background-color: {COLORS['matte_black']};
    color: {COLORS['brushed_silver']};
}}

h1, h2, h3, h4, h5, h6 {{
    color: {COLORS['petrol_blue']} !important;
}}

p, label, span, div {{
    color: {COLORS['brushed_silver']};
}}

/* ================= METRICS ================= */
div[data-testid="stMetricValue"] {{
    color: {COLORS['gold_bronze']} !important;
    font-weight: 700;
}}

div[data-testid="stMetricDelta"] {{
    color: {COLORS['brushed_silver']} !important;
    font-size: 0.85em;
}}

div[data-testid="stMetricLabel"] {{
    color: #A0A0A0 !important;
}}

/* ================= INPUTS ================= */
.stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input,
.stTextInput input {{
    background-color: {COLORS['panel_grey']} !important;
    color: {COLORS['brushed_silver']} !important;
    border: 1px solid {COLORS['slate_grey']};
}}

/* ================= POPUPS & MENUS ================= */
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div {{
    background-color: {COLORS['panel_grey']} !important;
}}

div[data-baseweb="popover"] span,
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] p,
div[data-baseweb="popover"] button,
div[data-baseweb="popover"] a {{
    color: {COLORS['brushed_silver']} !important;
}}

li[role="option"]:hover,
li:hover {{
    background-color: {COLORS['slate_grey']} !important;
}}

/* ================= SETTINGS MODAL ================= */
div[role="dialog"] {{
    background-color: {COLORS['panel_grey']} !important;
    color: {COLORS['brushed_silver']} !important;
}}

div[role="dialog"] h2,
div[role="dialog"] label,
div[role="dialog"] span,
div[role="dialog"] p,
div[role="dialog"] button {{
    color: {COLORS['brushed_silver']} !important;
}}

/* ================= SLIDERS & BUTTONS ================= */
.stSlider [data-baseweb="slider"] {{
    color: {COLORS['petrol_blue']};
}}

.stButton > button {{
    background-color: {COLORS['petrol_blue']};
    color: white !important;
    border: none;
}}

/* ================= EXPANDERS ================= */
.streamlit-expanderHeader {{
    background-color: {COLORS['panel_grey']};
    color: {COLORS['brushed_silver']} !important;
    font-weight: 600;
    border: 1px solid {COLORS['slate_grey']};
}}

/* ================= HEADER BAR ================= */
header[data-testid="stHeader"] {{
    background-color: {COLORS['matte_black']} !important;
}}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# SYSTEM CONFIGURATION
# ==========================================================
CONFIG = {
    "BIKE_MASS_KG": 15.11,
    "UNSPRUNG_MASS_KG": 4.27,
    "SHOCK_STROKE_MM": 62.5,
    "REAR_BIAS": 0.65,
    "LEV_RATIO_START": 2.90,
    "LEV_RATIO_COEFF": 0.00816,
    "SPRING_MIN": 390,
    "SPRING_MAX": 430,
    "REBOUND_LBS_PER_CLICK": 35,
    "BASE_FORK_PSI": 63.0,
    "FORK_PSI_PER_KG": 0.85,
    "SAG_PITCH_GAIN": 0.75,
    "NEG_SPRING_THRESHOLD": 70,
    "NEG_SPRING_GAIN": 0.6,
    "BRAKE_SUPPORT_GAIN": 1.0,
    "BRAKE_SUPPORT_MAX": 3,
    "BASE_FRONT_PSI": 23.0,
    "BASE_REAR_PSI": 26.0,
    "PSI_PER_KG": 0.25
}

SAG_DEFAULTS = {
    "Flow / Jumps": 30,
    "Dynamic": 31,
    "Alpine": 32,
    "Trail": 33,
    "Steep / Tech": 34,
    "Plush": 35,
}

# ==========================================================
# LOGIC FUNCTIONS (UNCHANGED)
# ==========================================================
def recommend_neopos(weight, style):
    base = 0
    if style in ["Alpine", "Steep / Tech"]:
        base += 2
    if style == "Plush":
        base -= 1
    if weight > 75:
        base += 1
    if weight < 70:
        base -= 1
    return max(0, min(4, base))


def get_fork_baseline(style, is_rec):
    if is_rec or style == "Plush":
        return "Bronze", 12, 12, -1
    if style in ["Flow / Jumps", "Dynamic"]:
        return "Gold", 10, 11, 0
    if style in ["Alpine", "Steep / Tech"]:
        return "Purple", 8, 10, 2
    return "Bronze", 11, 11, 0


def calculate_physics(weight, style, weather, is_rec, neopos_val):
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * (target_sag / 100)

    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2) * sag_mm

    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)

    if raw_rate < CONFIG["SPRING_MIN"]:
        spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]:
        spring_rate = CONFIG["SPRING_MAX"]
    else:
        spring_rate = 5 * round(raw_rate / 5)

    actual_sag = ((sprung_lbs * lr_mean) / spring_rate) * 25.4 / CONFIG["SHOCK_STROKE_MM"] * 100
    sag_error = actual_sag - target_sag

    shock_lsr = max(-13, min(0, -10 + round((spring_rate - 400) / CONFIG["REBOUND_LBS_PER_CLICK"])))
    shock_lsc = max(-17, min(0, -9))

    fork_psi = (
        CONFIG["BASE_FORK_PSI"]
        + (weight - 72) * CONFIG["FORK_PSI_PER_KG"]
        + sag_error * CONFIG["SAG_PITCH_GAIN"]
    )

    f_valve, base_lsc, base_lsr, brake_bias = get_fork_baseline(style, is_rec)
    brake_clicks = min(CONFIG["BRAKE_SUPPORT_MAX"], brake_bias)

    f_lsc = max(2, min(12, base_lsc - brake_clicks))
    f_lsr = max(2, min(19, base_lsr - round((fork_psi - 66) / 5)))

    return {
        "spring_rate": spring_rate,
        "raw_rate": raw_rate,
        "target_sag": target_sag,
        "actual_sag": actual_sag,
        "sag_error": sag_error,
        "shock_lsc": abs(shock_lsc),
        "shock_lsr": abs(shock_lsr),
        "fork_psi": fork_psi,
        "fork_valve": f_valve,
        "fork_lsc": abs(f_lsc),
        "fork_lsr": abs(f_lsr),
        "neopos": neopos_val,
    }
