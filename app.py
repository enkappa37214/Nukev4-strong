import streamlit as st
import math

# ==========================================================
# STREAMLIT CONFIG
# ==========================================================
st.set_page_config(page_title="Nukeproof Setup", page_icon="⚙️", layout="centered")

# ==========================================================
# COLOR PALETTE
# ==========================================================
COLORS = {
    "petrol_blue": "#005F6",
    "matte_black": "#1A1A1A",
    "brushed_silver": "#BFC1C2",
    "gold_bronze": "#A67C37",
    "slate_grey": "#4A4D4A"
}

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
    "PSI_PER_KG": 0.25,
    "MAX_NEOPOS": 4
}

SAG_DEFAULTS = {
    "Flow / Jumps": 30,
    "Dynamic": 31,
    "Alpine": 32,
    "Trail": 33,
    "Steep / Tech": 34,
    "Plush": 35
}

# ==========================================================
# NEOPOS RECOMMENDATION FUNCTION
# ==========================================================
def recommend_neopos(fork_psi, sag_pct):
    """Simple heuristic for auto Neopos recommendation based on fork PSI and sag."""
    if fork_psi < 62 or sag_pct > 35: return 4
    elif fork_psi < 64 or sag_pct > 34: return 3
    elif fork_psi < 66 or sag_pct > 33: return 2
    else: return 1

# ==========================================================
# FORK VALVE BASELINE FUNCTION
# ==========================================================
def get_fork_baseline(style, is_rec):
    if is_rec or style == "Plush":
        return "Bronze (Velvet)", 12, 12, -1
    if style in ["Flow / Jumps", "Dynamic"]:
        return "Gold (Standard)", 10, 11, 0
    if style in ["Alpine", "Steep / Tech"]:
        return "Purple (Digressive)", 8, 10, 2
    return "Bronze (Velvet)", 11, 11, 0

# ==========================================================
# PHYSICS CALCULATION
# ==========================================================
def calculate_physics(weight, style, weather, is_rec, neopos_tokens):
    # Target Sag
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec

    # System Mass
    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046

    # Mean Leverage Ratio (Integral)
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm

    # Raw Spring Rate
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)

    # Selected Spring
    if raw_rate < CONFIG["SPRING_MIN"]:
        spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]:
        spring_rate = CONFIG["SPRING_MAX"]
    else:
        spring_rate = 5 * round(raw_rate / 5)

    # Actual Sag
    actual_sag_mm = ((sprung_lbs * lr_mean) / spring_rate) * 25.4
    actual_sag_pct = (actual_sag_mm / CONFIG["SHOCK_STROKE_MM"]) * 100
    sag_error = actual_sag_pct - target_sag

    # Rear Damping
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
        "sys_mass": sys_mass,
        "lr_mean": lr_mean,
        "raw_rate": raw_rate,
        "spring_rate": spring_rate,
        "target_sag": target_sag,
        "actual_sag": actual_sag_pct,
        "sag_error": sag_error,
        "shock_lsc": abs(shock_comp),
        "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi,
        "fork_valve": f_valve,
        "fork_lsc": abs(f_lsc),
        "fork_lsr": abs(f_lsr),
        "brake_clicks": brake_clicks,
        "neopos_tokens": neopos_tokens,
        "f_tyre": f_psi_tyre,
        "r_tyre": r_psi_tyre
    }

# ==========================================================
# UI
# ==========================================================
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.0")

# Inputs
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        weight = st.number_input("Rider Weight (kg)", min_value=65.0, max_value=80.0, value=72.0, step=0.5)
        is_rec = st.toggle("Recovery Mode", value=False)
    with col2:
        style = st.selectbox("Riding Style", list(SAG_DEFAULTS.keys()), index=3)
        weather = st.selectbox("Weather", ["Standard", "Cold", "Rain / Wet"])

# Estimate physics for auto Neopos
est_data = calculate_physics(weight, style, weather, is_rec, neopos_tokens=0)
neopos_auto = recommend_neopos(est_data["fork_psi"], est_data["actual_sag"])

# Neopos Slider (-1 = Auto)
neopos_slider = st.slider("Neopos Tokens (Auto Recommended)", -1, CONFIG["MAX_NEOPOS"], value=-1, step=1)
if neopos_slider == -1:
    neopos_final = neopos_auto
else:
    neopos_final = neopos_slider

# Final Calculation
data = calculate_physics(weight, style, weather, is_rec, neopos_final)

st.divider()

# Rear
with st.expander("Rear Suspension", expanded=True):
    st.metric("Raw Spring Rate", f"{data['raw_rate']:.1f} lb/in")
    st.metric("Selected Spring Rate", f"{data['spring_rate']} lb ±10 lb")
    st.metric("Target Sag", f"{data['target_sag']}%", f"Actual: {data['actual_sag']:.1f}%")
    st.metric("Sag Error", f"{data['sag_error']:+.1f}%")
    st.metric("Shock LSC", f"{data['shock_lsc']} OUT")
    st.metric("Shock LSR", f"{data['shock_lsr']} OUT")

# Fork
with st.expander("Fork (Selva V)", expanded=True):
    st.metric("Air Pressure", f"{data['fork_psi']:.1f} PSI")
    st.metric("Valve", data['fork_valve'])
    st.metric("LSC", f"{data['fork_lsc']} OUT")
    st.metric("LSR", f"{data['fork_lsr']} OUT")
    st.metric("Neopos Tokens", data['neopos_tokens'])

# Tyres
with st.expander("Tyres", expanded=True):
    st.metric("Front Pressure", f"{data['f_tyre']:.1f} PSI")
    st.metric("Rear Pressure", f"{data['r_tyre']:.1f} PSI")
