import streamlit as st

# =============================
# Page config
# =============================
st.set_page_config(page_title="Burn Consult Readiness Tool", layout="wide")

st.title("Burn Consult Readiness Tool")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

# =============================
# Labels (for missing-items list)
# =============================
LABELS = {
    "mechanism_documented": "Mechanism documented",
    "time_of_injury": "Time of injury documented",
    "morphology_burn_consistent": "Morphology consistent with burn",
    "depth_estimated": "Depth estimated",
    "tbsa_estimated": "TBSA estimated",
    "location_high_risk_checked": "High-risk areas assessed",
    "circumferential_checked": "Circumferential involvement assessed",
    "inhalation_risk_assessed": "Inhalation risk assessed",
    "vitals_reviewed": "Vitals reviewed / instability assessed",
    "comorbidities_reviewed": "Major comorbidities reviewed",
    "consult_question_defined": "Consult question defined",
    "chemical_agent_known_if_chemical": "If chemical: agent identified + decontamination documented",
    "electrical_voltage_known_if_electrical": "If electrical: voltage/LOC/ECG documented",
}

# =============================
# Helper functions
# =============================
def add_detail(details: dict, label: str, value):
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        value = ", ".join([v for v in value if str(v).strip()])
    value = str(value).strip()
    if value:
        details[label] = value

def compute_readiness(inputs: dict):
    mech_type = inputs.get("mechanism_type", "unknown")

    # NOTE: inhalation PRESENT is NOT required; only "assessed" is.
    required = [
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
    ]

    if mech_type == "chemical":
        required.append("chemical_agent_known_if_chemical")
    if mech_type == "electrical":
        required.append("electrical_voltage_known_if_electrical")

    done = [k for k in required if inputs.get(k) is True]
    missing = [k for k in required if inputs.get(k) is not True]

    pct = round((len(done) / len(required)) * 100, 1) if required else 0.0
    missing_labels = [LABELS.get(k, k) for k in missing]
    return pct, missing_labels

def scope_triage(inputs: dict):
    mech_doc = inputs.get("mechanism_documented") is True
    morph = inputs.get("morphology_burn_consistent") is True

    special_present = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if special_present:
        return "WITHIN SCOPE", "Special burn mechanism present (chemical/electrical/inhalation)."

    if mech_doc and morph:
        return "WITHIN SCOPE", "Burn-consistent mechanism and morphology."

    return "OUTSIDE OF SCOPE", "Mechanism and/or morphology not consistent with burn."

def recommend_tier(inputs: dict, readiness_pct: float, scope: str):
    high_risk = inputs.get("location_high_risk_checked") is True
    special_present = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if scope == "OUTSIDE OF SCOPE":
        return "CONSIDER ALTERNATE SERVICE"

    if high_risk or special_present:
        return "CONSULT NOW"

    if readiness_pct >= 70:
        return "STRONGLY RECOMMEND BURN SURGERY CONSULT"

    return "LOW RECOMMENDATION FOR BURN SURGERY CONSULT"

def build_message(inputs: dict, details: dict, scope: str, tier: str, why: str, missing_labels: list):
    key_lines = [f"- {k}: {v}" for k, v in details.items() if str(v).strip()]
    key_block = "\n".join(key_lines).strip()
    missing_short = "; ".join(missing_labels[:6]) if missing_labels else ""
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
                "Recommend evaluation by the appropriate alternate service per local workflow. "
                "Re-consult Burn Surgery if burn-consistent features develop or special mechanisms are suspected."
            )
        if key_block:
            msg += f"\n\nKey details documented:\n{key_block}"
        if missing_short:
            msg += f"\n\nMissing elements: {missing_short}."
        return msg

    msg = f"Recommend Burn Surgery consultation. Tier: {tier}. Rationale: {why}"
    if key_block:
        msg += f"\n\nKey details documented:\n{key_block}"
    if missing_short:
        msg += f"\n\nMissing elements being obtained in parallel: {missing_short}."
    return msg


# =============================
# Sidebar: Inputs (stable layout)
# =============================
st.sidebar.header("Inputs")

if "submitted_once" not in st.session_state:
    st.session_state.submitted_once = False
    st.session_state.latest_inputs = {}
    st.session_state.latest_details = {}

with st.sidebar.form("burn_form", clear_on_submit=False):
    inputs = {}
    details = {}

    inputs["mechanism_type"] = st.selectbox(
        "Mechanism type (overall)",
        ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
        key="mech_type_sb",
    )

    st.subheader("Core burn assessment")

    inputs["mechanism_documented"] = st.checkbox("Mechanism documented", key="mech_doc_sb")
    if inputs["mechanism_documented"]:
        mech_opts = ["Scald", "Flame", "Contact", "Flash", "Steam", "Friction", "Hot oil/grease", "Unknown/unclear"]
        mech_sel = st.multiselect("Mechanism (structured)", mech_opts, key="mech_struct_sb")
        add_detail(details, "Mechanism (structured)", mech_sel)
        mech_txt = st.text_area(
            "Mechanism details (free text)",
            height=70,
            placeholder="Example: hot water scald to R forearm; no chemical/electrical exposure; occurred ~18:30.",
            key="mech_txt_sb",
        )
        add_detail(details, "Mechanism details", mech_txt)

    inputs["time_of_injury"] = st.checkbox("Time of injury documented", key="toi_sb")
    if inputs["time_of_injury"]:
        tf = st.radio(
            "Timeframe (structured)",
            ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
            key="timeframe_sb",
        )
        add_detail(details, "Timeframe (structured)", tf)
        toi_txt = st.text_area(
            "Time of injury details (free text)",
            height=60,
            placeholder="Approx time, delayed presentation, progression since injury.",
            key="toi_txt_sb",
        )
        add_detail(details, "Time of injury details", toi_txt)

    inputs["morphology_burn_consistent"] = st.checkbox("Morphology consistent with burn", key="morph_sb")
    if inputs["morphology_burn_consistent"]:
        morph_opts = ["Blistering", "Eschar", "Tissue loss", "Charred/white/leathery", "Weeping/moist", "Dry/waxy"]
        morph_sel = st.multiselect("Morphology (structured)", morph_opts, key="morph_struct_sb")
        add_detail(details, "Morphology (structured)", morph_sel)
        morph_txt = st.text_area(
            "Morphology details (free text)",
            height=60,
            placeholder="Describe appearance, borders, tenderness, cap refill, progression.",
            key="morph_txt_sb",
        )
        add_detail(details, "Morphology details", morph_txt)

    inputs["depth_estimated"] = st.checkbox("Depth estimated", key="depth_sb")
    if inputs["depth_estimated"]:
        depth = st.radio(
            "Depth estimate (structured)",
            ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
            key="depth_radio_sb",
        )
        add_detail(details, "Depth (structured)", depth)

    inputs["tbsa_estimated"] = st.checkbox("TBSA estimated", key="tbsa_sb")
    if inputs["tbsa_estimated"]:
        tbsa_val = st.number_input("TBSA %", 0.0, 100.0, 0.0, 0.5, key="tbsa_val_sb")
        tbsa_method = st.selectbox(
            "TBSA method",
            ["Rule of 9s", "Palmar method", "Lund-Browder", "Other/uncertain"],
            key="tbsa_method_sb"
        )
        add_detail(details, "TBSA % (structured)", f"{tbsa_val:.1f}%")
        add_detail(details, "TBSA method (structured)", tbsa_method)

    inputs["location_high_risk_checked"] = st.checkbox("High-risk areas assessed", key="hi_risk_sb")
    if inputs["location_high_risk_checked"]:
        hi_opts = ["Face", "Hands", "Feet", "Genitals", "Perineum", "Major joints"]
        hi_sel = st.multiselect("High-risk areas (structured)", hi_opts, key="hi_struct_sb")
        add_detail(details, "High-risk areas (structured)", hi_sel)

    inputs["circumferential_checked"] = st.checkbox("Circumferential involvement assessed", key="circ_sb")
    if inputs["circumferential_checked"]:
        circ = st.radio("Circumferential involvement", ["No", "Yes", "Uncertain"], key="circ_radio_sb")
        add_detail(details, "Circumferential involvement (structured)", circ)

        # ===== Inhalation (STABLE, NO GAP) =====
    st.subheader("Inhalation")

    inputs["inhalation_risk_assessed"] = st.checkbox(
        "Inhalation risk assessed",
        key="inh_assessed"
    )

    inh_findings = st.multiselect(
        "Inhalation findings (structured)",
        [
            "Enclosed space exposure",
            "Smoke exposure",
            "Soot in nares/oropharynx",
            "Singed nasal hairs",
            "Hoarseness/voice change",
            "Wheezing",
            "Stridor",
        ],
        disabled=not inputs["inhalation_risk_assessed"],
        key="inh_findings",
    )

    inh_notes = st.text_area(
        "Inhalation assessment notes (free text)",
        placeholder="Airway exam, O2 requirement, COHb/ABG if obtained.",
        height=60,
        disabled=not inputs["inhalation_risk_assessed"],
        key="inh_notes",
    )

    inh_result = st.radio(
        "Inhalation injury result (choose ONE)",
        ["Not present", "Present", "Uncertain"],
        disabled=not inputs["inhalation_risk_assessed"],
        key="inh_result",
    )

    # logic flags
    inputs["inhalation_risk_present"] = (
        inputs["inhalation_risk_assessed"] and inh_result == "Present"
    )

    # add to consult message ONLY if assessed
    if inputs["inhalation_risk_assessed"]:
        add_detail(details, "Inhalation findings (structured)", inh_findings)
        add_detail(details, "Inhalation notes", inh_notes)
        add_detail(details, "Inhalation result (structured)", inh_result)


# =============================
# Main page: Output
# =============================
st.header("Output")

if not st.session_state.submitted_once:
    st.info("Fill inputs in the sidebar, then click **Update Output**.")
else:
    use_inputs = st.session_state.latest_inputs
    use_details = st.session_state.latest_details

    readiness_pct, missing_labels = compute_readiness(use_inputs)
    scope, why = scope_triage(use_inputs)
    tier = recommend_tier(use_inputs, readiness_pct, scope)
    msg = build_message(use_inputs, use_details, scope, tier, why, missing_labels)

    st.subheader("Summary")
    st.write(f"**Scope:** {scope}")
    st.write(f"**Recommendation:** {tier}")
    st.write(f"**Readiness %:** {readiness_pct}%")

    st.markdown("### Paste-ready message")
    st.code(msg)

    st.markdown("### Top missing items")
    if missing_labels:
        for item in missing_labels[:10]:
            st.write(f"• {item}")
    else:
        st.write("None 🎯")
