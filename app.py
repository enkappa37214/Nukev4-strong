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
# COLORS
# ==========================================================
COLORS = {
    "petrol_blue": "#005F60",
    "matte_black": "#0E1117",
    "panel_grey": "#262730",
    "brushed_silver": "#FAFAFA",
    "gold_bronze": "#D4AF37",
    "slate_grey": "#4A4D4F"
}

# ==========================================================
# CSS (SAFE STREAMLIT OVERRIDE)
# ==========================================================
st.markdown(f"""
<style>
/* ===============================
   APP BACKGROUND
================================ */
.stApp {{
    background-color: {COLORS['matte_black']};
}}

/* ===============================
   HEADERS ONLY
================================ */
h1, h2, h3, h4, h5, h6 {{
    color: {COLORS['petrol_blue']} !important;
}}

/* ===============================
   METRICS
================================ */
div[data-testid="stMetricValue"] {{
    color: {COLORS['gold_bronze']} !important;
    font-weight: 700;
}}

div[data-testid="stMetricLabel"] {{
    color: #A0A0A0 !important;
}}

div[data-testid="stMetricDelta"] {{
    color: {COLORS['brushed_silver']} !important;
    font-size: 0.85em;
}}

/* ===============================
   INPUT WIDGETS
================================ */
.stSelectbox div[data-baseweb="select"] > div,
.stNumberInput input {{
    background-color: {COLORS['panel_grey']} !important;
    color: {COLORS['brushed_silver']} !important;
    border: 1px solid {COLORS['slate_grey']};
}}

/* ===============================
   DROPDOWNS
================================ */
ul[data-baseweb="menu"] {{
    background-color: {COLORS['panel_grey']} !important;
}}

li[role="option"] {{
    background-color: {COLORS['panel_grey']} !important;
    color: {COLORS['brushed_silver']} !important;
}}

li[role="option"]:hover {{
    background-color: {COLORS['slate_grey']} !important;
}}

/* ===============================
   EXPANDERS
================================ */
.streamlit-expanderHeader {{
    background-color: {COLORS['panel_grey']};
    border: 1px solid {COLORS['slate_grey']};
    font-weight: 600;
}}

/* ===============================
   BUTTONS
================================ */
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
# LOGIC
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

# ==========================================================
# UI
# ==========================================================
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.7")

col1, col2 = st.columns(2)
with col1:
    weight = st.number_input("Rider Weight (kg)", 50.0, 110.0, 72.0, 0.5)
with col2:
    style = st.selectbox("Riding Style", list(SAG_DEFAULTS.keys()), index=3)

st.markdown("### Neopos Tokens")
auto_np = recommend_neopos(weight, style)
neopos = st.select_slider(
    f"Auto recommended: {auto_np}",
    options=["Auto", 0, 1, 2, 3, 4],
    value="Auto"
)

st.success("✅ App rendered correctly — CSS fixed")
