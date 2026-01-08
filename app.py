import streamlit as st
import math

# ==========================================================
# SYSTEM CONFIGURATION (CONSTANTS)
# ==========================================================
CONFIG = {
    # Mass & Geometry
    "BIKE_MASS_KG": 15.11,
    "UNSPRUNG_MASS_KG": 4.27,
    "SHOCK_STROKE_MM": 62.5,
    "REAR_BIAS": 0.65,

    # Linkage Kinematics
    "LEV_RATIO_START": 2.90,
    "LEV_RATIO_COEFF": 0.00816,

    # Spring Hardware limits
    "SPRING_MIN": 390,
    "SPRING_MAX": 430,

    # Damping Scaling
    "REBOUND_LBS_PER_CLICK": 35,

    # Fork Baseline
    "BASE_FORK_PSI": 63.0,
    "FORK_PSI_PER_KG": 0.85,
    "SAG_PITCH_GAIN": 0.75,
    "NEG_SPRING_THRESHOLD": 70,
    "NEG_SPRING_GAIN": 0.6,

    # Brake Support
    "BRAKE_SUPPORT_GAIN": 1.0,
    "BRAKE_SUPPORT_MAX": 3,

    # Tyres
    "BASE_FRONT_PSI": 23.0,
    "BASE_REAR_PSI": 26.0,
    "PSI_PER_KG": 0.25,

    # Neopos
    "NEOPOS_MAX": 4
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
# LOGIC FUNCTIONS
# ==========================================================
def get_fork_baseline(style, is_rec):
    if is_rec or style == "Plush":
        return "Bronze (Velvet)", 12, 12, 0
    if style in ["Flow / Jumps", "Dynamic"]:
        return "Gold (Standard)", 10, 11, 0
    if style in ["Alpine", "Steep / Tech"]:
        return "Purple (Digressive)", 8, 10, 1
    return "Bronze (Velvet)", 11, 11, 0

def calculate_physics(weight, style, weather, is_rec):
    # Target Sag
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec
    
    # System Mass & Sprung Lbs
    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046
    
    # Mean leverage ratio (integral)
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm

    # Raw Spring Rate
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)
    if raw_rate < CONFIG["SPRING_MIN"]: spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]: spring_rate = CONFIG["SPRING_MAX"]
    else: spring_rate = 5 * round(raw_rate / 5)

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
    fork_psi = CONFIG["BASE_FORK_PSI"] + (weight - 72) * CONFIG["FORK_PSI_PER_KG"] + sag_error * CONFIG["SAG_PITCH_GAIN"]
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

    # High-Speed Compression (HSC)
    hsc_base = 12
    hsc_adj = -0.1 * max(0, 72 - weight) + 0.2 * sag_error
    style_hsc_mod = {"Flow / Jumps": -2,"Dynamic": -2,"Alpine": -1,"Steep / Tech": -1,"Plush": -2,"Trail":0}
    hsc_adj += style_hsc_mod.get(style, 0)
    if weather == "Cold": hsc_adj += 1
    elif weather == "Rain / Wet": hsc_adj -= 1
    hsc_calc = int(max(2, min(12, round(hsc_base + hsc_adj))))

    # Neopos auto recommendation
    neopos_auto = min(CONFIG["NEOPOS_MAX"], max(0, round((fork_psi - 60)/2)))
    
    # Tyres
    t_mod = (weight - 72) * CONFIG["PSI_PER_KG"]
    f_psi_tyre = CONFIG["BASE_FRONT_PSI"] + t_mod
    r_psi_tyre = CONFIG["BASE_REAR_PSI"] + t_mod
    if weather == "Rain / Wet": f_psi_tyre -= 1.5; r_psi_tyre -= 1.5

    return {
        "sys_mass": sys_mass, "lr_mean": lr_mean, "target_sag": target_sag,
        "raw_rate": raw_rate, "spring_rate": spring_rate, "actual_sag": actual_sag_pct, "sag_error": sag_error,
        "shock_lsc": abs(shock_comp), "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi, "fork_valve": f_valve, "fork_lsc": abs(f_lsc), "fork_lsr": abs(f_lsr),
        "hsc_calc": hsc_calc,
        "brake_bias": brake_bias, "brake_clicks": brake_clicks,
        "f_tyre": f_psi_tyre, "r_tyre": r_psi_tyre,
        "neopos_auto": neopos_auto
    }

# ==========================================================
# STREAMLIT UI
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4", layout="centered")
st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Integrated v12.0 – HSC & Neopos")

# Inputs
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        weight = st.number_input("Rider Weight (kg)", min_value=65.0, max_value=80.0, value=72.0, step=0.5)
        is_rec = st.toggle("Recovery Mode", value=False)
    with col2:
        style = st.selectbox("Riding Style", options=list(SAG_DEFAULTS.keys()), index=3)
        weather = st.selectbox("Weather", options=["Standard", "Cold", "Rain / Wet"])

# Calculate
data = calculate_physics(weight, style, weather, is_rec)

# Neopos override slider
neopos = st.slider("Neopos Tokens (0 = auto)", 0, CONFIG["NEOPOS_MAX"], value=data['neopos_auto'], help="Auto-calculated based on system; override as needed.")

st.divider()
st.subheader(f"Setup Profile: {style.upper()}")

# Rear Section
with st.expander("Rear Suspension", expanded=True):
    st.metric("Raw Spring Rate", f"{data['raw_rate']:.1f} lb/in")
    st.metric("Selected Spring Rate", f"{data['spring_rate']} lb")
    st.metric("Target Sag", f"{data['target_sag']}%", f"Actual: {data['actual_sag']:.1f}%")
    st.metric("Sag Error", f"{data['sag_error']:+.1f}%")
    st.metric("Shock LSC", f"{data['shock_lsc']} OUT")
    st.metric("Shock LSR", f"{data['shock_lsr']} OUT")

# Fork Section
with st.expander("Fork (Selva V)", expanded=True):
    st.metric("Fork Air PSI", f"{data['fork_psi']:.1f} PSI")
    st.metric("Valve", data['fork_valve'])
    st.metric("LSC", f"{data['fork_lsc']} OUT")
    st.metric("LSR", f"{data['fork_lsr']} OUT")
    st.metric("HSC", f"{data['hsc_calc']} OUT")
    st.metric("Neopos Tokens", f"{neopos} (Auto: {data['neopos_auto']})")

# Tyres
with st.expander("Tyres (SuperGravity)", expanded=True):
    st.metric("Front PSI", f"{data['f_tyre']:.1f}")
    st.metric("Rear PSI", f"{data['r_tyre']:.1f}")

# Metadata
st.caption(f"System Mass: {data['sys_mass']:.1f} kg | Mean Leverage: {data['lr_mean']:.3f}")
