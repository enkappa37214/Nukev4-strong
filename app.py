import streamlit as st
import pandas as pd
import datetime
import numpy as np
from fpdf import FPDF
from streamlit_gsheets import GSheetsConnection
import locale

# Set locale for consistent number formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')

# ==========================================================
# 1. CONFIGURATION & DATA CONSTANTS
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4 - Formula Expert", page_icon="⚡", layout="centered")

# CSS / Styling
COLORS = {
    "petrol": "#005F60",
    "bg": "#0E1117",
    "card": "#262730",
    "text": "#FAFAFA",
    "accent": "#D4AF37",  # Formula Gold
    "alert": "#FF4B4B"
}

st.markdown(f"""
<style>
    .stApp {{ background-color: {COLORS['bg']}; color: {COLORS['text']}; }}
    h1, h2, h3 {{ color: {COLORS['petrol']} !important; }}
    div[data-testid="stMetricValue"] {{ color: {COLORS['accent']} !important; font-weight: 700; }}
    .stSelectbox div[data-baseweb="select"] > div {{ background-color: {COLORS['card']}; }}
    div[role="dialog"] {{ background-color: {COLORS['card']}; }}
    .stSlider [data-baseweb="slider"] {{ color: {COLORS['petrol']}; }}
    .stButton>button {{ border: 1px solid {COLORS['accent']}; }}
</style>
""", unsafe_allow_html=True)

def reset_form_callback():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# --- ENGINEERING CONSTANTS (CORRECTED 2026 SPEC) ---
CONFIG = {
    "SHOCK_STROKE_MM": 62.5,
    "LEV_RATIO_START": 2.90,
    "LEV_RATIO_COEFF": 0.00816,
    
    # Formula Mod (Coil)
    # [CORRECTION] Reduced from 1.12 to 1.05 to prevent over-springing on high leverage frame
    "MOD_FRICTION_CORRECTION": 1.05, 
    "REBOUND_CLICKS_SHOCK": 13,
    
    # Formula Selva V (Air)
    "FORK_PSI_BASE_OFFSET": 65.0,
    "FORK_PSI_PER_KG": 0.88,
    # [CORRECTION] Reduced from 3.5 to 2.0 to prevent negative spring suck-down
    "NEOPOS_PSI_DROP": 2.0,
    "ALTITUDE_PSI_DROP": 1.5,
    "REBOUND_CLICKS_FORK": 21,
}

STYLES = {
    "Alpine Epic":       {"sag": 30.0, "bias": 65, "lsc_offset": 2, "desc": "Efficiency focus. Neutral bias."},
    "Flow / Park":       {"sag": 30.0, "bias": 63, "lsc_offset": 4, "desc": "Max Support. Forward bias."},
    "Dynamic":           {"sag": 31.0, "bias": 65, "lsc_offset": 0, "desc": "Balanced Enduro bias."},
    "Trail":             {"sag": 32.0, "bias": 65, "lsc_offset": 0, "desc": "Chatter focus."},
    "Steep / Tech":      {"sag": 33.0, "bias": 68, "lsc_offset": 1, "desc": "Geometry focus. Rearward bias."},
    "Plush":             {"sag": 35.0, "bias": 65, "lsc_offset": -2, "desc": "Comfort max."}
}

# ==========================================================
# 2. HELPER FUNCTIONS (LOGIC)
# ==========================================================

def get_cts_valve(style, weight, is_recovery):
    if is_recovery: return "Purple" # High flow safer for recovery
    
    # [LOGIC UPDATE] 2026 CTS Mapping
    if style == "Flow / Park": return "Blue" # Progressive/Poppy
    if style == "Trail": return "Gold" # Standard
    
    # Heavy Rider Logic for Steep/Tech
    if style == "Steep / Tech": 
        return "Orange" if weight > 85 else "Gold" # Orange provides anti-dive for heavy riders

    if style == "Alpine Epic":
        return "Purple" if weight < 75 else "Gold"

    if style == "Plush":
        return "Purple" # High Flow / Soft
        
    return "Gold"

def get_neopos_count(weight, style, is_recovery):
    if is_recovery: return 3
    
    val = 1
    if style in ["Flow / Park", "Steep / Tech"]: val += 1
    if style == "Plush": val = 0
    if weight > 85: val += 1
    if weight < 65: val = 0
    return max(0, min(3, val))

def calculate_setup(rider_kg, bike_kg, unsprung_kg, style_key, sag_target, bias_manual, altitude, weather, is_recovery, neopos_select, spring_override):
    s_data = STYLES[style_key]
    
    # [EXISTING NEOPOS LOGIC...] 
    neopos_rec = get_neopos_count(rider_kg, style_key, is_recovery)
    if neopos_select == "Auto": neopos_final = neopos_rec
    else: neopos_final = int(neopos_select)
    neopos_delta = neopos_final - neopos_rec

    # [EXISTING MASS/LOAD CALCS...]
    effective_bias_pct = bias_manual 
    total_mass_kg = rider_kg + bike_kg
    sprung_mass_kg = total_mass_kg - unsprung_kg
    rear_load_kg = sprung_mass_kg * (effective_bias_pct / 100.0)
    rear_load_lbs = rear_load_kg * 2.20462
    
    # [EXISTING KINEMATICS...]
    final_sag_pct = 35.0 if is_recovery else sag_target
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * (final_sag_pct / 100.0)
    lr_at_sag = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] * sag_mm)
    spring_force_lbs = rear_load_lbs * lr_at_sag
    shock_compress_in = sag_mm / 25.4
    raw_rate = spring_force_lbs / shock_compress_in
    mod_rate = raw_rate * CONFIG["MOD_FRICTION_CORRECTION"]
    
    # --- SPRING RATE COMPENSATION LOGIC ---
    # 1. Calculate Ideal (including Neopos balance correction)
    rate_comp_lbs = 0
    if neopos_delta < 0: rate_comp_lbs = abs(neopos_delta) * 10
    if neopos_delta > 0: rate_comp_lbs = -(neopos_delta * 5)
    
    ideal_rate_exact = int(mod_rate + rate_comp_lbs)
    
    # 2. Determine Actual Rate Used (Auto vs Override)
    if spring_override == "Auto":
        active_rate = ideal_rate_exact
        rate_mismatch = 0
    else:
        active_rate = int(spring_override)
        rate_mismatch = active_rate - ideal_rate_exact
        
    # 3. Calculate Resulting Sag (Approximation)
    # If using stiffer spring, sag decreases. 
    sag_actual_pct = final_sag_pct * (ideal_rate_exact / active_rate)

    # --- SHOCK DAMPING (Adaptive) ---
    # Rebound: Uses ACTIVE rate (Self-correcting: Heavier spring = Stiffer rebound)
    reb_clicks = 7 - int((active_rate - 450) / 50)
    if weather == "Cold": reb_clicks += 2
    reb_clicks = max(1, min(13, reb_clicks))
    
    # LSC: Compensate for Spring Mismatch
    # If Spring is Soft (Mismatch < 0) -> ADD LSC (Stiffen/Lower Click #)
    # If Spring is Stiff (Mismatch > 0) -> REDUCE LSC (Soften/Higher Click #)
    # Formula Mod: 1=Closed(Stiff), 13=Open(Soft). 
    # Mismatch -50lbs -> Need Stiffer -> Subtract clicks.
    lsc_spring_comp = int(rate_mismatch / 25) # e.g., -50lbs / 25 = -2 clicks (Stiffer)
    
    # Neopos LSC Comp (Existing)
    lsc_neo_comp = 0
    if neopos_delta < 0: lsc_neo_comp = -abs(neopos_delta) # Stiffen if front diving
    
    base_lsc = 7 + s_data["lsc_offset"] + lsc_spring_comp + lsc_neo_comp
    
    if final_sag_pct > 32.0 and not is_recovery: base_lsc -= 1 # Deep sag needs support (Stiffen)
    if weather == "Rain / Wet": base_lsc += 2 # Soften
    if is_recovery: base_lsc = 12 # Open/Soft
        
    lsc_clicks = max(1, min(13, base_lsc))
    
    # 6. FORK (SELVA V)
    # Base Pressure
    base_psi = CONFIG["FORK_PSI_BASE_OFFSET"] + ((rider_kg - 75) * CONFIG["FORK_PSI_PER_KG"])
    
    # Neopos & Altitude
    alt_penalty = (altitude / 1000.0) * CONFIG["ALTITUDE_PSI_DROP"]
    
    # [!] COMPENSATION: Fork Pressure
    # If tokens missing, add pressure to prevent bottom out (Safety)
    psi_safety = 0
    if neopos_delta < 0: psi_safety = abs(neopos_delta) * 3.0 # +3psi per missing token
    
    # Standard formula uses the ACTUAL count inside the fork
    final_psi = base_psi - (neopos_final * CONFIG["NEOPOS_PSI_DROP"]) - alt_penalty + psi_safety
    
    if is_recovery: final_psi = max(40, final_psi * 0.9)
    
    # Valve
    valve = "Bronze" if is_recovery else get_cts_valve(style_key, rider_kg, is_recovery)
    
    # Fork Damping
    fork_reb = 10 + int((final_psi - 70) / 10)
    if weather == "Cold": fork_reb += 2
    fork_reb = max(2, min(21, fork_reb))
    
    # [!] COMPENSATION: Fork Compression
    # Clicks are from OPEN (12 = Open, 0 = Closed)
    # If Linear (Missing tokens) -> Need LOWER number (More Damping)
    lsc_fork_comp = 0
    if neopos_delta < 0: lsc_fork_comp = -abs(neopos_delta) # Subtract clicks (Stiffen)
    if neopos_delta > 0: lsc_fork_comp = neopos_delta        # Add clicks (Soften)
    
    fork_lsc = 12 # Start Open
    if valve == "Gold": fork_lsc = 7
    if valve == "Orange": fork_lsc = 5
    if valve == "Blue": fork_lsc = 4
    if valve == "Purple": fork_lsc = 10
    
    fork_lsc += lsc_fork_comp
    
    if weather == "Rain / Wet": fork_lsc = 12
    fork_lsc = max(0, min(12, fork_lsc)) # Clamp
    
    return {
        "mod_rate": ideal_rate_exact,   # The perfect math
        "active_rate": active_rate,     # What is installed
        "sag_actual": sag_actual_pct,   # Resulting sag
        "std_rate": 25 * round(ideal_rate_exact / 25),
        "shock_reb": reb_clicks,
        "shock_lsc": lsc_clicks,
        "fork_psi": final_psi,
        "fork_cts": valve,
        "fork_neopos": neopos_final,
        "neopos_rec": neopos_rec,
        "fork_reb": fork_reb,
        "fork_lsc": fork_lsc,
        "sag": final_sag_pct,
        "bias": effective_bias_pct
    }
# ==========================================================
# 3. UI MAIN
# ==========================================================
col_title, col_reset = st.columns([0.8, 0.2])
with col_title:
    st.title("Nukeproof Mega v4 Setup")
    st.caption("Formula Suspension Expert (2026 Spec)")
with col_reset:
    if st.button("Reset", on_click=reset_form_callback, type="secondary"):
        st.rerun()

# --- INPUT SECTION ---
st.subheader("1. Configuration")
col_w1, col_w2, col_w3 = st.columns(3)
with col_w1:
    rider_kg = st.number_input("Rider Weight (kg)", 40.0, 140.0, 72.0, 0.1, help="Fully kitted weight.", key="rider_kg")
with col_w2:
    bike_kg = st.number_input("Bike Weight (kg)", 10.0, 30.0, 15.1, 0.1, key="bike_kg")
with col_w3:
    unsprung_kg = st.number_input("Unsprung Mass (kg)", 2.0, 10.0, 4.27, 0.01, key="unsprung_kg")

col_rec, col_env1, col_env2 = st.columns(3)
with col_rec:
    st.write("") 
    st.write("") 
    is_rec = st.toggle("Recovery Mode", help="Max softness + Anti-Dive safety.", key="is_rec")
with col_env1:
    weather = st.selectbox("Weather", ["Standard", "Cold (<5°C)", "Rain / Wet"], key="weather")
with col_env2:
    altitude = st.number_input("Max Altitude (m)", 0, 3000, 500, 50, key="altitude")

st.markdown("---")

st.subheader("2. Tuning")
col_style, col_sag, col_bias = st.columns(3)

def update_defaults():
    s_key = st.session_state.style_select
    st.session_state.sag_slider = STYLES[s_key]["sag"]
    st.session_state.bias_slider = STYLES[s_key]["bias"]

with col_style:
    style_key = st.selectbox("Riding Style", list(STYLES.keys()), key="style_select", on_change=update_defaults)

with col_sag:
    if "sag_slider" not in st.session_state: st.session_state.sag_slider = 31.0
    target_sag = st.slider("Target Sag (%)", 30.0, 35.0, key="sag_slider", step=0.5, help="Nukeproof Kinematic Limit")

with col_bias:
    if "bias_slider" not in st.session_state: st.session_state.bias_slider = 65
    target_bias = st.slider("Rear Bias (%)", 55, 80, key="bias_slider", help="Applied to Sprung Mass")

# ==========================================================
# 4. CALCULATIONS & OUTPUT
# ==========================================================

rec_neopos_peek = get_neopos_count(rider_kg, style_key, is_rec)

st.divider()
c1, c2 = st.columns(2)

st.info("""
**Damping Reference:** All settings are measured from **FULLY CLOSED** (Turn Clockwise ↻ until stop).  
**0 Clicks** = Max Damping (Stiffest / Slowest).  
**Higher Number** = Less Damping (Softer / Faster).
""")

# --- LEFT COLUMN (SHOCK) ---
with c1:
    st.subheader("Formula MOD (Coil)")
    # [Insert Image Tag Here if needed, ensure it is commented out or valid]
    
    # SPRING RATE OVERRIDE INPUT
    # We place this here so it sits visually in the Shock section
    spring_options = ["Auto"] + [str(r) for r in range(300, 650, 5)] # 5lb increments
    spring_override = st.selectbox(
        "Actual Spring Rate (lbs)", 
        options=spring_options, 
        index=0,
        help="Select your installed Sprindex/Coil rate to adapt damping.",
        key="spring_override"
    )

# --- RIGHT COLUMN (FORK) ---
with c2:
    st.subheader("Formula Selva V (Air)")
    
    # NEOPOS OVERRIDE INPUT
    neopos_select = st.select_slider(
        "Neopos Config (Installed)", 
        options=["Auto", "0", "1", "2", "3"], 
        value="Auto",
        help=f"Auto recommends: {rec_neopos_peek}.",
        key="neopos_override"
    )

# --- RUN CALCULATION ---
# Pass the new spring_override variable
res = calculate_setup(rider_kg, bike_kg, unsprung_kg, style_key, target_sag, target_bias, altitude, weather, is_rec, neopos_select, spring_override)

# --- DISPLAY RESULTS (Updated) ---
with c1:
    # Display Active Rate vs Ideal
    st.metric("Spring Rate", f"{res['active_rate']} lbs", delta=f"Ideal: {res['mod_rate']} lbs", delta_color="off")
    
    # Warn if actual sag deviates significantly
    if abs(res['sag_actual'] - res['sag']) > 2.0:
        st.caption(f"⚠️ **Geometry Shift:** Estimated Sag {res['sag_actual']:.1f}% (Target {res['sag']}%)")

    d1, d2 = st.columns(2)
    d1.metric("Rebound", f"{res['shock_reb']}", "Clicks from CLOSED")
    d2.metric("Compression", f"{res['shock_lsc']}", "Clicks from CLOSED")
    
    if res['active_rate'] != res['mod_rate']:
         st.info("ℹ️ **Adaptive Tuning:** Damping adjusted to compensate for spring rate mismatch.")
        
# FORK OUTPUT (Right Column - continued)
with c2:
    # We already rendered the Header and Slider above. Now rendering metrics.
    
    st.metric("Pressure", f"{res['fork_psi']:.1f} psi", delta=f"Active: {res['fork_neopos']} Neopos")
    
    h1, h2 = st.columns(2)
    h1.metric("CTS Valve", res['fork_cts'])
    
    # Visual feedback on Neopos mismatch
    neo_label = f"{res['fork_neopos']}"
    if res['fork_neopos'] != res['neopos_rec']:
        neo_label += f" (Rec: {res['neopos_rec']})"
        
    h2.metric("Neopos Count", neo_label, delta_color="off")
    
    d3, d4 = st.columns(2)
    d3.metric("Rebound", f"{res['fork_reb']}", "Clicks from CLOSED")
    d4.metric("Compression", f"{res['fork_lsc']}", "Clicks from CLOSED")
    
    if is_rec:
        st.warning("⚠️ Recovery Safety: High Neopos applied.")
    
    # Expert Signal for Heavy Riders
    if rider_kg > 85 and style_key == "Steep / Tech" and res['fork_cts'] == "Orange":
        st.info("ℹ️ **Expert Note:** Orange valve selected for max anti-dive support at this weight class.")
    
    # Mismatch warning
    if res['fork_neopos'] != res['neopos_rec']:
        st.caption(f"⚠️ **Compensating:** Fork PSI, LSC & Shock Rate adjusted for volume mismatch.")

# PDF Generation
def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Nukeproof Mega v4 Setup Report", ln=True, align='C')
    pdf.set_font("Arial", size=11); pdf.ln(10)
    
    pdf.cell(200, 8, f"Rider: {rider_kg}kg | Bike: {bike_kg}kg | Unsprung: {unsprung_kg}kg", ln=True)
    pdf.cell(200, 8, f"Style: {style_key} | Weather: {weather}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Formula MOD", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, f"Sprindex Rate: {data['mod_rate']} lbs", ln=True)
    pdf.cell(200, 8, f"Rebound: {data['shock_reb']} clicks", ln=True)
    pdf.cell(200, 8, f"Compression: {data['shock_lsc']} clicks", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Formula Selva V", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, f"Pressure: {data['fork_psi']:.1f} psi", ln=True)
    pdf.cell(200, 8, f"Neopos: {data['fork_neopos']}", ln=True)
    pdf.cell(200, 8, f"CTS: {data['fork_cts']}", ln=True)
    
    return pdf.output(dest="S").encode("latin-1")

if st.button("Export PDF Report"):
    try:
        pdf_bytes = generate_pdf(res)
        st.download_button("Download PDF", pdf_bytes, "setup_report.pdf", "application/pdf")
    except Exception as e:
        st.error(f"PDF Error: {e}")

st.caption("Calculations valid for Nukeproof Mega v4 (2020-2026) + Formula Selva V 2025 + Formula Mod 2025")
