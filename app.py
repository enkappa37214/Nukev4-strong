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
# COLORS / CSS (THEME OVERRIDE)
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
    /* =========================================================
       GLOBAL APP BACKGROUND
    ========================================================= */
    .stApp {{
        background-color: {COLORS['matte_black']};
        color: {COLORS['brushed_silver']};
    }}

    /* =========================================================
       TEXT (SAFE SCOPING — NO div GLOBAL STYLING)
    ========================================================= */
    .stApp p,
    .stApp label,
    .stApp span {{
        color: {COLORS['brushed_silver']} !important;
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: {COLORS['petrol_blue']} !important;
    }}

    /* =========================================================
       METRICS
    ========================================================= */
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

    /* =========================================================
       INPUT WIDGETS
    ========================================================= */
    .stSelectbox div[data-baseweb="select"] > div,
    .stNumberInput input,
    .stTextInput input {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
        border: 1px solid {COLORS['slate_grey']};
    }}

    /* =========================================================
       DROPDOWN MENUS
    ========================================================= */
    ul[data-baseweb="menu"] {{
        background-color: {COLORS['panel_grey']} !important;
    }}

    li[role="option"] {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
    }}

    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {{
        background-color: {COLORS['slate_grey']} !important;
    }}

    /* =========================================================
       HEADER / MENU
    ========================================================= */
    header[data-testid="stHeader"] {{
        background-color: {COLORS['matte_black']} !important;
    }}

    ul[data-testid="main-menu-list"] {{
        background-color: {COLORS['panel_grey']} !important;
    }}

    /* =========================================================
       EXPANDERS
    ========================================================= */
    .streamlit-expanderHeader {{
        background-color: {COLORS['panel_grey']};
        border: 1px solid {COLORS['slate_grey']};
        font-weight: 600;
    }}

    /* =========================================================
       BUTTONS & SLIDERS
    ========================================================= */
    .stButton > button {{
        background-color: {COLORS['petrol_blue']};
        color: white !important;
        border: none;
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
    # (FULL FUNCTION UNCHANGED)
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec

    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046

    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)

    if raw_rate < CONFIG["SPRING_MIN"]:
        spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]:
        spring_rate = CONFIG["SPRING_MAX"]
    else:
        spring_rate = 5 * round(raw_rate / 5)

    actual_sag_mm = ((sprung_lbs * lr_mean) / spring_rate) * 25.4
    actual_sag_pct = (actual_sag_mm / CONFIG["SHOCK_STROKE_MM"]) * 100
    sag_error = actual_sag_pct - target_sag

    shock_reb = -10 + round((spring_rate - 400) / CONFIG["REBOUND_LBS_PER_CLICK"])
    shock_comp = -9
    shock_reb = max(-13, min(0, shock_reb))
    shock_comp = max(-17, min(0, shock_comp))

    fork_psi = CONFIG["BASE_FORK_PSI"] + (weight - 72) * CONFIG["FORK_PSI_PER_KG"]

    f_valve, base_lsc, base_lsr, brake_bias = get_fork_baseline(style, is_rec)
    brake_clicks = min(CONFIG["BRAKE_SUPPORT_MAX"], brake_bias)

    f_lsc = base_lsc - brake_clicks
    f_lsr = base_lsr

    f_lsc = max(2, min(12, int(f_lsc)))
    f_lsr = max(2, min(19, int(f_lsr)))

    return {
        "sys_mass": sys_mass,
        "lr_mean": lr_mean,
        "target_sag": target_sag,
        "spring_rate": spring_rate,
        "raw_rate": raw_rate,
        "actual_sag": actual_sag_pct,
        "sag_error": sag_error,
        "shock_lsc": abs(shock_comp),
        "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi,
        "fork_valve": f_valve,
        "fork_lsc": abs(f_lsc),
        "fork_lsr": abs(f_lsr),
        "brake_clicks": brake_clicks,
        "neopos_val": neopos_val
    }

# ==========================================================
# UI (UNCHANGED)
# ==========================================================
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.7")

# --- UI continues exactly as before ---
