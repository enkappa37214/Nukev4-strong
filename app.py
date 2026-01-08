import streamlit as st
import math

# ==========================================================
# SYSTEM CONFIGURATION (CONSTANTS)
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
    "MAX_NEOPOS": 4,
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
# COLOR PALETTE
# ==========================================================
COLORS = {
    "petrol_blue": "#005F6",
    "matte_black": "#1A1A1A",
    "brushed_silver": "#BFC1C2",
    "gold": "#A67C37",
    "slate_grey": "#4A4D4",
}

# ==========================================================
# LOGIC FUNCTIONS
# ==========================================================
def get_fork_baseline(style, is_rec):
    """Returns valve type, base LSC, LSR, and brake bias"""
    if is_rec or style == "Plush":
        return "Bronze (Velvet)", 12, 12, -1
    if style in ["Flow / Jumps", "Dynamic"]:
        return "Gold (Standard)", 10, 11, 0
    if style in ["Alpine", "Steep / Tech"]:
        return "Purple (Digressive)", 8, 10, 2
    return "Bronze (Velvet)", 11, 11, 0

def calculate_physics(weight, style, weather, is_rec, neopos_override=None):
    # --- Sag & Kinematics ---
    target_sag = 35 if is_rec else SAG_DEFAULTS.get(style, 33)
    sag_dec = target_sag / 100.0
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * sag_dec
    sys_mass = weight + CONFIG["BIKE_MASS_KG"]
    sprung_lbs = ((sys_mass * CONFIG["REAR_BIAS"]) - CONFIG["UNSPRUNG_MASS_KG"]) * 2.2046

    # --- Integral Leverage Ratio ---
    lr_mean = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] / 2.0) * sag_mm

    # --- Rear Spring Rate ---
    raw_rate = (sprung_lbs * lr_mean) / (sag_mm / 25.4)
    if raw_rate < CONFIG["SPRING_MIN"]:
        spring_rate = CONFIG["SPRING_MIN"]
    elif raw_rate > CONFIG["SPRING_MAX"]:
        spring_rate = CONFIG["SPRING_MAX"]
    else:
        spring_rate = 5 * round(raw_rate / 5)

    # --- Actual Sag & Error ---
    actual_sag_mm = ((sprung_lbs * lr_mean) / spring_rate) * 25.4
    actual_sag_pct = (actual_sag_mm / CONFIG["SHOCK_STROKE_MM"]) * 100
    sag_error = actual_sag_pct - target_sag

    # --- Rear Damping ---
    shock_reb = -10 + round((spring_rate - 400) / CONFIG["REBOUND_LBS_PER_CLICK"])
    comp_offset = 0
    if style in ["Alpine", "Steep / Tech"]: comp_offset = 2
    elif style == "Plush": comp_offset = -2
    shock_comp = -9 + comp_offset
    if weather == "Cold": shock_reb -= 1; shock_comp -= 1
    if weather == "Rain / Wet": shock_comp -= 2
    shock_reb = max(-13, min(0, shock_reb))
    shock_comp = max(-17, min(0, shock_comp))

    # --- Fork PSI ---
    fork_psi = CONFIG["BASE_FORK_PSI"]
    fork_psi += (weight - 72) * CONFIG["FORK_PSI_PER_KG"]
    fork_psi += sag_error * CONFIG["SAG_PITCH_GAIN"]
    if weight < CONFIG["NEG_SPRING_THRESHOLD"]:
        fork_psi -= (CONFIG["NEG_SPRING_THRESHOLD"] - weight) * CONFIG["NEG_SPRING_GAIN"]

    # --- Fork Damping ---
    f_valve, base_lsc, base_lsr, brake_bias = get_fork_baseline(style, is_rec)
    brake_clicks = min(CONFIG["BRAKE_SUPPORT_MAX"], brake_bias * CONFIG["BRAKE_SUPPORT_GAIN"])
    f_lsc = base_lsc - brake_clicks
    reb_correction = round((fork_psi - 66) / 5)
    f_lsr = base_lsr - reb_correction
    if weather == "Cold": f_lsc += 1; f_lsr += 1
    f_lsc = max(2, min(12, int(f_lsc)))
    f_lsr = max(2, min(19, int(f_lsr)))

    # --- Tyres ---
    t_mod = (weight - 72) * CONFIG["PSI_PER_KG"]
    f_psi_tyre = CONFIG["BASE_FRONT_PSI"] + t_mod
    r_psi_tyre = CONFIG["BASE_REAR_PSI"] + t_mod
    if weather == "Rain / Wet":
        f_psi_tyre -= 1.5; r_psi_tyre -= 1.5

    # --- Neopos Recommendation ---
    # Automatic calculation based on fork PSI & sag
    recommended_neopos = min(CONFIG["MAX_NEOPOS"], max(0, round((fork_psi - 60) / 2.5)))
    neopos = recommended_neopos if neopos_override is None else neopos_override
    neopos = min(CONFIG["MAX_NEOPOS"], max(0, neopos))  # enforce bounds

    return {
        "sys_mass": sys_mass, "lr_mean": lr_mean, "target_sag": target_sag,
        "raw_rate": raw_rate, "spring_rate": spring_rate,
        "actual_sag": actual_sag_pct, "sag_error": sag_error,
        "shock_lsc": abs(shock_comp), "shock_lsr": abs(shock_reb),
        "fork_psi": fork_psi, "fork_valve": f_valve,
        "fork_lsc": abs(f_lsc), "fork_lsr": abs(f_lsr),
        "brake_bias": brake_bias, "brake_clicks": brake_clicks,
        "f_tyre": f_psi_tyre, "r_tyre": r_psi_tyre,
        "neopos": neopos, "recommended_neopos": recommended_neopos,
    }

# ==========================================================
# STREAMLIT UI
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4", layout="centered", page_icon="⚙️")
st.markdown(f"""
<style>
body {{
    background-color: {COLORS['matte_black']};
    color: {COLORS['brushed_silver']};
}}
h1, h2, h3 {{
    color: {COLORS['petrol_blue']};
}}
.stMetricLabel {{ color: {COLORS['slate_grey']}; }}
.stMetricValue, .stMetricDelta {{ color: {COLORS['brushed_silver']}; }}
.recommended {{ color: {COLORS['gold']} !important; font-weight:bold; }}
</style>
""", unsafe_allow_html=True)

st.title("Nukeproof Mega v4 Calculator")
st.markdown("### Engineering Logic v12.0 with Neopos Auto-Recommendation")

# --- Inputs ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        weight = st.number_input("Rider Weight (kg)", min_value=65.0, max_value=80.0, value=72.0, step=0.5)
        is_rec = st.toggle("Recovery Mode", value=False)
    with col2:
        style = st.selectbox("Riding Style", list(SAG_DEFAULTS.keys()), index=3)
        weather = st.selectbox("Weather", ["Standard", "Cold", "Rain / Wet"])

# Neopos Slider (auto + manual override)
data_calc = calculate_physics(weight, style, weather, is_rec)
st.markdown(f"**Recommended Neopos Tokens:** <span class='recommended'>{data_calc['recommended_neopos']}</span>", unsafe_allow_html=True)
neopos_override = st.slider("Override Neopos Tokens (Auto / Manual)", 0, CONFIG["MAX_NEOPOS"], value=data_calc['recommended_neopos'], help="Slide to override automatic recommendation")

# --- Recalculate with Neopos Override ---
data = calculate_physics(weight, style, weather, is_rec, neopos_override)

st.divider()

# --- Results ---
st.subheader(f"Setup Profile: {style.upper()}")

# Rear
with st.expander("Rear Suspension (Formula Mod)", expanded=True):
    st.metric("Raw Rear Spring Rate", f"{data['raw_rate']:.1f} lb/in")
    st.metric("Selected Rear Spring", f"{data['spring_rate']} lb (±10 lb)")
    st.metric("Target Sag", f"{data['target_sag']}%", f"Actual: {data['actual_sag']:.1f}%")
    st.metric("Sag Error", f"{data['sag_error']:+.1f}%")
    st.metric("LSC (Compression)", f"{data['shock_lsc']} OUT")
    st.metric("LSR (Rebound)", f"{data['shock_lsr']} OUT")

# Fork
with st.expander("Fork (Selva V)", expanded=True):
    st.metric("Fork Air Pressure", f"{data['fork_psi']:.1f} PSI")
    st.metric("CTS Valve", data['fork_valve'])
    st.metric("LSC (Compression)", f"{data['fork_lsc']} OUT", help=f"Brake Bias: {data['brake_bias']} | Saturation: {data['brake_clicks']}")
    st.metric("LSR (Rebound)", f"{data['fork_lsr']} OUT")
    st.metric("Neopos Tokens", f"{data['neopos']} (Recommended: {data['recommended_neopos']})", help="Auto calculation based on fork PSI & sag. Override using slider.")

# Tyres
with st.expander("Tyres (SuperGravity)", expanded=True):
    st.metric("Front Pressure", f"{data['f_tyre']:.1f} PSI")
    st.metric("Rear Pressure", f"{data['r_tyre']:.1f} PSI")

# Metadata
st.caption(f"System Mass: {data['sys_mass']:.1f} kg | Mean Leverage: {data['lr_mean']:.3f} | Pitch Gain: {CONFIG['SAG_PITCH_GAIN']}")
