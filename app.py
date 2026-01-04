import streamlit as st

# =========================================================
# Helpers
# =========================================================
def add_detail(details: dict, label: str, value: str):
    """Store a detail if it has meaningful content."""
    if value is None:
        return
    v = str(value).strip()
    if v:
        details[label] = v

def two_col_checkboxes(options, key_prefix):
    """Render checkboxes in two columns; return list of selected option strings."""
    c1, c2 = st.columns(2)
    selected = []
    for i, opt in enumerate(options):
        col = c1 if i % 2 == 0 else c2
        if col.checkbox(opt, key=f"{key_prefix}__{i}"):
            selected.append(opt)
    return selected

# =========================================================
# Labels / checklist registry
# =========================================================
CHECKLIST = {
    "mechanism_documented": "Mechanism documented",
    "time_of_injury": "Time of injury documented",
    "morphology_burn_consistent": "Morphology consistent with burn",
    "depth_estimated": "Depth estimated",
    "tbsa_estimated": "TBSA estimated (%)",
    "location_high_risk_checked": "High-risk areas assessed",
    "circumferential_checked": "Circumferential involvement assessed",
    "chemical_agent_known_if_chemical": "If chemical: agent identified + decontamination documented",
    "electrical_voltage_known_if_electrical": "If electrical: voltage/LOC/ECG documented",
    "inhalation_risk_assessed": "Inhalation risk assessed",
    "vitals_reviewed": "Vitals reviewed / instability assessed",
    "comorbidities_reviewed": "Major comorbidities reviewed",
    "consult_question_defined": "Consult question defined (what do you want Burn to do?)",
    "severe_skin_failure_flag": "Severe skin failure suspected (e.g., SJS/TEN pattern)",
}

# =========================================================
# Readiness scoring
# =========================================================
def burn_consult_readiness(inputs: dict):
    """
    Readiness = are the core items documented?
    IMPORTANT: 'inhalation present' is NOT required.
    Only 'inhalation assessed' is required.
    """
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
        "inhalation_risk_assessed",  # required; present is NOT required
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

# =========================================================
# Scope triage
# =========================================================
def scope_triage(inputs: dict):
    mech = inputs.get("mechanism_documented") is True
    morph = inputs.get("morphology_burn_consistent") is True

    chemical = inputs.get("chemical_agent_known_if_chemical") is True
    electrical = inputs.get("electrical_voltage_known_if_electrical") is True
    inhalation_present = inputs.get("inhalation_risk_present") is True

    if mech and morph:
        return "WITHIN SCOPE", "Burn-consistent mechanism and morphology."
    if chemical or electrical or inhalation_present:
        return "WITHIN SCOPE", "Special burn mechanism present (chemical/electrical/inhalation)."
    if (not mech) or (not morph):
        return "OUTSIDE SCOPE", "Mechanism or morphology not consistent with burn."
    return "UNCERTAIN", "Insufficient data to confirm burn scope."

# =========================================================
# Recommendation tier
# =========================================================
def recommendation_tier(inputs: dict, completeness: float, scope: str):
    high_risk_area = inputs.get("location_high_risk_checked") is True
    special = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if scope == "OUTSIDE SCOPE":
        return "CONSIDER ALTERNATE SERVICE"

    if scope == "WITHIN SCOPE" and (special or high_risk_area):
        return "CONSULT NOW"

    if scope == "WITHIN SCOPE":
        return "STRONGLY RECOMMEND BURN SURGERY CONSULT" if completeness >= 70 else "LOW RECOMMENDATION FOR BURN SURGERY CONSULT"

    return "CONSIDER ALTERNATE SERVICE"

# =========================================================
# Message generator (human prose)
# =========================================================
def generate_message(inputs, scope, tier, why, missing_items, details: dict):
    missing_short = "; ".join(missing_items[:4]) if missing_items else ""

    # build detail block (optional)
    detail_lines = []
    if details:
        detail_lines.append("Key details documented:")
        for k, v in details.items():
            detail_lines.append(f"- {k}: {v}")
        detail_block = "\n" + "\n".join(detail_lines) + "\n"
    else:
        detail_block = ""

    severe_skin = inputs.get("severe_skin_failure_flag") is True

    if scope == "OUTSIDE SCOPE":
        if severe_skin:
            msg = (
                f"{why} The presentation suggests a severe non-burn skin process. "
                "Recommend urgent multidisciplinary evaluation per local protocol and escalation to the appropriate admitting team. "
                "Burn Surgery can be re-consulted if burn-consistent features emerge or if institutional pathways route severe skin failure to Burn."
            )
        else:
            msg = (
                f"{why} Burn Surgery involvement is not clearly indicated at this time. "
                "Recommend evaluation by an alternate appropriate service per local protocol. "
                "Re-consult Burn Surgery if burn-consistent mechanism/morphology becomes apparent, if high-risk anatomic involvement has burn-consistent findings, "
                "or if special mechanisms are suspected (chemical/electrical/inhalation)."
            )

        if missing_short:
            msg += f" Missing elements to clarify: {missing_short}."
        return msg + detail_block

    # WITHIN SCOPE
    msg = (
        "Recommend Burn Surgery consultation to assist with depth/TBSA assessment and determine the need for burn-center evaluation/transfer. "
        f"Rationale: {why}"
    )
    if missing_short:
        msg += f" Missing elements being obtained in parallel: {missing_short}."
    return msg + detail_block

# =========================================================
# Streamlit UI
# =========================================================
st.set_page_config(page_title="Burn Consult Tool", layout="wide")
st.title("Burn Consult Readiness Tool")
st.caption("Decision support only. Adapt to local protocols.")

left, right = st.columns([1.15, 1])

# -------------------------
# LEFT: Inputs
# -------------------------
with left:
    details = {}  # captured text to feed into consult message
    inputs = {}

    with st.form("burn_form", clear_on_submit=False):
    
        st.markdown("## Inputs")
    
        inputs["mechanism_type"] = st.selectbox(
            "Mechanism type (overall)",
            ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
            key="mech_type__v1",
        )
    
        st.markdown("## Core burn assessment")
    
        # Mechanism documented (with suboptions + free text)
        inputs["mechanism_documented"] = st.checkbox(CHECKLIST["mechanism_documented"], key="mech_doc__v1")
        if inputs["mechanism_documented"]:
            mech_opts = ["Scald", "Flame", "Contact", "Flash", "Steam", "Friction", "Hot oil/grease", "Unknown/unclear"]
            sel = two_col_checkboxes(mech_opts, "mech_opts__v1")
            add_detail(details, "Mechanism (structured)", ", ".join(sel))
            mech_txt = st.text_area(
                "Mechanism details (free text)",
                height=70,
                placeholder="Example: hot water scald to R forearm while cooking; no chemical/electrical exposure; occurred at ~18:30.",
                key="mech_txt__v1",
            )
            add_detail(details, "Mechanism details (free text)", mech_txt)
    
        # Time of injury
        inputs["time_of_injury"] = st.checkbox(CHECKLIST["time_of_injury"], key="toi_doc__v1")
        if inputs["time_of_injury"]:
            toi = st.radio(
                "Timeframe (structured)",
                ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
                horizontal=True,
                key="toi_struct__v1",
            )
            add_detail(details, "Timeframe (structured)", toi)
            toi_txt = st.text_area(
                "Time of injury details (free text)",
                height=60,
                placeholder="Include approximate time + delayed presentation + progression since injury.",
                key="toi_txt__v1",
            )
            add_detail(details, "Time of injury details (free text)", toi_txt)
    
        # Morphology
        inputs["morphology_burn_consistent"] = st.checkbox(CHECKLIST["morphology_burn_consistent"], key="morph__v1")
        if inputs["morphology_burn_consistent"]:
            morph_opts = ["Blistering", "Eschar", "Tissue loss", "Charred/leathery", "Weeping/moist", "Dry/waxy"]
            sel = two_col_checkboxes(morph_opts, "morph_opts__v1")
            add_detail(details, "Morphology (structured)", ", ".join(sel))
            morph_txt = st.text_area(
                "Morphology notes (free text)",
                height=60,
                placeholder="Describe appearance, distribution, margins, and any concern for non-burn mimics.",
                key="morph_txt__v1",
            )
            add_detail(details, "Morphology notes (free text)", morph_txt)
    
        # Depth
        inputs["depth_estimated"] = st.checkbox(CHECKLIST["depth_estimated"], key="depth__v1")
        if inputs["depth_estimated"]:
            depth = st.radio(
                "Depth estimate (structured)",
                ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
                horizontal=True,
                key="depth_struct__v1",
            )
            add_detail(details, "Depth (structured)", depth)
    
            # Optional supportive findings
            depth_findings = ["Blanching present", "Blanching absent", "Sensation intact", "Sensation decreased", "Sensation absent"]
            sel = two_col_checkboxes(depth_findings, "depth_find__v1")
            add_detail(details, "Depth supporting findings (structured)", ", ".join(sel))
    
            depth_txt = st.text_area(
                "Depth notes (free text)",
                height=60,
                placeholder="Pain/sensation, cap refill/blanching, moist vs dry, eschar, etc.",
                key="depth_txt__v1",
            )
            add_detail(details, "Depth notes (free text)", depth_txt)
    
        # TBSA
        inputs["tbsa_estimated"] = st.checkbox(CHECKLIST["tbsa_estimated"], key="tbsa__v1")
        if inputs["tbsa_estimated"]:
            tbsa_pct = st.number_input("TBSA % (structured)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="tbsa_pct__v1")
            tbsa_method = st.selectbox("TBSA method (structured)", ["Rule of 9s", "Palm method", "Lund-Browder", "Unknown"], key="tbsa_method__v1")
            add_detail(details, "TBSA % (structured)", f"{tbsa_pct:.1f}%")
            add_detail(details, "TBSA method (structured)", tbsa_method)
    
        # High-risk areas
        inputs["location_high_risk_checked"] = st.checkbox(CHECKLIST["location_high_risk_checked"], key="highrisk__v1")
        if inputs["location_high_risk_checked"]:
            sites = ["Face", "Hands", "Feet", "Genitals", "Perineum", "Major joints"]
            sel = two_col_checkboxes(sites, "sites__v1")
            add_detail(details, "High-risk sites (structured)", ", ".join(sel))
            sites_txt = st.text_area(
                "High-risk site notes (free text)",
                height=50,
                placeholder="Any functional concerns, swelling, airway/facial involvement, etc.",
                key="sites_txt__v1",
            )
            add_detail(details, "High-risk site notes (free text)", sites_txt)
    
        # Circumferential
        inputs["circumferential_checked"] = st.checkbox(CHECKLIST["circumferential_checked"], key="circ__v1")
        if inputs["circumferential_checked"]:
            circ_sites = ["Upper extremity", "Lower extremity", "Chest/torso", "Neck"]
            sel = two_col_checkboxes(circ_sites, "circ_sites__v1")
            add_detail(details, "Circumferential areas (structured)", ", ".join(sel))
            circ_txt = st.text_area(
                "Circumferential notes (free text)",
                height=50,
                placeholder="Distal pulses, cap refill, swelling, compartment concerns.",
                key="circ_txt__v1",
            )
            add_detail(details, "Circumferential notes (free text)", circ_txt)
    
        # -------------------------
        # Inhalation (clean redesign)
        # IMPORTANT: this block is self-contained so it cannot swallow the rest of the page
        # -------------------------
        st.markdown("## Inhalation")
    
        inputs["inhalation_risk_assessed"] = st.checkbox(
            CHECKLIST["inhalation_risk_assessed"],
            key="inh_assessed__v1",
        )
    
        # Use an expander so the UI expands without breaking page layout
        with st.expander("Inhalation details (only if assessed)", expanded=inputs["inhalation_risk_assessed"]):
            if inputs["inhalation_risk_assessed"]:
                inh_risk_opts = [
                    "Enclosed space exposure",
                    "Smoke exposure",
                    "Soot in nares/oropharynx",
                    "Singed nasal hairs",
                    "Hoarseness/voice change",
                    "Wheezing",
                    "Stridor",
                    "Respiratory distress / increasing O2 requirement",
                ]
                sel = two_col_checkboxes(inh_risk_opts, "inh_risk__v1")
                add_detail(details, "Inhalation risk factors (structured)", ", ".join(sel))
    
                inh_result = st.radio(
                    "Inhalation injury result (choose ONE)",
                    ["Not present", "Present", "Uncertain"],
                    horizontal=True,
                    key="inh_result__v1",
                )
                add_detail(details, "Inhalation result (structured)", inh_result)
    
                # Convert radio -> boolean
                inputs["inhalation_risk_present"] = (inh_result == "Present")
    
                inh_txt = st.text_area(
                    "Inhalation assessment notes (free text)",
                    height=70,
                    placeholder="Airway exam, soot/voice change, O2 needs, COHb/ABG if obtained, bronchoscopy if done.",
                    key="inh_txt__v1",
                )
                add_detail(details, "Inhalation notes (free text)", inh_txt)
            else:
                # If not assessed, treat as not present for logic
                inputs["inhalation_risk_present"] = False
    
        if not inputs["inhalation_risk_assessed"]:
            inputs["inhalation_risk_present"] = False
    
        # -------------------------
        # Vitals / context (always visible)
        # -------------------------
        st.markdown("## Vitals / context")
    
        inputs["vitals_reviewed"] = st.checkbox(CHECKLIST["vitals_reviewed"], key="vitals__v1")
        if inputs["vitals_reviewed"]:
            vitals_txt = st.text_area(
                "Vitals / instability notes (free text)",
                height=60,
                placeholder="Tachycardia/hypotension/fever, O2 requirement, pain control issues, etc.",
                key="vitals_txt__v1",
            )
            add_detail(details, "Vitals / instability notes (free text)", vitals_txt)
    
        inputs["comorbidities_reviewed"] = st.checkbox(CHECKLIST["comorbidities_reviewed"], key="comorb__v1")
        if inputs["comorbidities_reviewed"]:
            comorb_txt = st.text_area(
                "Comorbidities (free text)",
                height=60,
                placeholder="DM, immunosuppression, vascular disease, CKD, anticoagulation, etc.",
                key="comorb_txt__v1",
            )
            add_detail(details, "Comorbidities (free text)", comorb_txt)
    
        # Consult question (single-choice + free text)
        inputs["consult_question_defined"] = st.checkbox(CHECKLIST["consult_question_defined"], key="cq__v1")
        if inputs["consult_question_defined"]:
            cq_choice = st.radio(
                "What do you want Burn to do? (choose ONE)",
                [
                    "Confirm burn depth / TBSA",
                    "Wound care / dressing recommendations",
                    "Need for burn-center transfer",
                    "Operative evaluation / debridement planning",
                    "Other (specify in text)",
                ],
                key="cq_choice__v1",
            )
            add_detail(details, "Consult question (structured)", cq_choice)
    
            cq_txt = st.text_area(
                "Consult question notes (free text)",
                height=60,
                placeholder="Add nuance here (e.g., concern for evolving depth, pain control, compartment issues, unclear diagnosis).",
                key="cq_txt__v1",
            )
            add_detail(details, "Consult question notes (free text)", cq_txt)
    
        # -------------------------
        # Special cases (always visible)
        # -------------------------
        st.markdown("## Special cases")
    
        inputs["severe_skin_failure_flag"] = st.checkbox(CHECKLIST["severe_skin_failure_flag"], key="skin_fail__v1")
        if inputs["severe_skin_failure_flag"]:
            sf_txt = st.text_area(
                "Severe skin failure notes (free text)",
                height=60,
                placeholder="SJS/TEN pattern, mucosal involvement, systemic symptoms, medication triggers, etc.",
                key="skin_fail_txt__v1",
            )
            add_detail(details, "Severe skin failure notes (free text)", sf_txt)
    
        # -------------------------
        # Mechanism-specific required fields
        # -------------------------
        st.markdown("## Mechanism-specific fields")
    
        if inputs["mechanism_type"] == "chemical":
            inputs["chemical_agent_known_if_chemical"] = st.checkbox(CHECKLIST["chemical_agent_known_if_chemical"], key="chem_req__v1")
            if inputs["chemical_agent_known_if_chemical"]:
                chem_txt = st.text_area(
                    "Chemical details (free text)",
                    height=60,
                    placeholder="Agent, concentration if known, decon performed, irrigation duration, pH testing if applicable.",
                    key="chem_txt__v1",
                )
                add_detail(details, "Chemical details (free text)", chem_txt)
        else:
            inputs["chemical_agent_known_if_chemical"] = False
    
        if inputs["mechanism_type"] == "electrical":
            inputs["electrical_voltage_known_if_electrical"] = st.checkbox(CHECKLIST["electrical_voltage_known_if_electrical"], key="elec_req__v1")
            if inputs["electrical_voltage_known_if_electrical"]:
                elec_txt = st.text_area(
                    "Electrical details (free text)",
                    height=60,
                    placeholder="Voltage (low/high), LOC, ECG, arrhythmia, entry/exit wounds, CK/urine concerns.",
                    key="elec_txt__v1",
                )
                add_detail(details, "Electrical details (free text)", elec_txt)
        else:
            inputs["electrical_voltage_known_if_electrical"] = False


# -------------------------
# RIGHT: Output (always visible)
# -------------------------
with right:
    r = burn_consult_readiness(inputs)
    scope, why = scope_triage(inputs)
    tier = recommendation_tier(inputs, r["completeness_pct"], scope)
    msg = generate_message(inputs, scope, tier, why, r["missing_items"], details)

    st.markdown("## Output")
    st.metric("Scope", scope)
    st.metric("Recommendation", tier)
    st.metric("Readiness %", f"{r['completeness_pct']}%")

    st.markdown("### Paste-ready message")
    st.code(msg)

    st.markdown("### Top missing items")
    if r["missing_items"]:
        for item in r["missing_items"][:8]:
            st.write(f"• {item}")
    else:
        st.write("None 🎯")
