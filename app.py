import streamlit as st
import math

# ==========================================================
# STREAMLIT CONFIG (MUST BE FIRST)
# ==========================================================
st.set_page_config(
    page_title="Nukeproof Mega v4 Calculator",
    page_icon="⚙️",
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==========================================================
# COLORS (Corrected Hex Codes)
# ==========================================================
COLORS = {
    "petrol_blue": "#005F60",
    "matte_black": "#1A1A1A",
    "brushed_silver": "#BFC1C2",
    "gold_bronze": "#A67C37",
    "slate_grey": "#4A4D4F"
}

# Inject CSS for metrics & headers
st.markdown(f"""
<style>
    .stApp {{ background-color: {COLORS['matte_black']}; color: {COLORS['brushed_silver']}; }}
    .stMetric > div > div:first-child {{ color: {COLORS['petrol_blue']}; }}
    .stMetric > div > div:nth-child(2) {{ color: {COLORS['gold_bronze']}; font-weight: bold; }}
    h1, h2, h3 {{ color: {COLORS['petrol_blue']}; }}
    .st-expander {{ background-color: {COLORS['slate_grey']}; border-radius: 8px; padding: 8px; }}
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
    "Plush": 35
}

NEOPOS_MAX = 4

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================
def fork_baseline(style, is_rec):
    """Returns CTS Valve, base LSC, base LSR, brake support index"""
    if is_rec or style == "Plush":
        return "Bronze (Velvet)", 12, 12, -1
    if style in ["Flow / Jumps", "Dynamic"]:
        return "Gold (Standard)", 10, 11, 0
    if style in ["Alpine", "Steep / Tech"]:
        return "Purple (Digressive)", 8, 10, 2
    return "Bronze (Velvet)", 11, 11, 0

def recommend_neopos(weight, sag_pct, style):
    """Returns recommended Neopos tokens 0-4"""
    # Light riders: softer front, fewer tokens
    # Heavy riders: firmer, more tokens
    if style in ["Plush", "Trail"] and weight < 72:
        return 1
    elif style in ["Alpine", "Steep / Tech"]:
        if weight < 75: return 2
        return 3
    return 2

def calculate_physics(weight, style, weather, is_rec, neopos_val):
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec
    
    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046
    
    # Mean leverage ratio (integral method)
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm
    
    # Raw spring rate
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)
    if raw_rate < CONFIG["SPRING_MIN"]: spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]: spring_rate = CONFIG["SPRING_MAX"]
    else: spring_rate = 5 * round(raw_rate / 5)
    
    # Actual Sag
    actual_sag_mm = ((sprung_lbs * lr_mean) / spring_rate) * 25.4
    actual_sag_pct = (actual_sag_mm / CONFIG["SHOCK_STROKE_MM"]) * 100
    sag_error = actual_sag_pct - target_sag

    # Shock damping
    shock_reb = -10 + round((spring_rate - 400) / CONFIG["REBOUND_LBS_PER_CLICK"])
    comp_offset = {"Alpine":2,"Steep / Tech":2,"Plush":-2}.get(style,0)
    shock_comp = -9 + comp_offset
    if weather=="Cold": shock_reb-=1; shock_comp-=1
    if weather=="Rain / Wet": shock_comp-=2
    shock_reb = max(-13, min(0, shock_reb))
    shock_comp = max(-17, min(0, shock_comp))

    # Fork PSI
    fork_psi = CONFIG["BASE_FORK_PSI"] + (weight - 72)*CONFIG["FORK_PSI_PER_KG"] + sag_error*CONFIG["SAG_PITCH_GAIN"]
    if weight < CONFIG["NEG_SPRING_THRESHOLD"]:
        fork_psi -= (CONFIG["NEG_SPRING_THRESHOLD"] - weight)*CONFIG["NEG_SPRING_GAIN"]

    # Fork Damping
    f_valve, base_lsc, base_lsr, brake_bias = fork_baseline(style,is_rec)
    brake_clicks = min(CONFIG["BRAKE_SUPPORT_MAX"], brake_bias*CONFIG["BRAKE_SUPPORT_GAIN"])
    f_lsc = base_lsc - brake_clicks - neopos_val
    reb_correction = round((fork_psi - 66)/5)
    f_lsr = base_lsr - reb_correction
    if weather=="Cold": f_lsc+=1; f_lsr+=1
    f_lsc = max(2, min(12, int(f_lsc)))
    f_lsr = max(2, min(19, int(f_lsr)))

    # Tyres
    t_mod = (weight - 72)*CONFIG["PSI_PER_KG"]
    f_psi_tyre = CONFIG["BASE_FRONT_PSI"] + t_mod
    r_psi_tyre = CONFIG["BASE_REAR_PSI"] + t_mod
    if weather=="Rain / Wet": f_psi_tyre-=1.5; r_psi_tyre-=1.5

    return {
        "sys_mass": sys_mass,
        "lr_mean": lr_mean,
        "target_sag": target_sag,
        "raw_rate": raw_rate,
        "spring_rate": spring_rate,
        "actual_sag": actual_sag_pct,
        "sag_error": sag_error,
        "shock_lsc": abs(shock_comp),
        "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi,
        "fork_valve": f_valve,
        "fork_lsc": abs(f_lsc),
        "fork_lsr": abs(f_lsr),
        "neopos": neopos_val,
        "brake_clicks": brake_clicks,
        "f_tyre": f_psi_tyre,
        "r_tyre": r_psi_tyre
    }

# ==========================================================
# UI
# ==========================================================
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.0")

# --- Inputs ---
col1, col2 = st.columns(2)
with col1:
    weight = st.number_input("Rider Weight (kg)", min_value=50.0, max_value=110.0, value=72.0, step=0.5)
    is_rec = st.toggle("Recovery Mode", value=False)
with col2:
    style = st.selectbox("Riding Style", options=list(SAG_DEFAULTS.keys()), index=3)
    weather = st.selectbox("Weather", options=["Standard","Cold","Rain / Wet"])

# Neopos slider: Auto + 0-4
st.markdown("### Neopos Tokens (Auto recommended, override 0-4)")
neopos_auto = recommend_neopos(weight, SAG_DEFAULTS[style], style)
neopos_val = st.select_slider(
    "Neopos Tokens",
    options=["Auto",0,1,2,3,4],
    value="Auto"
)
if neopos_val=="Auto":
    neopos_val = neopos_auto

# --- Calculation ---
data = calculate_physics(weight, style, weather, is_rec, neopos_val)

st.divider()

# --- Outputs ---
st.subheader(f"Setup Profile: {style.upper()}")

# Rear
with st.expander("Rear Suspension (Formula Mod)", expanded=True):
    c1,c2,c3 = st.columns(3)
    c1.metric("Raw Spring Rate", f"{data['raw_rate']:.1f} lb/in")
    c2.metric("Selected Spring", f"{data['spring_rate']} lb")
    c3.metric("Target / Actual Sag", f"{data['target_sag']}% / {data['actual_sag']:.1f}% (Error: {data['sag_error']:+.1f}%)")
    st.markdown("---")
    d1,d2 = st.columns(2)
    d1.metric("Shock LSC (Compression)", f"{data['shock_lsc']} OUT")
    d2.metric("Shock LSR (Rebound)", f"{data['shock_lsr']} OUT")

# Fork
with st.expander("Fork (Selva V)", expanded=True):
    c1,c2 = st.columns(2)
    c1.metric("Air Pressure", f"{data['fork_psi']:.1f} PSI")
    c2.metric("CTS Valve", data['fork_valve'])
    st.markdown("---")
    d1,d2 = st.columns(2)
    d1.metric("LSC (Low Speed Compression)", f"{data['fork_lsc']} OUT | Neopos: {data['neopos']}")
    d2.metric("LSR (Rebound)", f"{data['fork_lsr']} OUT | Brake Clicks: {data['brake_clicks']}")

# Tyres
with st.expander("Tyres (SuperGravity)", expanded=True):
    t1,t2 = st.columns(2)
    t1.metric("Front Pressure", f"{data['f_tyre']:.1f} PSI")
    t2.metric("Rear Pressure", f"{data['r_tyre']:.1f} PSI")
