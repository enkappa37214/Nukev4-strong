import streamlit as st
import pandas as pd
from fpdf import FPDF
import locale

# Set locale for consistent number formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')

# ==========================================================
# 1. CONFIGURATION & CONSTANTS (MOVED TO TOP)
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4 - Formula Expert", page_icon="⚡", layout="centered")

# --- ENGINEERING CONSTANTS ---
CONFIG = {
    "SHOCK_STROKE_MM": 62.5,
    "LEV_RATIO_START": 2.90,
    "LEV_RATIO_COEFF": 0.00816,
    "MOD_FRICTION_CORRECTION": 1.05, 
    "REBOUND_CLICKS_SHOCK": 13,   
    "COMP_CLICKS_SHOCK": 17,      
    "FORK_PSI_BASE_OFFSET": 65.0,
    "FORK_PSI_PER_KG": 0.88,
    "NEOPOS_PSI_DROP": 2.0,
    "ALTITUDE_PSI_DROP": 1.5,
    "REBOUND_CLICKS_FORK": 19,    
}

# --- DATA DICTIONARIES (Moved here to prevent NameError) ---

# RIDING STYLES
STYLES = {
    
    "Flow / Park":       {"sag": 30.0, "bias": 63, "lsc_offset": -3, "desc": "Max Support. Forward bias."},
    "Dynamic":           {"sag": 31.0, "bias": 65, "lsc_offset": 0, "desc": "Balanced Enduro bias."},
    "Alpine Epic":       {"sag": 32.0, "bias": 65, "lsc_offset": -1, "desc": "Efficiency focus. Neutral bias."},
    "Trail":             {"sag": 33.0, "bias": 65, "lsc_offset": 0, "desc": "Chatter focus."},
    "Steep / Tech":      {"sag": 34.0, "bias": 68, "lsc_offset": -2, "desc": "Geometry focus. Rearward bias."},
    "Plush":             {"sag": 35.0, "bias": 65, "lsc_offset": 4, "desc": "Comfort max."}
}

# FORK VALVE SPECS
FORK_VALVE_SPECS = {
    "Purple": {"support": 2, "ramp": 2}, 
    "Blue":   {"support": 3, "ramp": 7}, 
    "Gold":   {"support": 5, "ramp": 5}, 
    "Orange": {"support": 7, "ramp": 6}, 
    "Green":  {"support": 8, "ramp": 8}, 
    "Bronze": {"support": 2, "ramp": 9}, 
    "Red":    {"support": 6, "ramp": 7}, 
}

# SHOCK VALVE SPECS
SHOCK_VALVE_SPECS = {
    "Gold":   {"support": 3, "ramp": 3},
    "Orange": {"support": 5, "ramp": 5},
    "Green":  {"support": 8, "ramp": 8},
}

# TIRE SPECS
TIRE_CASINGS = {
    "Reinforced (DD/SuperGravity)": -1.0,
    "Standard (EXO/SnakeSkin)": 0.0,
    "Downhill (DH/2-Ply)": -2.0
}
TIRE_WIDTHS = {
    "2.3\" - 2.4\"": 0.0,
    "2.5\" - 2.6\"": -1.5
}
TIRE_INSERTS = {
    "None": {"f": 0.0, "r": 0.0},
    "Rear Only": {"f": 0.0, "r": -1.5},
    "Both": {"f": -1.5, "r": -1.5}
}

# --- STATE MANAGEMENT ---
DEFAULTS = {
    "rider_kg": 72.0,
    "bike_kg": 15.1,
    "unsprung_kg": 4.27,
    "is_rec": False,
    "weather": "Standard",
    "altitude": 500,
    "style_select": "Alpine Epic",
    "sag_slider": 31.0,
    "bias_slider": 65,
    "spring_override": "Auto",
    "neopos_override": "Auto",
    "valve_override": "Auto",
    "shock_valve_override": "Auto",
    "tire_casing": "Standard (EXO/SnakeSkin)",
    "tire_width": "2.3\" - 2.4\"",
    "tire_insert": "None",
    "is_tubeless": True
}

# --- CALLBACKS ---
def reset_form_callback():
    st.session_state.clear() 

def initialize_state():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

def update_rec_logic():
    # [FIXED] Handles logic for turning Recovery ON and OFF
    if st.session_state.is_rec:
        st.session_state.sag_slider = 35.0
    else:
        # Revert to selected style defaults
        s_key = st.session_state.style_select
        if s_key in STYLES:
            st.session_state.sag_slider = STYLES[s_key]["sag"]
            st.session_state.bias_slider = STYLES[s_key]["bias"]

def update_style_logic():
    if not st.session_state.get('is_rec', False):
        s_key = st.session_state.style_select
        if s_key in STYLES:
            st.session_state.sag_slider = STYLES[s_key]["sag"]
            st.session_state.bias_slider = STYLES[s_key]["bias"]

# Initialize State
initialize_state()

# CSS / Styling
COLORS = {
    "petrol": "#005F60",
    "bg": "#0E1117",
    "card": "#262730",
    "text": "#FAFAFA",
    "accent": "#D4AF37",
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

# ==========================================================
# 2. HELPER FUNCTIONS
# ==========================================================

def get_fork_cts(style, weight, is_recovery):
    if is_recovery: return "Bronze" 
    if style == "Flow / Park": return "Blue"
    if style == "Trail": return "Gold"
    if style == "Steep / Tech": 
        return "Orange" if weight > 85 else "Gold"
    if style == "Alpine Epic":
        return "Purple" if weight < 75 else "Gold"
    if style == "Plush":
        return "Purple"
    return "Gold"

def get_shock_cts_ideal(style, weight, is_recovery):
    if is_recovery: return "Gold"
    if weight > 90: return "Green" # Heavy riders
    if weight < 70: return "Gold"  # Light riders
    if style == "Plush": return "Gold"
    return "Orange" # Standard

def get_neopos_count(weight, style, is_recovery):
    if is_recovery: return 1
    val = 1
    if style in ["Flow / Park", "Steep / Tech"]: val += 1
    if style == "Plush": val = 0
    if weight > 85: val += 1
    if weight < 65: val = 0
    return max(0, min(3, val))

def calculate_setup(rider_kg, bike_kg, unsprung_kg, style_key, sag_target, bias_manual, altitude, weather, is_recovery, neopos_select, spring_override, fork_valve_override, shock_valve_override, tire_casing, tire_width, tire_insert, is_tubeless):
    s_data = STYLES[style_key]
    
    # --- 1. CONFIGURATION ---
    neopos_rec = get_neopos_count(rider_kg, style_key, is_recovery)
    
    # CTS Selection
    fork_valve_ideal = get_fork_cts(style_key, rider_kg, is_recovery)
    shock_valve_ideal = get_shock_cts_ideal(style_key, rider_kg, is_recovery)
    
    # Fork Active
    if fork_valve_override == "Auto":
        fork_valve_active = fork_valve_ideal
        fork_valve_mismatch = False
    else:
        fork_valve_active = fork_valve_override
        fork_valve_mismatch = (fork_valve_active != fork_valve_ideal)
        
    # Shock Active
    if shock_valve_override == "Auto":
        shock_valve_active = shock_valve_ideal
        shock_valve_mismatch = False
    else:
        shock_valve_active = shock_valve_override
        shock_valve_mismatch = (shock_valve_active != shock_valve_ideal)

    if neopos_select == "Auto": 
        neopos_installed = neopos_rec
    else: 
        neopos_installed = int(neopos_select)

    # --- 2. HYDRAULIC HANDSHAKE (Deltas) ---
    # Fork
    fork_ideal_scores = FORK_VALVE_SPECS.get(fork_valve_ideal, FORK_VALVE_SPECS["Gold"])
    fork_active_scores = FORK_VALVE_SPECS.get(fork_valve_active, FORK_VALVE_SPECS["Gold"])
    fork_support_delta = fork_active_scores["support"] - fork_ideal_scores["support"]
    fork_ramp_delta = fork_active_scores["ramp"] - fork_ideal_scores["ramp"]

    # Shock
    shock_ideal_scores = SHOCK_VALVE_SPECS.get(shock_valve_ideal, SHOCK_VALVE_SPECS["Orange"])
    shock_active_scores = SHOCK_VALVE_SPECS.get(shock_valve_active, SHOCK_VALVE_SPECS["Orange"])
    shock_support_delta = shock_active_scores["support"] - shock_ideal_scores["support"]

    # --- 3. SHOCK CALCULATIONS ---
    effective_bias_pct = bias_manual 
    total_mass_kg = rider_kg + bike_kg
    sprung_mass_kg = total_mass_kg - unsprung_kg
    rear_load_kg = sprung_mass_kg * (effective_bias_pct / 100.0)
    rear_load_lbs = rear_load_kg * 2.20462
    
    final_sag_pct = 35.0 if is_recovery else sag_target
    sag_mm = CONFIG["SHOCK_STROKE_MM"] * (final_sag_pct / 100.0)
    lr_at_sag = CONFIG["LEV_RATIO_START"] - (CONFIG["LEV_RATIO_COEFF"] * sag_mm)
    
    spring_force_lbs = rear_load_lbs * lr_at_sag
    shock_compress_in = sag_mm / 25.4
    raw_rate = spring_force_lbs / shock_compress_in
    mod_rate = raw_rate * CONFIG["MOD_FRICTION_CORRECTION"]
    ideal_rate_exact = int(mod_rate)
    
    if spring_override == "Auto":
        active_rate = ideal_rate_exact
        rate_mismatch = 0
    else:
        active_rate = int(spring_override)
        rate_mismatch = active_rate - ideal_rate_exact
        
    sag_actual_pct = final_sag_pct * (ideal_rate_exact / active_rate)

    # Shock Damping
    reb_clicks = 7 - int((active_rate - 450) / 50)
    if weather == "Cold (<5°C)": reb_clicks += 3
    reb_clicks = max(1, min(CONFIG["REBOUND_CLICKS_SHOCK"], reb_clicks))
    
    # Compression Logic
    lsc_spring_comp = int(rate_mismatch / 25) 
    
    neopos_delta = neopos_installed - neopos_rec
    lsc_chassis_bal = 0
    if neopos_delta < 0: lsc_chassis_bal = -abs(neopos_delta)
    
    # Valve Compensation
    lsc_shock_valve_offset = int(shock_support_delta * 1.5)

    base_lsc = 9 + s_data["lsc_offset"] + lsc_spring_comp + lsc_chassis_bal + lsc_shock_valve_offset
    
    if final_sag_pct > 32.0 and not is_recovery: base_lsc -= 1
    if weather == "Rain / Wet": base_lsc += 2
    if is_recovery: base_lsc = 17 
        
    lsc_clicks = max(1, min(CONFIG["COMP_CLICKS_SHOCK"], base_lsc))

    # --- 4. FORK CALCULATIONS ---
    base_psi = CONFIG["FORK_PSI_BASE_OFFSET"] + ((rider_kg - 75) * CONFIG["FORK_PSI_PER_KG"])
    alt_penalty = (altitude / 1000.0) * CONFIG["ALTITUDE_PSI_DROP"]
    
    neopos_correction = int(fork_ramp_delta / 3) 
    final_neopos_count = max(0, min(3, neopos_installed - neopos_correction))
    effective_neopos_delta = final_neopos_count - neopos_rec

    psi_safety = 0
    if effective_neopos_delta < 0: psi_safety = abs(effective_neopos_delta) * 3.0
    
    raw_psi = base_psi - (final_neopos_count * CONFIG["NEOPOS_PSI_DROP"]) - alt_penalty + psi_safety
    if is_recovery: raw_psi = max(40, raw_psi * 0.9)

    psi_correction_factor = 1.0 - (fork_support_delta * 0.03)
    final_psi = raw_psi * psi_correction_factor

    if weather == "Cold (<5°C)":
        final_psi = final_psi * 1.05
    
    fork_reb = 10 - int((final_psi - 70) / 10)
    if weather == "Cold (<5°C)": fork_reb += 3
    fork_reb = max(2, min(CONFIG["REBOUND_CLICKS_FORK"], fork_reb))
    
    lsc_valve_offset = int(fork_support_delta * 1.5)
    
    lsc_neopos_offset = 0
    if effective_neopos_delta < 0: lsc_neopos_offset = -abs(effective_neopos_delta)
    if effective_neopos_delta > 0: lsc_neopos_offset = effective_neopos_delta
    
    fork_lsc = 12
    if fork_valve_ideal == "Gold": fork_lsc = 7
    if fork_valve_ideal == "Orange": fork_lsc = 5
    if fork_valve_ideal == "Blue": fork_lsc = 4
    if fork_valve_ideal == "Purple": fork_lsc = 10
    if fork_valve_ideal == "Bronze": fork_lsc = 8
    
    fork_lsc += lsc_neopos_offset + lsc_valve_offset
    
    if weather == "Rain / Wet": fork_lsc = 12
    fork_lsc = max(0, min(12, fork_lsc))

    # --- 5. TIRE PRESSURE CALCULATIONS ---
    # Baseline: 75kg rider -> 23F / 26R. scaling +1psi per 5kg
    weight_offset = (rider_kg - 75.0) / 5.0
    
    base_f = 23.0 + weight_offset
    base_r = 26.0 + weight_offset
    
    # Modifiers
    casing_mod = TIRE_CASINGS.get(tire_casing, 0.0)
    base_f += casing_mod; base_r += casing_mod
    
    width_mod = TIRE_WIDTHS.get(tire_width, 0.0)
    base_f += width_mod; base_r += width_mod
    
    insert_mod = TIRE_INSERTS.get(tire_insert, {"f":0.0, "r":0.0})
    base_f += insert_mod["f"]; base_r += insert_mod["r"]
    
    if not is_tubeless:
        base_f += 4.0; base_r += 4.0
        
    if style_key == "Flow / Park":
        base_f += 2.0; base_r += 2.0
    elif style_key == "Steep / Tech":
        base_f -= 1.0; base_r -= 1.0
    elif style_key == "Alpine Epic":
        base_f += 1.0; base_r += 1.0
        
    if weather == "Rain / Wet":
        base_f -= 2.0; base_r -= 2.0
    elif weather == "Cold (<5°C)":
        base_f -= 1.0; base_r -= 1.0
        
    final_f_psi = max(18.0, min(35.0, base_f))
    final_r_psi = max(18.0, min(35.0, base_r))
    
    return {
        "mod_rate": ideal_rate_exact,
        "active_rate": active_rate,
        "sag_actual": sag_actual_pct,
        "shock_reb": reb_clicks,
        "shock_lsc": lsc_clicks,
        "fork_psi": final_psi,
        "fork_cts": fork_valve_active,
        "shock_cts": shock_valve_active,
        "shock_cts_ideal": shock_valve_ideal,
        "fork_neopos": final_neopos_count,
        "neopos_rec": neopos_rec,
        "fork_reb": fork_reb,
        "fork_lsc": fork_lsc,
        "sag": final_sag_pct,
        "bias": effective_bias_pct,
        "fork_valve_mismatch": fork_valve_mismatch,
        "shock_valve_mismatch": shock_valve_mismatch,
        "fork_support_delta": fork_support_delta,
        "shock_support_delta": shock_support_delta,
        "tire_front": final_f_psi,
        "tire_rear": final_r_psi
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
        pass 

# --- INPUT SECTION ---
st.subheader("1. Configuration")
col_w1, col_w2, col_w3 = st.columns(3)
with col_w1:
    with col_w1:
        rider_kg = st.number_input("Rider Weight (kg)", 40.0, 140.0, step=0.5, key="rider_kg", help="Fully kitted weight.")
with col_w2:
    bike_kg = st.number_input("Bike Weight (kg)", 10.0, 30.0, step=0.1, key="bike_kg")
with col_w3:
    unsprung_kg = st.number_input("Unsprung Mass (kg)", 2.0, 10.0, key="unsprung_kg")

col_rec, col_env1, col_env2 = st.columns(3)
with col_rec:
    st.write("") 
    st.write("") 
    is_rec = st.toggle("Recovery Mode", help="Max softness + Anti-Dive safety.", key="is_rec", on_change=update_rec_logic)
with col_env1:
    weather = st.selectbox("Weather", ["Standard", "Cold (<5°C)", "Rain / Wet"], key="weather")
with col_env2:
    altitude = st.number_input("Max Altitude (m)", 0, 3000, step=50, key="altitude")

st.markdown("---")

st.subheader("2. Tuning")
col_style, col_sag, col_bias = st.columns(3)

with col_style:
    style_key = st.selectbox("Riding Style", list(STYLES.keys()), key="style_select", on_change=update_style_logic)

with col_sag:
    target_sag = st.slider("Target Sag (%)", 30.0, 35.0, key="sag_slider", step=0.5, help="Nukeproof Kinematic Limit")

with col_bias:
    # [FIXED] Capped at 70% for safety
    target_bias = st.slider("Rear Bias (%)", 55, 70, key="bias_slider", help="Applied to Sprung Mass")

# [NEW] Tire Section
st.markdown("---")
st.subheader("3. Tires")
t1, t2, t3, t4 = st.columns(4)
with t1:
    tire_casing = st.selectbox("Casing", list(TIRE_CASINGS.keys()), key="tire_casing")
with t2:
    tire_width = st.selectbox("Width", list(TIRE_WIDTHS.keys()), key="tire_width")
with t3:
    tire_insert = st.selectbox("Inserts", list(TIRE_INSERTS.keys()), key="tire_insert")
with t4:
    st.write("") 
    st.write("") 
    is_tubeless = st.toggle("Tubeless", value=True, key="is_tubeless")

# ==========================================================
# 4. CALCULATIONS & OUTPUT
# ==========================================================

rec_neopos_peek = get_neopos_count(rider_kg, style_key, is_rec)

st.divider()
c1, c2 = st.columns(2)

st.info("""
**Damping Reference:** Settings are clicks from **FULLY CLOSED** (Clockwise ↻).  
**0** = Max Damping (Stiff). **Higher #** = Min Damping (Soft).

**Formula Mod:** Comp: 17 | Reb: 13 Clicks  
**Formula Selva V:** Comp: 12 | Reb: 19 Clicks
""")

# --- LEFT COLUMN (SHOCK) ---
with c1:
    st.subheader("Formula MOD (Coil)")
    
    sc1, sc2 = st.columns(2)
    with sc1:
        spring_options = ["Auto"] + [str(r) for r in range(300, 650, 5)] 
        spring_override = st.selectbox(
            "Spring Rate (lbs)", 
            options=spring_options, 
            key="spring_override"
        )
    with sc2:
        shock_valve_options = ["Auto"] + list(SHOCK_VALVE_SPECS.keys())
        shock_valve_select = st.selectbox(
            "CTS Valve (Shock)",
            options=shock_valve_options,
            help="Select Gold, Orange, or Green.",
            key="shock_valve_override"
        )

# --- RIGHT COLUMN (FORK) ---
with c2:
    st.subheader("Formula Selva V (Air)")
    
    fc1, fc2 = st.columns(2)
    with fc1:
        fork_valve_options = ["Auto"] + list(FORK_VALVE_SPECS.keys())
        fork_valve_select = st.selectbox(
            "CTS Valve (Installed)",
            options=fork_valve_options,
            key="valve_override"
        )
    with fc2:
        neopos_select = st.select_slider(
            "Neopos (Installed)", 
            options=["Auto", "0", "1", "2", "3"], 
            help=f"Auto recommends: {rec_neopos_peek}.",
            key="neopos_override"
        )

# --- RUN CALCULATION ---
res = calculate_setup(rider_kg, bike_kg, unsprung_kg, style_key, target_sag, target_bias, altitude, weather, is_rec, neopos_select, spring_override, fork_valve_select, shock_valve_select, tire_casing, tire_width, tire_insert, is_tubeless)

# --- DISPLAY RESULTS ---
st.markdown("### 🛞 Tire Pressure")
tp1, tp2 = st.columns(2)
tp1.metric("Front Tire", f"{res['tire_front']:.1f} psi")
tp2.metric("Rear Tire", f"{res['tire_rear']:.1f} psi")
st.markdown("---")

with c1:
    st.metric("Spring Rate", f"{res['active_rate']} lbs", delta=f"Ideal: {res['mod_rate']} lbs", delta_color="off")
    
    if abs(res['sag_actual'] - res['sag']) > 2.0:
        st.caption(f"⚠️ **Geometry Shift:** Estimated Sag {res['sag_actual']:.1f}%")

    st.metric("CTS Valve", res['shock_cts'])

    d1, d2 = st.columns(2)
    d1.metric("Rebound", f"{res['shock_reb']}", "Clicks from CLOSED")
    d2.metric("Compression", f"{res['shock_lsc']}", "Clicks from CLOSED")
    
    if res['shock_valve_mismatch']:
        st.warning(f"⚠️ **Shock Compensation Active**")
        st.caption(f"Valve: {res['shock_cts']} (Ideal: {res['shock_cts_ideal']})")
        if res['shock_support_delta'] != 0:
            action = "Opened" if res['shock_support_delta'] > 0 else "Closed"
            st.caption(f"• LSC {action} to balance valve support.")
    elif res['active_rate'] != res['mod_rate']:
         st.info("ℹ️ **Compensation:** Damping adjusted for spring rate mismatch.")

with c2:
    st.metric("Pressure", f"{res['fork_psi']:.1f} psi", delta=f"Active: {res['fork_neopos']} Neopos")
    
    h1, h2 = st.columns(2)
    h1.metric("CTS Valve", res['fork_cts'])
    
    neo_label = f"{res['fork_neopos']}"
    if res['fork_neopos'] != res['neopos_rec']:
        neo_label += f" (Rec: {res['neopos_rec']})"
        
    h2.metric("Neopos Count", neo_label, delta_color="off")
    
    d3, d4 = st.columns(2)
    d3.metric("Rebound", f"{res['fork_reb']}", "Clicks from CLOSED")
    d4.metric("Compression", f"{res['fork_lsc']}", "Clicks from CLOSED")
    
    if res['fork_valve_mismatch']:
        st.warning(f"⚠️ **Valve Compensation Active**")
        action = "Lowered" if res['fork_support_delta'] > 0 else "Increased"
        st.caption(f"• PSI/LSC {action} for {res['fork_cts']} support.")
    
    if is_rec:
        st.warning("⚠️ Recovery Safety: Neopos reduced.")

# PDF Generation
def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "Nukeproof Mega v4 Setup Report", ln=True, align='C')
    pdf.set_font("Arial", size=11); pdf.ln(10)
    
    pdf.cell(200, 8, f"Rider: {rider_kg}kg | Bike: {bike_kg}kg", ln=True)
    pdf.cell(200, 8, f"Style: {style_key} | Weather: {weather}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Tires", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, f"Front: {data['tire_front']:.1f} psi", ln=True)
    pdf.cell(200, 8, f"Rear: {data['tire_rear']:.1f} psi", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Formula MOD", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, f"Rate: {data['active_rate']} lbs | Valve: {data['shock_cts']}", ln=True)
    pdf.cell(200, 8, f"Rebound: {data['shock_reb']} clicks", ln=True)
    pdf.cell(200, 8, f"Compression: {data['shock_lsc']} clicks", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Formula Selva V", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 8, f"Pressure: {data['fork_psi']:.1f} psi", ln=True)
    pdf.cell(200, 8, f"Neopos: {data['fork_neopos']} | Valve: {data['fork_cts']}", ln=True)
    pdf.cell(200, 8, f"Rebound: {data['fork_reb']} clicks", ln=True)
    pdf.cell(200, 8, f"Compression: {data['fork_lsc']} clicks", ln=True)
    
    return pdf.output(dest="S").encode("latin-1")

if st.button("Export PDF Report"):
    try:
        pdf_bytes = generate_pdf(res)
        st.download_button("Download PDF", pdf_bytes, "setup_report.pdf", "application/pdf")
    except Exception as e:
        st.error(f"PDF Error: {e}")

st.caption("Calculations valid for Nukeproof Mega v4 (2020-2026) + Formula Selva V 2025 + Formula Mod 2025")
