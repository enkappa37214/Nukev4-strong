import streamlit as st
import pandas as pd
from fpdf import FPDF
import locale
import streamlit.components.v1 as components 

# Set locale for consistent number formatting
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')

# ==========================================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================================
st.set_page_config(page_title="Nukeproof Mega v4 - Formula Expert", page_icon="⚡", layout="centered")

# Force Scroll to Top on Refresh
components.html(
    """
    <script>
        window.parent.document.querySelector("section.main").scrollTo(0, 0);
    </script>
    """, 
    height=0
)

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

# --- KINEMATIC CONSTANTS (Mega v4 Specifics) ---
KINEMATIC_MAP = {
    "BASE_RING": 32,             # Optimized chainring size
    "LSC_PER_TOOTH": 0.5,        # LSC Clicks per tooth delta
    "KICKBACK_REB_OFFSET": 2,    # Clicks to open Rebound (Faster)
    "GEO_CORRECTION_LSC": -1     # Clicks to soften Fork LSC
}

# --- DATA DICTIONARIES ---

STYLES = {
    "Flow / Park":       {"sag": 30.0, "bias": 63, "lsc_offset": -3, "desc": "Max Support. Forward bias."},
    "Dynamic":           {"sag": 31.0, "bias": 65, "lsc_offset": 0, "desc": "Balanced Enduro bias."},
    "Alpine Epic":       {"sag": 32.0, "bias": 65, "lsc_offset": -1, "desc": "Efficiency focus. Neutral bias."},
    "Trail":             {"sag": 33.0, "bias": 65, "lsc_offset": 0, "desc": "Chatter focus."},
    "Steep / Tech":      {"sag": 34.0, "bias": 68, "lsc_offset": -2, "desc": "Geometry focus. Rearward bias."},
    "Plush":             {"sag": 35.0, "bias": 65, "lsc_offset": 4, "desc": "Comfort max."}
}

FORK_VALVE_SPECS = {
    "Purple": {"support": 2, "ramp": 2}, 
    "Blue":   {"support": 3, "ramp": 7}, 
    "Gold":   {"support": 5, "ramp": 5}, 
    "Orange": {"support": 7, "ramp": 6}, 
    "Green":  {"support": 8, "ramp": 8}, 
    "Bronze": {"support": 2, "ramp": 9}, 
    "Red":    {"support": 6, "ramp": 7}, 
}

SHOCK_VALVE_SPECS = {
    "Gold":   {"support": 3, "ramp": 3},
    "Orange": {"support": 5, "ramp": 5},
    "Green":  {"support": 8, "ramp": 8},
}

TIRE_CASINGS = {
    "Standard (EXO/SnakeSkin)": 0.0,
    "Reinforced (DD/SuperGravity)": -1.0,
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

# --- DIAGNOSTIC KNOWLEDGE BASE ---
DIAGNOSTIC_PROBLEMS = {
    "None (Fresh Setup)": {"action": "none", "msg": ""},
    
    # --- FRONT END ---
    "Front: Washing out in corners": {
        "diagnosis": "Fork staying too high, tire not loading.",
        "action": "soften_fork_lsc",
        "value": 2,
        "msg": "Opened Fork LSC (+2) to help load the front tire."
    },
    "Front: Diving under braking": {
        "diagnosis": "Fork collapsing under mass transfer.",
        "action": "stiffen_fork_lsc",
        "value": -2,
        "msg": "Closed Fork LSC (-2) to add chassis support."
    },
    "Front: Harsh Spiking (Roots/Rocks)": { 
        "diagnosis": "High-speed oil flow restricted. Valve is too stiff.",
        "action": "softer_fork_valve", 
        "value": "Gold", 
        "msg": "⚠️ **Hardware Limit:** Clickers cannot fix high-speed spiking. Switch to a Softer CTS Valve (e.g., Gold)."
    },
    
    # --- REAR END ---
    "Rear: Bucking on jumps (OTB)": {
        "diagnosis": "Shock releasing energy too fast.",
        "action": "slow_shock_reb",
        "value": -2,
        "msg": "Slowed Shock Rebound (-2) to control return energy."
    },
        "Rear: Harsh Bottom Out": { 
        "diagnosis": "Spring rate insufficient for hit size.",
        "action": "increase_spring_dynamic", 
        "value": 0.05, # Represents a 5% increase
        "msg": "⚠️ **Hardware Limit:** Hydraulics overwhelmed. Increase Sprindex by 15-25 lbs based on current feel."
    },
    "Rear: Top-stroke harshness": { 
        "diagnosis": "Excessive preload fighting initial movement.",
        "action": "check_preload",
        "value": 0,
        "msg": "⚠️ **Setup Check:** Ensure Spring Preload is < 2 turns. If sag is low, go down a spring rate."
    },

    # --- CHASSIS ---
    "Chassis: Dead / No Pop": {
        "diagnosis": "System over-damped, absorbing all energy.",
        "action": "speed_global_reb",
        "value": 2,
        "msg": "Opened Rebound F&R (+2) to bring the life back."
    },
    "Chassis: Pitching Forward (Seesaw)": { 
        "diagnosis": "Rear pushing front down (Rebound imbalance).",
        "action": "balance_pitch",
        "value": 0,
        "msg": "Slowed Rear Rebound (-2) and Sped up Fork Rebound (+1) to level the chassis."
    }
}

# --- STATE MANAGEMENT ---
DEFAULTS = {
    "rider_kg": 72.0,
    "bike_kg": 15.1,
    "unsprung_kg": 4.27,
    "is_rec": False,
    "chainring_size": 32,
    "temperature": "Standard (>10°C)",
    "trail_condition": "Dry",
    "altitude": 500,
    "style_select": "Trail",
    "previous_style": "Trail",
    "sag_slider": 33.0,
    "bias_slider": 65,
    "spring_override": "Auto",
    "neopos_override": "Auto",
    "valve_override": "Auto",
    "shock_valve_override": "Auto",
    "tire_casing_front": "Reinforced (DD/SuperGravity)",
    "tire_casing_rear": "Reinforced (DD/SuperGravity)",
    "tire_width": "2.3\" - 2.4\"",
    "tire_insert": "None",
    "is_tubeless": True,
    "problem_select": "None (Fresh Setup)"
}

# --- CALLBACKS ---
def reset_form_callback():
    st.session_state.clear() 

def initialize_state():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

def update_style_logic():
    if not st.session_state.get('is_rec', False):
        s_key = st.session_state.style_select
        if s_key in STYLES:
            st.session_state.sag_slider = STYLES[s_key]["sag"]
            st.session_state.bias_slider = STYLES[s_key]["bias"]

def update_rec_logic():
    if st.session_state.is_rec:
        st.session_state.previous_style = st.session_state.style_select
        st.session_state.style_select = "Plush"
        st.session_state.sag_slider = 35.0
    else:
        st.session_state.style_select = st.session_state.get("previous_style", "Trail")
        update_style_logic()

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

def calculate_setup(rider_kg, bike_kg, unsprung_kg, style_key, sag_target, bias_manual, altitude, temperature, trail_condition, is_recovery, chainring_size, neopos_select, spring_override, fork_valve_override, shock_valve_override, tire_casing_front, tire_casing_rear, tire_width, tire_insert, is_tubeless, problem_select):
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

    # --- ADVANCED WEATHER LOGIC ---
    reb_adj_shock = 0
    lsc_adj_shock = 0
    reb_adj_fork = 0
    lsc_adj_fork = 0
    fork_psi_mult = 1.0
    tire_psi_adj = 0.0

    # 1. Temperature Logic
    if temperature == "Cool (0-10°C)":
        reb_adj_shock += 2; lsc_adj_shock += 1
        reb_adj_fork += 2; lsc_adj_fork += 1
        fork_psi_mult = 1.02 
    elif temperature == "Freezing (<0°C)":
        reb_adj_shock += 5; lsc_adj_shock += 3
        reb_adj_fork += 5; lsc_adj_fork += 2
        fork_psi_mult = 1.05 

    # 2. Condition Logic
    if trail_condition == "Wet":
        lsc_adj_shock += 1; lsc_adj_fork += 1  
        tire_psi_adj -= 1.0
    elif trail_condition == "Mud":
        lsc_adj_shock += 2; lsc_adj_fork += 2  
        tire_psi_adj -= 2.0
    
    if temperature == "Freezing (<0°C)" and trail_condition == "Dry":
        tire_psi_adj -= 1.0

    # --- DIAGNOSTIC LAYER (Post-Physics) ---
    diag_shock_reb = 0
    diag_shock_lsc = 0
    diag_fork_reb = 0
    diag_fork_lsc = 0
    diag_msg = None
    hardware_msg = None
    
    if problem_select != "None (Fresh Setup)":
        task = DIAGNOSTIC_PROBLEMS.get(problem_select, {})
        action = task.get("action", "")
        val = task.get("value", 0)
        diag_msg = task.get("msg", "")
        
        # Parse Actions
        if action == "soften_fork_lsc": diag_fork_lsc += val
        elif action == "stiffen_fork_lsc": diag_fork_lsc += val
        elif action == "slow_shock_reb": diag_shock_reb += val
        elif action == "speed_global_reb":
            diag_shock_reb += val
            diag_fork_reb += val
        elif action == "balance_pitch":
            diag_shock_reb -= 2
            diag_fork_reb += 1
        # Hardware Flags
        if action == "increase_spring_dynamic":
            # Calculate 5% of ideal rate, rounded to nearest 5 lbs for Sprindex
            adjustment = round((ideal_rate_exact * val) / 5) * 5
            adjustment = max(10, adjustment) 
            hardware_msg = f"⚠️ **Hardware Limit:** Increase Sprindex by **{adjustment} lbs** to stop harsh bottom-out."
        elif action in ["softer_fork_valve", "check_preload"]:
            hardware_msg = diag_msg

    # --- KINEMATIC LOGIC LAYER (NEW) ---
    kinematic_notes = []

    # 1. CHAINRING & ANTI-SQUAT (Rear Support)
    # Physics: Larger ring = Less Anti-Squat = Needs more LSC
    ring_delta = chainring_size - KINEMATIC_MAP["BASE_RING"]
    # Physics: Deeper sag = Less Anti-Squat = Needs more LSC
    sag_depth_delta = max(0, final_sag_pct - 30.0)
    
    as_lsc_comp = (ring_delta * KINEMATIC_MAP["LSC_PER_TOOTH"]) + (sag_depth_delta * 0.2)
    
    if is_recovery:
        as_lsc_comp *= 0.5 # Relax support in recovery
        
    as_lsc_comp_int = int(round(as_lsc_comp))
    if as_lsc_comp_int != 0:
        kinematic_notes.append(f"Anti-Squat ({as_lsc_comp_int:+} LSC)")

    # 2. DYNAMIC GEOMETRY (Chassis Pitch)
    # Physics: Deep rear + Stiff front = Chopper (Understeer). Soften front to level chassis.
    pitch_imbalance = 0
    if final_sag_pct >= 34.0 and fork_valve_active in ["Green", "Orange", "Gold"]:
        pitch_imbalance = KINEMATIC_MAP["GEO_CORRECTION_LSC"]
        if not is_recovery:
             kinematic_notes.append("Geo Correction (-Fork LSC)")

    # 3. KICKBACK & CHAIN GROWTH (Return Speed)
    # Physics: High chain tension fights return. Speed up rebound to compensate.
    kickback_reb_mod = 0
    if style_key in ["Steep / Tech", "Plush"] or is_recovery:
        kickback_reb_mod = KINEMATIC_MAP["KICKBACK_REB_OFFSET"]
        if is_recovery: kickback_reb_mod += 1
        kinematic_notes.append(f"Kickback Mgmt (+{kickback_reb_mod} Reb)")

    # --- FINAL DAMPING APPLY ---
    # Shock Rebound
    reb_clicks = 7 - int((active_rate - 450) / 50)
    reb_clicks += reb_adj_shock + diag_shock_reb
    # Apply Kinematics
    reb_clicks += kickback_reb_mod
    reb_clicks = max(1, min(CONFIG["REBOUND_CLICKS_SHOCK"], reb_clicks))
    
    # Shock Compression
    lsc_spring_comp = int(rate_mismatch / 25) 
    neopos_delta = neopos_installed - neopos_rec
    lsc_chassis_bal = 0
    if neopos_delta < 0: lsc_chassis_bal = -abs(neopos_delta)
    lsc_shock_valve_offset = int(shock_support_delta * 1.5)

    base_lsc = 9 + s_data["lsc_offset"] + lsc_spring_comp + lsc_chassis_bal + lsc_shock_valve_offset
    if final_sag_pct > 32.0 and not is_recovery: base_lsc -= 1
    
    base_lsc += lsc_adj_shock + diag_shock_lsc
    # Apply Kinematics
    base_lsc += as_lsc_comp_int
    
    if is_recovery: base_lsc = 17 
    lsc_clicks = max(1, min(CONFIG["COMP_CLICKS_SHOCK"], base_lsc))

    # Fork
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
    final_psi = final_psi * fork_psi_mult
    
    # Fork Rebound
    fork_reb = 10 - int((final_psi - 70) / 10)
    fork_reb += reb_adj_fork + diag_fork_reb
    fork_reb = max(2, min(CONFIG["REBOUND_CLICKS_FORK"], fork_reb))
    
    # Fork Compression
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
    fork_lsc += lsc_adj_fork + diag_fork_lsc
    # Apply Kinematics
    fork_lsc += pitch_imbalance
    fork_lsc = max(0, min(12, fork_lsc))

    
        # --- TIRES (REFINED WITH MASS BIAS) ---
    weight_offset = (rider_kg - 75.0) / 5.0
    
    # Neutral bias is 65%. 
    # For every 1% increase in rear bias, add 0.2 psi to rear and subtract 0.2 psi from front.
    bias_shift = (effective_bias_pct - 65.0) * 0.2
    
    base_f = 23.0 + weight_offset - bias_shift
    base_r = 26.0 + weight_offset + bias_shift
    
    # Apply Casing Modifications
    casing_mod_f = TIRE_CASINGS.get(tire_casing_front, 0.0)
    base_f += casing_mod_f
    casing_mod_r = TIRE_CASINGS.get(tire_casing_rear, 0.0)
    base_r += casing_mod_r
    
    # Apply Width and Insert Modifications
    width_mod = TIRE_WIDTHS.get(tire_width, 0.0)
    base_f += width_mod
    base_r += width_mod
    
    insert_mod = TIRE_INSERTS.get(tire_insert, {"f": 0.0, "r": 0.0})
    base_f += insert_mod["f"]
    base_r += insert_mod["r"]
    
    # Tube Correction
    if not is_tubeless:
        base_f += 4.0
        base_r += 4.0
        
    # Style Specific Tweaks
    if style_key == "Flow / Park":
        base_f += 2.0; base_r += 2.0
    elif style_key == "Steep / Tech":
        base_f -= 1.0; base_r -= 1.0
    elif style_key == "Alpine Epic":
        base_f += 1.0; base_r += 1.0
    
    # Environmental Adjustment
    base_f += tire_psi_adj
    base_r += tire_psi_adj
    
    # Clamping and Final Calculation
    final_f_psi = max(18.0, min(35.0, base_f)) * fork_psi_mult
    final_r_psi = max(18.0, min(35.0, base_r)) * fork_psi_mult

    # Calculate Total Adjustment Values for Visualization
    shock_reb_total_adj = reb_adj_shock + diag_shock_reb
    shock_lsc_total_adj = lsc_adj_shock + diag_shock_lsc
    fork_reb_total_adj = reb_adj_fork + diag_fork_reb
    fork_lsc_total_adj = lsc_adj_fork + diag_fork_lsc

    return {
        "mod_rate": ideal_rate_exact,
        "active_rate": active_rate,
        "sag_actual": sag_actual_pct,
        "shock_reb": reb_clicks,
        "shock_lsc": lsc_clicks,
        "shock_reb_adj": shock_reb_total_adj,
        "shock_lsc_adj": shock_lsc_total_adj,
        "fork_psi": final_psi,
        "fork_cts": fork_valve_active,
        "shock_cts": shock_valve_active,
        "shock_cts_ideal": shock_valve_ideal,
        "fork_neopos": final_neopos_count,
        "neopos_rec": neopos_rec,
        "fork_reb": fork_reb,
        "fork_lsc": fork_lsc,
        "fork_reb_adj": fork_reb_total_adj,
        "fork_lsc_adj": fork_lsc_total_adj,
        "sag": final_sag_pct,
        "bias": effective_bias_pct,
        "fork_valve_mismatch": fork_valve_mismatch,
        "shock_valve_mismatch": shock_valve_mismatch,
        "fork_support_delta": fork_support_delta,
        "shock_support_delta": shock_support_delta,
        "tire_front": final_f_psi,
        "tire_rear": final_r_psi,
        "diag_msg": diag_msg,
        "hardware_msg": hardware_msg,
        "diag_shock_reb_val": diag_shock_reb,
        "diag_shock_lsc_val": diag_shock_lsc,
        "diag_fork_reb_val": diag_fork_reb,
        "diag_fork_lsc_val": diag_fork_lsc,
        "kinematic_notes": kinematic_notes
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
    temperature = st.selectbox("Temperature", ["Standard (>10°C)", "Cool (0-10°C)", "Freezing (<0°C)"], key="temperature")
    
with col_env2:
    chainring_size = st.selectbox("Chainring Size", [30, 32, 34, 36], index=1, key="chainring_size", help="Affects Anti-Squat. 30T=Crisp, 34T=Plush.")

col_alt, col_dummy = st.columns([0.5, 0.5])
with col_alt:
    trail_condition = st.selectbox("Trail Condition", ["Dry", "Wet", "Mud"], key="trail_condition")
with col_dummy:
    altitude = st.number_input("Max Altitude (m)", 0, 3000, step=50, key="altitude")

st.markdown("---")

st.subheader("2. Tuning")
col_style, col_sag, col_bias = st.columns(3)
with col_style:
    style_key = st.selectbox("Riding Style", list(STYLES.keys()), key="style_select", on_change=update_style_logic, disabled=st.session_state.is_rec)
with col_sag:
    target_sag = st.slider("Target Sag (%)", 30.0, 35.0, key="sag_slider", step=0.5, help="Nukeproof Kinematic Limit")
with col_bias:
    target_bias = st.slider("Rear Bias (%)", 55, 70, key="bias_slider", help="Applied to Sprung Mass")

st.markdown("---")
st.subheader("3. Tires")
t1, t2, t3, t4, t5 = st.columns(5)
with t1:
    tire_casing_front = st.selectbox("Front Casing", list(TIRE_CASINGS.keys()), key="tire_casing_front")
with t2:
    tire_casing_rear = st.selectbox("Rear Casing", list(TIRE_CASINGS.keys()), key="tire_casing_rear")
with t3:
    tire_width = st.selectbox("Width", list(TIRE_WIDTHS.keys()), key="tire_width")
with t4:
    tire_insert = st.selectbox("Inserts", list(TIRE_INSERTS.keys()), key="tire_insert")
with t5:
    st.write("") 
    st.write("") 
    is_tubeless = st.toggle("Tubeless", value=True, key="is_tubeless")

# [NEW] DIAGNOSTICS SECTION
st.markdown("---")
st.subheader("4. Diagnostics (Post-Ride)")
problem_select = st.selectbox(
    "Did you experience any issues?",
    list(DIAGNOSTIC_PROBLEMS.keys()),
    key="problem_select"
)

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
        spring_override = st.selectbox("Spring Rate (lbs)", options=spring_options, key="spring_override")
    with sc2:
        shock_valve_options = ["Auto"] + list(SHOCK_VALVE_SPECS.keys())
        shock_valve_select = st.selectbox("CTS Valve (Shock)", options=shock_valve_options, help="Select Gold, Orange, or Green.", key="shock_valve_override")

# --- RIGHT COLUMN (FORK) ---
with c2:
    st.subheader("Formula Selva V (Air)")
    
    fc1, fc2 = st.columns(2)
    with fc1:
        fork_valve_options = ["Auto"] + list(FORK_VALVE_SPECS.keys())
        fork_valve_select = st.selectbox("CTS Valve (Installed)", options=fork_valve_options, key="valve_override")
    with fc2:
        neopos_select = st.select_slider("Neopos (Installed)", options=["Auto", "0", "1", "2", "3"], help=f"Auto recommends: {rec_neopos_peek}.", key="neopos_override")

# --- RUN CALCULATION ---
res = calculate_setup(
    rider_kg, bike_kg, unsprung_kg, style_key, target_sag, target_bias, 
    altitude, temperature, trail_condition, is_rec, chainring_size, 
    neopos_select, spring_override, 
    fork_valve_select,
    shock_valve_select,
    tire_casing_front, tire_casing_rear, tire_width, tire_insert, 
    is_tubeless, problem_select
)

# --- DISPLAY RESULTS ---
st.markdown("### 🛞 Tire Pressure")
tp1, tp2 = st.columns(2)
tp1.metric("Front Tire (Indoor)", f"{res['tire_front']:.1f} psi")
tp2.metric("Rear Tire (Indoor)", f"{res['tire_rear']:.1f} psi")

if temperature != "Standard (>10°C)":
    st.info(f"**ℹ️ Winter Protocol:** Inflate tires to these pressures **Indoors**. They will drop ~{int((res['tire_front']*(1-(1/1.05))) if 'Freezing' in temperature else (res['tire_front']*(1-(1/1.02))))} PSI when exposed to outdoor cold.")

st.markdown("---")

# Display Diagnostic Message
if res['diag_msg']:
    st.info(f"🔧 **Diagnostic Active:** {res['diag_msg']}")

with c1:
    st.metric("Spring Rate", f"{res['active_rate']} lbs", delta=f"Ideal: {res['mod_rate']} lbs", delta_color="off")
    if abs(res['sag_actual'] - res['sag']) > 2.0:
        st.caption(f"⚠️ **Geometry Shift:** Estimated Sag {res['sag_actual']:.1f}%")
    
    # [HARDWARE WARNING - SHOCK]
    if res['hardware_msg'] and "Spring" in res['hardware_msg']:
        st.error(res['hardware_msg'])
    elif res['hardware_msg'] and "Preload" in res['hardware_msg']:
        st.warning(res['hardware_msg'])

    st.metric("CTS Valve", res['shock_cts'])

    d1, d2 = st.columns(2)
    
    # Custom Delta String for Shock
    d_reb_str = None
    if res['diag_shock_reb_val'] != 0: d_reb_str = f"{res['diag_shock_reb_val']:+d} (Diag)"
    elif res['shock_reb_adj'] != 0: d_reb_str = f"{res['shock_reb_adj']:+d} (Winter)"

    # Build Compression string with Kinematics
    d_lsc_str = []
    if res['diag_shock_lsc_val'] != 0: d_lsc_str.append(f"{res['diag_shock_lsc_val']:+d} (Diag)")
    if res['shock_lsc_adj'] != 0: d_lsc_str.append(f"{res['shock_lsc_adj']:+d} (Cond)")
    if res['kinematic_notes']: 
        for note in res['kinematic_notes']:
            if "Anti-Squat" in note: d_lsc_str.append(note)

    d1.metric("Rebound", f"{res['shock_reb']}", delta=d_reb_str)
    d2.metric("Compression", f"{res['shock_lsc']}", delta=", ".join(d_lsc_str) if d_lsc_str else None)
    
    if res['shock_valve_mismatch']:
        st.warning(f"⚠️ **Shock Compensation Active**")
        st.caption(f"Valve: {res['shock_cts']} (Ideal: {res['shock_cts_ideal']})")

with c2:
    st.metric("Pressure", f"{res['fork_psi']:.1f} psi", delta=f"Active: {res['fork_neopos']} Neopos")
    
    # [HARDWARE WARNING - FORK]
    if res['hardware_msg'] and "CTS Valve" in res['hardware_msg']:
        st.error(res['hardware_msg'])

    h1, h2 = st.columns(2)
    h1.metric("CTS Valve", res['fork_cts'])
    
    neo_label = f"{res['fork_neopos']}"
    if res['fork_neopos'] != res['neopos_rec']:
        neo_label += f" (Rec: {res['neopos_rec']})"
    h2.metric("Neopos Count", neo_label, delta_color="off")
    
    d3, d4 = st.columns(2)
    
    # Custom Delta String for Fork
    f_reb_str = None
    if res['diag_fork_reb_val'] != 0: f_reb_str = f"{res['diag_fork_reb_val']:+d} (Diag)"
    elif res['fork_reb_adj'] != 0: f_reb_str = f"{res['fork_reb_adj']:+d} (Winter)"

    f_lsc_str = []
    if res['diag_fork_lsc_val'] != 0: f_lsc_str.append(f"{res['diag_fork_lsc_val']:+d} (Diag)")
    if res['fork_lsc_adj'] != 0: f_lsc_str.append(f"{res['fork_lsc_adj']:+d} (Cond)")
    if res['kinematic_notes']: 
        for note in res['kinematic_notes']:
            if "Geo" in note: f_lsc_str.append(note)

    d3.metric("Rebound", f"{res['fork_reb']}", delta=f_reb_str)
    d4.metric("Compression", f"{res['fork_lsc']}", delta=", ".join(f_lsc_str) if f_lsc_str else None)
    
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
    pdf.cell(200, 8, f"Style: {style_key} | Temp: {temperature} | Cond: {trail_condition}", ln=True)
    if problem_select != "None (Fresh Setup)":
        pdf.set_text_color(200, 0, 0)
        pdf.cell(200, 8, f"Diagnostic Fix: {problem_select}", ln=True)
        pdf.set_text_color(0, 0, 0)
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12); pdf.cell(200, 10, "Tires (Inflation Targets)", ln=True)
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
