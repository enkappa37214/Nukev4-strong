import streamlit as st
import math

# ==========================================================
# STREAMLIT CONFIG (Must be first)
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4 Calculator", page_icon="⚙️", layout="centered")

# ==========================================================
# COLORS / CSS (HARDENED FOR DROPDOWNS)
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
    /* 1. FORCE DARK BACKGROUND (Global) */
    .stApp {{
        background-color: {COLORS['matte_black']};
        color: {COLORS['brushed_silver']};
    }}
    
    /* 2. HEADERS & TEXT */
    h1, h2, h3, h4, h5, h6 {{ color: {COLORS['petrol_blue']} !important; }}
    p, label, span, div {{ color: {COLORS['brushed_silver']}; }}
    
    /* 3. METRICS (Gold Accents) */
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

    /* 4. INPUTS: SELECTBOX & NUMBER INPUT (Collapsed State) */
    .stSelectbox div[data-baseweb="select"] > div, 
    .stNumberInput input, 
    .stTextInput input {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
        border: 1px solid {COLORS['slate_grey']};
    }}
    
    /* 5. INPUTS: DROPDOWN MENUS (The Light Mode Fix) */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul {{
        background-color: {COLORS['panel_grey']} !important;
        color: {COLORS['brushed_silver']} !important;
    }}
    
    /* Options in the list */
    li[role="option"] {{
        color: {COLORS['brushed_silver']} !important;
    }}
    
    /* Selected/Hover option */
    li[aria-selected="true"], li[role="option"]:hover {{
        background-color: {COLORS['slate_grey']} !important;
    }}

    /* 6. SLIDERS & BUTTONS */
    .stSlider [data-baseweb="slider"] {{
        color: {COLORS['petrol_blue']};
    }}
    .stButton>button {{
        background-color: {COLORS['petrol_blue']};
        color: white !important;
        border: none;
    }}

    /* 7. EXPANDERS */
    .streamlit-expanderHeader {{
        background-color: {COLORS['panel_grey']};
        color: {COLORS['brushed_silver']} !important;
        font-weight: 600;
        border: 1px solid {COLORS['slate_grey']};
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
    # Returns only the color name for display
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
    actual_sag_pct = (actual_sag_mm / CONFIG["SHOCK_STROKE_MM"]) * 100
    sag_error = actual_sag_pct - target_sag

    # Shock Damping
    shock_reb = -10 + round((spring_rate - 400) / CONFIG["REBOUND_LBS_PER_CLICK"])
    comp_offset = 0
    if style in ["Alpine", "Steep / Tech"]: comp_offset = 2
    elif style == "Plush": comp_offset = -2
    shock_comp = -9 + comp_offset
    if weather == "Cold": shock_reb -= 1; shock_comp -= 1
    if weather == "Rain / Wet": shock_comp -= 2
    shock_reb = max(-13, min(0, shock_reb))
    shock_comp = max(-17, min(0, shock_comp))

    # Fork PSI
    fork_psi = CONFIG["BASE_FORK_PSI"]
    fork_psi += (weight - 72) * CONFIG["FORK_PSI_PER_KG"]
    fork_psi += sag_error * CONFIG["SAG_PITCH_GAIN"]
    if weight < CONFIG["NEG_SPRING_THRESHOLD"]:
        fork_psi -= (CONFIG["NEG_SPRING_THRESHOLD"] - weight) * CONFIG["NEG_SPRING_GAIN"]

    # Fork Damping
    f_valve, base_lsc, base_lsr, brake_bias = get_fork_baseline(style, is_rec)
    brake_clicks = min(CONFIG["BRAKE_SUPPORT_MAX"], brake_bias * CONFIG["BRAKE_SUPPORT_GAIN"])
    
    f_lsc = base_lsc - brake_clicks 
    
    reb_correction = round((fork_psi - 66) / 5)
    f_lsr = base_lsr - reb_correction
    if weather == "Cold": f_lsc += 1; f_lsr += 1
    f_lsc = max(2, min(12, int(f_lsc)))
    f_lsr = max(2, min(19, int(f_lsr)))

    # Tyres
    t_mod = (weight - 72) * CONFIG["PSI_PER_KG"]
    f_psi_tyre = CONFIG["BASE_FRONT_PSI"] + t_mod
    r_psi_tyre = CONFIG["BASE_REAR_PSI"] + t_mod
    if weather == "Rain / Wet":
        f_psi_tyre -= 1.5; r_psi_tyre -= 1.5

    return {
        "sys_mass": sys_mass, "lr_mean": lr_mean, "target_sag": target_sag,
        "spring_rate": spring_rate, "raw_rate": raw_rate, "actual_sag": actual_sag_pct,
        "sag_error": sag_error, "shock_lsc": abs(shock_comp), "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi, "fork_valve": f_valve, "fork_lsc": abs(f_lsc), "fork_lsr": abs(f_lsr),
        "brake_clicks": brake_clicks, "neopos_val": neopos_val,
        "f_tyre": f_psi_tyre, "r_tyre": r_psi_tyre
    }

# ==========================================================
# UI
# ==========================================================
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.4")

# Inputs
col1, col2 = st.columns(2)
with col1:
    weight = st.number_input("Rider Weight (kg)", min_value=50.0, max_value=110.0, value=72.0, step=0.5)
    is_rec = st.toggle("Recovery Mode", value=False)
with col2:
    style = st.selectbox("Riding Style", options=list(SAG_DEFAULTS.keys()), index=3)
    weather = st.selectbox("Weather", options=["Standard", "Cold", "Rain / Wet"])

# Neopos slider
st.markdown("### Neopos Tokens")
neopos_auto = recommend_neopos(weight, style)
neopos_val = st.select_slider(
    "Auto Recommended: {} | Override 0–4".format(neopos_auto),
    options=["Auto", 0, 1, 2, 3, 4],
    value="Auto"
)
neopos_val_final = neopos_auto if neopos_val == "Auto" else int(neopos_val)

# Calculate
data = calculate_physics(weight, style, weather, is_rec, neopos_val_final)

st.divider()

# Rear Section
with st.expander("Rear Suspension (Formula Mod)", expanded=True):
    col_a, col_b = st.columns(2)
    col_a.metric("Spring Rate", f"{data['spring_rate']} lb", delta=f"Raw: {data['raw_rate']:.1f} lb")
    col_b.metric("Target Sag", f"{data['target_sag']}%", f"Act: {data['actual_sag']:.1f}%")
    st.caption(f"Sag Error: {data['sag_error']:+.1f}% | Pitch correction active")
    st.markdown("---")
    col_c, col_d = st.columns(2)
    col_c.metric("Shock LSC", f"{data['shock_lsc']} OUT")
    col_d.metric("Shock LSR", f"{data['shock_lsr']} OUT")

# Fork Section
with st.expander("Fork (Selva V)", expanded=True):
    # Row 1: Air Spring & Hardware (PSI, Valve, Neopos)
    c1, c2, c3 = st.columns(3)
    c1.metric("Air Pressure", f"{data['fork_psi']:.1f} PSI", delta="±1.0 PSI")
    c2.metric("CTS Valve", data['fork_valve'])
    c3.metric("Neopos", f"{data['neopos_val']}") 
    
    st.markdown("---")
    
    # Row 2: Damping (Knobs)
    d1, d2 = st.columns(2)
    d1.metric("Fork LSC", f"{data['fork_lsc']} OUT", help=f"12 Clicks Max. Bias: {data['brake_clicks']}")
    d2.metric("Fork LSR", f"{data['fork_lsr']} OUT", help="19 Clicks Max")

# Tyres
with st.expander("Tyres (SuperGravity)", expanded=True):
    col_a, col_b = st.columns(2)
    col_a.metric("Front", f"{data['f_tyre']:.1f} PSI")
    col_b.metric("Rear", f"{data['r_tyre']:.1f} PSI")

st.caption(f"System Mass: {data['sys_mass']:.1f} kg | Mean Leverage: {data['lr_mean']:.3f}")
