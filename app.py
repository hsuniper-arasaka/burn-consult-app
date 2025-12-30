import streamlit as st

# =============================
# Checklist labels (main checkboxes)
# =============================
CHECKLIST = {
    "mechanism_documented": "Mechanism documented",
    "time_of_injury": "Time of injury documented",
    "morphology_burn_consistent": "Morphology consistent with burn",
    "depth_estimated": "Depth estimated",
    "tbsa_estimated": "TBSA estimated",
    "location_high_risk_checked": "High-risk areas assessed",
    "circumferential_checked": "Circumferential involvement assessed",
    "chemical_agent_known_if_chemical": "If chemical: agent identified + decontamination documented",
    "electrical_voltage_known_if_electrical": "If electrical: voltage/LOC/ECG documented",
    "inhalation_risk_assessed": "Inhalation risk assessed",
    "inhalation_risk_present": "Inhalation risk PRESENT",
    "vitals_reviewed": "Vitals reviewed / instability assessed",
    "comorbidities_reviewed": "Major comorbidities reviewed",
    "consult_question_defined": "Consult question defined (what do you want Burn to do?)",
    "severe_skin_failure_flag": "Severe skin failure suspected (e.g., SJS/TEN pattern)",
}

# =============================
# Helpers
# =============================
def two_col_checkboxes(options, key_prefix):
    """Return list of selected options using 2-column checkbox layout."""
    selected = []
    cols = st.columns(2)
    for i, opt in enumerate(options):
        col = cols[i % 2]
        if col.checkbox(opt, key=f"{key_prefix}_{i}"):
            selected.append(opt)
    return selected

def add_detail(details: dict, label: str, value: str):
    """Store only non-empty strings."""
    if isinstance(value, str) and value.strip():
        details[label] = value.strip()

def inferred_burn_evidence(details: dict) -> bool:
    """
    True if structured fields imply burn features were observed (depth/TBSA/morph features),
    even if the user forgot to check the main morphology checkbox.
    """
    depth = details.get("Depth (structured)", "")
    depth_implies = depth in ["Superficial", "Superficial partial", "Deep partial", "Full thickness"]

    tbsa_text = details.get("TBSA % (structured)", "")
    tbsa_implies = False
    try:
        tbsa_implies = float(tbsa_text.replace("%", "").strip()) > 0
    except:
        tbsa_implies = False

    morph_struct = details.get("Morphology (structured)", "")
    morph_implies = bool(morph_struct.strip())

    return depth_implies or tbsa_implies or morph_implies

# =============================
# Readiness scoring (based ONLY on main checkboxes)
# =============================
def burn_consult_readiness_v2(inputs: dict):
    mech_type = inputs.get("mechanism_type", "unknown")

    required_keys = [
        "mechanism_documented",
        "time_of_injury",
        "morphology_burn_consistent",
        "depth_estimated",
        "tbsa_estimated",
        "location_high_risk_checked",
        "circumferential_checked",
        "vitals_reviewed",
        "comorbidities_reviewed",
        "consult_question_defined",
        "inhalation_risk_assessed",
        "inhalation_risk_present",
    ]

    if mech_type == "chemical":
        required_keys.append("chemical_agent_known_if_chemical")
    if mech_type == "electrical":
        required_keys.append("electrical_voltage_known_if_electrical")

    done = [k for k in required_keys if inputs.get(k) is True]
    missing = [k for k in required_keys if inputs.get(k) is not True]

    return {
        "completeness_pct": round(len(done) / len(required_keys) * 100, 1),
        "missing_items": [CHECKLIST[k] for k in missing if k in CHECKLIST],
    }

# =============================
# Scope triage (based ONLY on main checkboxes + special mechanisms)
# =============================
def scope_triage_v2(inputs: dict):
    mech = inputs.get("mechanism_documented") is True
    morph = inputs.get("morphology_burn_consistent") is True

    chemical = inputs.get("chemical_agent_known_if_chemical") is True
    electrical = inputs.get("electrical_voltage_known_if_electrical") is True
    inhalation = inputs.get("inhalation_risk_present") is True

    if mech and morph:
        return "WITHIN SCOPE", "Burn-consistent mechanism and morphology."
    if chemical or electrical or inhalation:
        return "WITHIN SCOPE", "Special burn mechanism present."
    if not mech or not morph:
        return "OUTSIDE OF SCOPE", "Mechanism or morphology not consistent with burn."
    return "UNCERTAIN", "Insufficient data to confirm burn scope."

# =============================
# Recommendation tier (based ONLY on main checkboxes)
# =============================
def recommendation_tier_v2(inputs: dict, completeness: float, scope: str):
    high_risk = inputs.get("location_high_risk_checked") is True
    special = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if scope == "OUTSIDE OF SCOPE":
        return "CONSIDER ALTERNATE SERVICE"

    if scope == "WITHIN SCOPE" and (special or high_risk):
        return "CONSULT NOW"

    if scope == "WITHIN SCOPE":
        return "STRONGLY RECOMMEND BURN SURGERY CONSULT" if completeness >= 70 else "LOW RECOMMENDATION FOR BURN SURGERY CONSULT"

    return "CONSIDER ALTERNATE SERVICE"

# =============================
# Message generator (human prose)
# =============================
def generate_message_v5(inputs, scope, why, missing):
    missing_short = "; ".join(missing[:4]) if missing else ""
    severe_skin = inputs.get("severe_skin_failure_flag") is True

    if scope == "OUTSIDE OF SCOPE":
        if severe_skin:
            msg = (
                f"{why} The presentation suggests a severe non-burn skin process. "
                "Recommend urgent multidisciplinary evaluation per local protocol. "
                "Escalate appropriately. Burn Surgery can be re-consulted if burn features emerge."
            )
        else:
            msg = (
                f"{why} Burn Surgery involvement is not clearly indicated at this time. "
                "Recommend evaluation by an alternate appropriate service per local protocol. "
                "Re-consult Burn Surgery if burn-consistent features develop."
            )
        if missing_short:
            msg += f" Missing elements: {missing_short}."
        return msg

    msg = (
        "Recommend Burn Surgery consultation to assist with depth/TBSA assessment "
        "and determine need for burn-center evaluation or transfer. "
        f"Rationale: {why}"
    )
    if missing_short:
        msg += f" Missing elements being obtained: {missing_short}."
    return msg

# =============================
# Streamlit UI
# =============================
st.set_page_config(page_title="Burn Consult Tool", layout="wide")
st.title("Burn Consult Readiness Tool")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

left, right = st.columns(2)

with left:
    st.subheader("Inputs")

    mechanism_type = st.selectbox(
        "Mechanism type (overall)",
        ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
        index=0
    )

    inputs = {"mechanism_type": mechanism_type}
    details = {}  # label -> string

    # -------------------------
    # Core burn assessment
    # -------------------------
    st.markdown("## Core burn assessment")

    # Mechanism
    inputs["mechanism_documented"] = st.checkbox(CHECKLIST["mechanism_documented"], key="mech_main")
    if inputs["mechanism_documented"]:
        mech_opts = ["Scald", "Flame", "Contact", "Friction", "Flash", "Hot oil/grease", "Steam", "Unknown/unclear"]
        mech_selected = two_col_checkboxes(mech_opts, "mech_opt")
        add_detail(details, "Mechanism (structured)", ", ".join(mech_selected))

        mech_text = st.text_area(
            "Mechanism details (free text)",
            height=80,
            placeholder="Example: hot water scald to R forearm while cooking; no chemical/electrical exposure; occurred ~18:30.",
            key="mech_txt"
        )
        add_detail(details, "Mechanism (free text)", mech_text)

    # Time of injury
    inputs["time_of_injury"] = st.checkbox(CHECKLIST["time_of_injury"], key="toi_main")
    if inputs["time_of_injury"]:
        toi_bucket = st.radio(
            "Timeframe (structured)",
            ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
            horizontal=True,
            key="toi_bucket"
        )
        add_detail(details, "Timeframe (structured)", toi_bucket)

        toi_text = st.text_area(
            "Time of injury details (free text)",
            height=70,
            placeholder="Include approximate time + delayed presentation + progression since injury.",
            key="toi_txt"
        )
        add_detail(details, "Time of injury (free text)", toi_text)

    # Morphology
    inputs["morphology_burn_consistent"] = st.checkbox(CHECKLIST["morphology_burn_consistent"], key="morph_main")
    if inputs["morphology_burn_consistent"]:
        morph_opts = ["Blistering/bullae", "Eschar/leathery", "Sloughing/tissue loss", "Erythema only", "Uncertain/mixed"]
        morph_selected = two_col_checkboxes(morph_opts, "morph_opt")
        add_detail(details, "Morphology (structured)", ", ".join(morph_selected))

        morph_text = st.text_area(
            "Morphology notes (free text)",
            height=70,
            placeholder="Optional: distribution, photos, alternative diagnosis concerns.",
            key="morph_txt"
        )
        add_detail(details, "Morphology (free text)", morph_text)

    # Depth
    inputs["depth_estimated"] = st.checkbox(CHECKLIST["depth_estimated"], key="depth_main")
    if inputs["depth_estimated"]:
        depth_level = st.radio(
            "Depth estimate (structured)",
            ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
            horizontal=True,
            key="depth_level"
        )
        add_detail(details, "Depth (structured)", depth_level)

        depth_exam_opts = ["Blanching present", "Blanching absent", "Sensation intact", "Sensation decreased", "Sensation absent", "Moist/weeping", "Dry/leathery"]
        depth_exam = two_col_checkboxes(depth_exam_opts, "depth_exam")
        add_detail(details, "Depth exam clues (structured)", ", ".join(depth_exam))

        depth_text = st.text_area(
            "Depth rationale (free text)",
            height=70,
            placeholder="Explain why: sensation, blanching, cap refill, appearance.",
            key="depth_txt"
        )
        add_detail(details, "Depth rationale (free text)", depth_text)

    # TBSA
    inputs["tbsa_estimated"] = st.checkbox(CHECKLIST["tbsa_estimated"], key="tbsa_main")
    if inputs["tbsa_estimated"]:
        tbsa_pct = st.number_input("TBSA % (structured)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="tbsa_pct")
        add_detail(details, "TBSA % (structured)", f"{tbsa_pct:.1f}%")

        tbsa_method = st.selectbox("TBSA method (structured)", ["Rule of 9s", "Palm method", "Lund-Browder", "Other/unclear"], key="tbsa_method")
        add_detail(details, "TBSA method (structured)", tbsa_method)

        tbsa_text = st.text_area(
            "TBSA notes (free text)",
            height=60,
            placeholder="Optional: which regions involved; anything uncertain.",
            key="tbsa_txt"
        )
        add_detail(details, "TBSA notes (free text)", tbsa_text)

    # High-risk areas
    inputs["location_high_risk_checked"] = st.checkbox(CHECKLIST["location_high_risk_checked"], key="loc_main")
    if inputs["location_high_risk_checked"]:
        loc_opts = ["Face", "Eyes/periorbital", "Hands", "Feet", "Genitals/perineum", "Major joints"]
        loc_selected = two_col_checkboxes(loc_opts, "loc_opt")
        add_detail(details, "High-risk locations (structured)", ", ".join(loc_selected))

        loc_text = st.text_area(
            "High-risk location notes (free text)",
            height=60,
            placeholder="Specify exact location(s), laterality, functional concerns.",
            key="loc_txt"
        )
        add_detail(details, "High-risk location notes (free text)", loc_text)

    # Circumferential
    inputs["circumferential_checked"] = st.checkbox(CHECKLIST["circumferential_checked"], key="circ_main")
    if inputs["circumferential_checked"]:
        circ_yes = st.radio("Circumferential burn? (structured)", ["No", "Yes", "Uncertain"], horizontal=True, key="circ_yes")
        add_detail(details, "Circumferential (structured)", circ_yes)

        perf_opts = ["Distal pulses palpable", "Doppler signals present", "Cap refill normal", "Cap refill delayed", "Increasing pain/tightness", "Paresthesias/numbness"]
        perf_selected = two_col_checkboxes(perf_opts, "perf_opt")
        add_detail(details, "Perfusion/compartment clues (structured)", ", ".join(perf_selected))

        circ_text = st.text_area(
            "Circumferential/perfusion notes (free text)",
            height=70,
            placeholder="Which limb/segment? pulses/cap refill/sensation? concern for escharotomy?",
            key="circ_txt"
        )
        add_detail(details, "Circumferential/perfusion notes (free text)", circ_text)

    # -------------------------
    # Inhalation
    # -------------------------
    st.markdown("## Inhalation")

    inputs["inhalation_risk_assessed"] = st.checkbox(CHECKLIST["inhalation_risk_assessed"], key="inh_assessed_main")
    if inputs["inhalation_risk_assessed"]:
        inh_risk_opts = ["Enclosed space exposure", "Smoke inhalation", "Soot in nares/oropharynx", "Singed nasal hairs", "Hoarseness/voice change", "Wheezing", "Stridor"]
        inh_risk = two_col_checkboxes(inh_risk_opts, "inh_risk")
        add_detail(details, "Inhalation risk factors (structured)", ", ".join(inh_risk))

        inh_text = st.text_area(
            "Inhalation assessment notes (free text)",
            height=70,
            placeholder="Airway exam, O2 requirement, respiratory symptoms, any COHb/ABG/bronch if done.",
            key="inh_assessed_txt"
        )
        add_detail(details, "Inhalation assessment notes (free text)", inh_text)

    inputs["inhalation_risk_present"] = st.checkbox(CHECKLIST["inhalation_risk_present"], key="inh_present_main")
    if inputs["inhalation_risk_present"]:
        inh_present_opts = ["Respiratory distress", "Hypoxia", "Carbonaceous sputum", "Intubated", "Progressive airway edema concern"]
        inh_present = two_col_checkboxes(inh_present_opts, "inh_present")
        add_detail(details, "Inhalation present indicators (structured)", ", ".join(inh_present))

        inh_present_text = st.text_area(
            "Inhalation present rationale (free text)",
            height=70,
            placeholder="What makes you confident inhalation injury is present?",
            key="inh_present_txt"
        )
        add_detail(details, "Inhalation present rationale (free text)", inh_present_text)

    # -------------------------
    # Vitals / context
    # -------------------------
    st.markdown("## Vitals / context")

    inputs["vitals_reviewed"] = st.checkbox(CHECKLIST["vitals_reviewed"], key="vitals_main")
    if inputs["vitals_reviewed"]:
        instability_opts = ["Tachycardia", "Hypotension", "Fever", "Hypoxia", "Altered mental status", "Shock/sepsis concern"]
        instability = two_col_checkboxes(instability_opts, "instab_opt")
        add_detail(details, "Instability flags (structured)", ", ".join(instability))

        vitals_text = st.text_area(
            "Vitals/trends (free text)",
            height=70,
            placeholder="BP/HR/RR/O2/temp + trend + interventions (fluids, oxygen, pressors).",
            key="vitals_txt"
        )
        add_detail(details, "Vitals/trends (free text)", vitals_text)

    inputs["comorbidities_reviewed"] = st.checkbox(CHECKLIST["comorbidities_reviewed"], key="pmh_main")
    if inputs["comorbidities_reviewed"]:
        pmh_opts = ["Diabetes", "CAD/CHF", "COPD", "ESRD/dialysis", "Cirrhosis", "Immunosuppressed/transplant", "Steroids/chemo", "Anticoag/antiplatelet", "Substance use"]
        pmh_selected = two_col_checkboxes(pmh_opts, "pmh_opt")
        add_detail(details, "Comorbidities (structured)", ", ".join(pmh_selected))

        pmh_text = st.text_area(
            "Comorbidities/meds (free text)",
            height=70,
            placeholder="Relevant PMH + meds that impact healing/infection/bleeding/pain control.",
            key="pmh_txt"
        )
        add_detail(details, "Comorbidities/meds (free text)", pmh_text)

    # -------------------------
    # Consult question (PRIMARY objective only)
    # -------------------------
    inputs["consult_question_defined"] = st.checkbox(CHECKLIST["consult_question_defined"], key="q_main")
    if inputs["consult_question_defined"]:
        primary_q = st.radio(
            "Primary reason for Burn Surgery consult (choose ONE)",
            [
                "Confirm burn depth and TBSA",
                "Determine need for burn-center transfer",
                "Admission vs outpatient management guidance",
                "Urgent operative / intervention concern (e.g., debridement, escharotomy)",
                "Airway or inhalation injury guidance",
                "Other (specify below)",
            ],
            key="q_primary"
        )
        add_detail(details, "Primary consult objective", primary_q)

        secondary_q = st.text_area(
            "Additional concerns / secondary questions (optional)",
            height=70,
            placeholder="Optional nuance. Example: circumferential concern, delayed presentation, alternative diagnosis concerns.",
            key="q_secondary"
        )
        add_detail(details, "Secondary consult considerations", secondary_q)

    # -------------------------
    # Special cases
    # -------------------------
    st.markdown("## Special cases")

    inputs["severe_skin_failure_flag"] = st.checkbox(CHECKLIST["severe_skin_failure_flag"], key="skin_main")
    if inputs["severe_skin_failure_flag"]:
        skin_opts = ["Mucosal involvement", "Diffuse desquamation", "New medication trigger", "Ocular involvement", "Nikolsky-like", "Systemic toxicity"]
        skin_selected = two_col_checkboxes(skin_opts, "skin_opt")
        add_detail(details, "Severe skin failure clues (structured)", ", ".join(skin_selected))

        skin_text = st.text_area(
            "Severe skin failure notes (free text)",
            height=70,
            placeholder="Why SJS/TEN concern? distribution, mucosa, meds, timeline, vitals.",
            key="skin_txt"
        )
        add_detail(details, "Severe skin failure notes (free text)", skin_text)

    # -------------------------
    # Mechanism-specific fields
    # -------------------------
    st.markdown("## Mechanism-specific fields")

    if mechanism_type == "chemical":
        inputs["chemical_agent_known_if_chemical"] = st.checkbox(CHECKLIST["chemical_agent_known_if_chemical"], key="chem_main")
        if inputs["chemical_agent_known_if_chemical"]:
            chem_opts = ["Agent identified", "Decontamination performed", "Irrigation documented", "pH checks performed (if relevant)"]
            chem_selected = two_col_checkboxes(chem_opts, "chem_opt")
            add_detail(details, "Chemical care (structured)", ", ".join(chem_selected))

            chem_text = st.text_area(
                "Chemical details (free text)",
                height=70,
                placeholder="Agent, exposure duration, decon/irrigation details, symptoms, pH if used.",
                key="chem_txt"
            )
            add_detail(details, "Chemical details (free text)", chem_text)
    else:
        inputs["chemical_agent_known_if_chemical"] = None

    if mechanism_type == "electrical":
        inputs["electrical_voltage_known_if_electrical"] = st.checkbox(CHECKLIST["electrical_voltage_known_if_electrical"], key="elec_main")
        if inputs["electrical_voltage_known_if_electrical"]:
            elec_opts = ["High voltage concern", "LOC reported", "ECG obtained", "Arrhythmia concern", "Entry/exit wounds assessed"]
            elec_selected = two_col_checkboxes(elec_opts, "elec_opt")
            add_detail(details, "Electrical evaluation (structured)", ", ".join(elec_selected))

            elec_text = st.text_area(
                "Electrical details (free text)",
                height=70,
                placeholder="Voltage if known, LOC, ECG findings, symptoms, entry/exit wounds.",
                key="elec_txt"
            )
            add_detail(details, "Electrical details (free text)", elec_text)
    else:
        inputs["electrical_voltage_known_if_electrical"] = None

with right:
    st.subheader("Output")

    # Readiness based on main checkboxes only
    r = burn_consult_readiness_v2(inputs)

    # Contradiction patch (logic copy only)
    burn_evidence = inferred_burn_evidence(details)
    inputs_for_logic = inputs.copy()
    if burn_evidence and not inputs.get("morphology_burn_consistent", False):
        inputs_for_logic["morphology_burn_consistent"] = True

    scope, why = scope_triage_v2(inputs_for_logic)
    tier = recommendation_tier_v2(inputs_for_logic, r["completeness_pct"], scope)
    msg = generate_message_v5(inputs_for_logic, scope, why, r["missing_items"])

    st.metric("Scope", scope)
    st.metric("Recommendation", tier)
    st.metric("Readiness %", f"{r['completeness_pct']}%")

    if burn_evidence and not inputs.get("morphology_burn_consistent", False):
        st.warning(
            "Possible inconsistency: you entered depth/TBSA/morphology features suggesting a burn, "
            "but 'Morphology consistent with burn' is unchecked. "
            "Either check it (if appropriate) or revise depth/TBSA to uncertain/0."
        )

    # Paste-ready details block (structured + free text)
    if details:
        lines = [f"- {k}: {v}" for k, v in details.items()]
        details_block = "\n".join(lines)
        msg2 = msg + "\n\nKey details documented:\n" + details_block
    else:
        msg2 = msg

    st.markdown("### Paste-ready message")
    st.code(msg2)

    st.markdown("### Top missing items")
    for item in r["missing_items"][:6]:
        st.write(f"- {item}")
