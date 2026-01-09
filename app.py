import streamlit as st
import math

# ==========================================================
# STREAMLIT CONFIG (Must be first)
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4 Calculator", page_icon="⚙️", layout="centered")

# ==========================================================
# COLORS / CSS (THEME OVERRIDE)
# ==========================================================
COLORS = {
    "petrol_blue": "#005F60",
    "matte_black": "#0E1117",  # Deepest grey/black
    "panel_grey": "#262730",   # Widget background
    "brushed_silver": "#FAFAFA", # High contrast text
    "gold_bronze": "#D4AF37",
    "slate_grey": "#4A4D4F"
}

st.markdown(f"""
<style>
    /* 1. FORCE DARK APP BACKGROUND */
    .stApp {{
        background-color: {COLORS['matte_black']};
        color: {COLORS['brushed_silver']};
    }}
    
    /* 2. TEXT & HEADERS */
    h1, h2, h3, h4, h5, h6 {{ color: {COLORS['petrol_blue']} !important; }}
    p, label, span, div {{ color: {COLORS['brushed_silver']}; }}
    
    /* 3. METRICS */
    div[data-testid="stMetricValue"] {{
        color: {COLORS['gold_bronze']} !important;
        font-weight: 700;
    }}
    div[data-testid="stMetricDelta"] {{
        color: {COLORS['brushed_silver']} !important;
        font-size: 0.9em;
    }}
    div[data-testid="stMetricLabel"] {{
        color: #A0A0A0 !important; 
    }}

    /* 4. INPUT WIDGETS (Collapsed) */
    .stSelectbox div[data-baseweb="select"] > div, 
    .stNumberInput input, 
    .stTextInput input {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
        border: 1px solid {COLORS['slate_grey']};
    }}

    /* 5. DROPDOWN MENUS (The Fix) */
    /* Target the list container directly */
    ul[data-baseweb="menu"] {{
        background-color: {COLORS['panel_grey']} !important;
    }}
    
    /* Target the individual items in the list */
    li[role="option"] {{
        color: {COLORS['brushed_silver']} !important;
        background-color: {COLORS['panel_grey']} !important;
    }}
    
    /* Target text inside the options */
    li[role="option"] div, li[role="option"] span {{
        color: {COLORS['brushed_silver']} !important;
    }}
    
    /* Hover state for options */
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {{
        background-color: {COLORS['slate_grey']} !important;
    }}

    /* 6. HAMBURGER MENU & SETTINGS (The Fix) */
    ul[data-testid="main-menu-list"] {{
        background-color: {COLORS['panel_grey']} !important;
    }}
    ul[data-testid="main-menu-list"] span,
    ul[data-testid="main-menu-list"] div,
    ul[data-testid="main-menu-list"] p {{
        color: {COLORS['brushed_silver']} !important;
    }}

    /* 7. MODALS (Settings Window) */
    div[role="dialog"] {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
    }}
    div[role="dialog"] h2, div[role="dialog"] label {{
        color: {COLORS['brushed_silver']} !important;
    }}
    
    /* 8. SLIDERS & BUTTONS */
    .stSlider [data-baseweb="slider"] {{
        color: {COLORS['petrol_blue']};
    }}
    .stButton>button {{
        background-color: {COLORS['petrol_blue']};
        color: white !important;
        border: none;
    }}

    /* 9. EXPANDERS */
    .streamlit-expanderHeader {{
        background-color: {COLORS['panel_grey']};
        color: {COLORS['brushed_silver']} !important;
        font-weight: 600;
        border: 1px solid {COLORS['slate_grey']};
    }}
    
    /* 10. HEADER BAR */
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
# LOGIC FUNCTIONS
# ==========================================================
def recommend_neopos(weight, style):
    base = 0
    if style in ["Alpine", "Steep / Tech"]: base += 2
    if style == "Plush": base -= 1
    if weight > 75: base += 1
    if weight < 70: base -= 1
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
    # Kinematics
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec
    
    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046
    
    # Integral Leverage Ratio
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm
    
    # Raw Spring Rate
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)
    
    if raw_rate < CONFIG["SPRING_MIN"]: spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]: spring_rate = CONFIG["SPRING_MAX"]
    else: spring_rate = 5 * round(raw_rate / 5)
    
    # Actual Sag & Error
    actual_sag_mm = ((sprung_lbs * lr_mean) / spring_rate) * 25.4
    actual_
