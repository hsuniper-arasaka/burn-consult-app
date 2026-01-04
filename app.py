import streamlit as st

# =============================
# Page config
# =============================
st.set_page_config(page_title="Burn Consult Readiness Tool", layout="wide")
st.title("Burn Consult Readiness Tool")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

# =============================
# Helpers
# =============================
def add_detail(details: dict, label: str, value: str):
    value = (value or "").strip()
    if value:
        details[label] = value

def two_col_checkboxes(options, key_prefix: str):
    """Render options as two-column checkboxes with stable unique keys. Returns selected list."""
    col1, col2 = st.columns(2)
    selected = []
    half = (len(options) + 1) // 2
    left = options[:half]
    right = options[half:]

    for i, opt in enumerate(left):
        if col1.checkbox(opt, key=f"{key_prefix}__L__{i}__{opt}"):
            selected.append(opt)
    for i, opt in enumerate(right):
        if col2.checkbox(opt, key=f"{key_prefix}__R__{i}__{opt}"):
            selected.append(opt)
    return selected

def compute_readiness(inputs: dict):
    mech_type = inputs.get("mechanism_type", "unknown")

    # readiness = "did you ASSESS/DOCUMENT the basics?"
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
        "inhalation_risk_assessed",  # assessed is required; present is not
    ]

    if mech_type == "chemical":
        required.append("chemical_agent_known_if_chemical")
    if mech_type == "electrical":
        required.append("electrical_voltage_known_if_electrical")

    done = [k for k in required if inputs.get(k) is True]
    missing = [k for k in required if inputs.get(k) is not True]

    pct = round((len(done) / len(required)) * 100, 1) if required else 0.0
    return pct, missing

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

def recommendation(inputs: dict, readiness_pct: float, scope: str):
    high_risk = inputs.get("location_high_risk_checked") is True
    special_present = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if scope == "OUTSIDE OF SCOPE":
        return "CONSIDER ALTERNATE SERVICE"

    if special_present or high_risk:
        return "CONSULT NOW"

    if readiness_pct >= 70:
        return "STRONGLY RECOMMEND BURN SURGERY CONSULT"
    return "LOW RECOMMENDATION FOR BURN SURGERY CONSULT"

def build_message(inputs: dict, details: dict, scope: str, tier: str, why: str, missing_labels: list[str]):
    # brief missing list
    missing_short = "; ".join(missing_labels[:5]) if missing_labels else ""

    # key details block
    key_lines = [f"- {k}: {v}" for k, v in details.items() if (v or "").strip()]
    key_block = "\n".join(key_lines).strip()

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

    msg = (
        f"Recommend Burn Surgery consultation. Tier: {tier}. "
        f"Rationale: {why}"
    )
    if key_block:
        msg += f"\n\nKey details documented:\n{key_block}"
    if missing_short:
        msg += f"\n\nMissing elements being obtained in parallel: {missing_short}."
    return msg

# =============================
# Labels (for missing items display)
# =============================
LABELS = {
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
    "vitals_reviewed": "Vitals reviewed / instability assessed",
    "comorbidities_reviewed": "Major comorbidities reviewed",
    "consult_question_defined": "Consult question defined",
}

# =============================
# Layout: Two columns
# IMPORTANT: All inputs MUST render INSIDE left column to avoid gaps
# =============================
left, right = st.columns([1.25, 1])

# =============================
# LEFT: Inputs (inside a single FORM)
# =============================
with left:
    st.header("Inputs")

    # session state store for last submitted
    if "submitted_once" not in st.session_state:
        st.session_state.submitted_once = False
        st.session_state.latest_inputs = {}
        st.session_state.latest_details = {}

    with st.form("burn_form", clear_on_submit=False):

        inputs = {}
        details = {}

        inputs["mechanism_type"] = st.selectbox(
            "Mechanism type (overall)",
            ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
            key="mech_type__v3"
        )

        # ---------- Core burn assessment ----------
        st.subheader("Core burn assessment")

        inputs["mechanism_documented"] = st.checkbox("Mechanism documented", key="mech_doc__v3")
        if inputs["mechanism_documented"]:
            mech_opts = ["Scald", "Flame", "Contact", "Flash", "Steam", "Friction", "Hot oil/grease", "Unknown/unclear"]
            sel = two_col_checkboxes(mech_opts, "mech_opts__v3")
            add_detail(details, "Mechanism (structured)", ", ".join(sel))
            txt = st.text_area(
                "Mechanism details (free text)",
                height=70,
                placeholder="Example: hot water scald to R forearm while cooking; no chemical/electrical exposure; occurred ~18:30.",
                key="mech_txt__v3",
            )
            add_detail(details, "Mechanism details", txt)

        inputs["time_of_injury"] = st.checkbox("Time of injury documented", key="toi__v3")
        if inputs["time_of_injury"]:
            tf = st.radio(
                "Timeframe (structured)",
                ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
                horizontal=True,
                key="timeframe__v3",
            )
            add_detail(details, "Timeframe (structured)", tf)
            toi_txt = st.text_area(
                "Time of injury details (free text)",
                height=60,
                placeholder="Include approx time, delayed presentation, progression since injury.",
                key="toi_txt__v3",
            )
            add_detail(details, "Time of injury details", toi_txt)

        inputs["morphology_burn_consistent"] = st.checkbox("Morphology consistent with burn", key="morph__v3")
        if inputs["morphology_burn_consistent"]:
            morph_sel = two_col_checkboxes(
                ["Blistering", "Eschar", "Tissue loss", "Charred/white/leathery", "Weeping/moist", "Dry/waxy"],
                "morph_opts__v3"
            )
            add_detail(details, "Morphology (structured)", ", ".join(morph_sel))
            morph_txt = st.text_area(
                "Morphology details (free text)",
                height=60,
                placeholder="Describe appearance, borders, tenderness, cap refill, progression.",
                key="morph_txt__v3",
            )
            add_detail(details, "Morphology details", morph_txt)

        inputs["depth_estimated"] = st.checkbox("Depth estimated", key="depth__v3")
        if inputs["depth_estimated"]:
            depth = st.radio(
                "Depth estimate (structured)",
                ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
                horizontal=True,
                key="depth_radio__v3",
            )
            add_detail(details, "Depth (structured)", depth)

        inputs["tbsa_estimated"] = st.checkbox("TBSA estimated", key="tbsa__v3")
        if inputs["tbsa_estimated"]:
            tbsa_val = st.number_input("TBSA % (structured)", 0.0, 100.0, 0.0, 0.5, key="tbsa_val__v3")
            tbsa_method = st.selectbox("TBSA method (structured)", ["Rule of 9s", "Palmar method", "Lund-Browder", "Other/uncertain"], key="tbsa_method__v3")
            add_detail(details, "TBSA % (structured)", f"{tbsa_val:.1f}%")
            add_detail(details, "TBSA method (structured)", tbsa_method)

        inputs["location_high_risk_checked"] = st.checkbox("High-risk areas assessed", key="hi_risk__v3")
        if inputs["location_high_risk_checked"]:
            hi_sel = two_col_checkboxes(["Face", "Hands", "Feet", "Genitals", "Perineum", "Major joints"], "hi_risk_opts__v3")
            add_detail(details, "High-risk areas (structured)", ", ".join(hi_sel))

        inputs["circumferential_checked"] = st.checkbox("Circumferential involvement assessed", key="circ__v3")
        if inputs["circumferential_checked"]:
            circ = st.radio("Circumferential involvement (structured)", ["No", "Yes", "Uncertain"], horizontal=True, key="circ_radio__v3")
            add_detail(details, "Circumferential involvement (structured)", circ)

        # ---------- Inhalation ----------
        st.subheader("Inhalation")

        inputs["inhalation_risk_assessed"] = st.checkbox("Inhalation risk assessed", key="inh_assessed__v3")

        # default: present = False unless assessed and user says Present
        inputs["inhalation_risk_present"] = False

        if inputs["inhalation_risk_assessed"]:
            inh_findings = [
                "Enclosed space exposure",
                "Smoke exposure",
                "Soot in nares/oropharynx",
                "Singed nasal hairs",
                "Hoarseness/voice change",
                "Wheezing",
                "Stridor",
            ]
            inh_sel = two_col_checkboxes(inh_findings, "inh_findings__v3")
            add_detail(details, "Inhalation findings (structured)", ", ".join(inh_sel))

            inh_txt = st.text_area(
                "Inhalation assessment notes (free text)",
                height=60,
                placeholder="Airway exam, O2 requirement, respiratory symptoms, COHb/ABG if obtained.",
                key="inh_txt__v3",
            )
            add_detail(details, "Inhalation notes", inh_txt)

            inh_result = st.radio(
                "Inhalation injury result (choose ONE)",
                ["Not present", "Present", "Uncertain"],
                horizontal=True,
                key="inh_result__v3",
            )
            add_detail(details, "Inhalation result (structured)", inh_result)
            inputs["inhalation_risk_present"] = (inh_result == "Present")

        # ---------- Vitals / context ----------
        st.subheader("Vitals / context")
        inputs["vitals_reviewed"] = st.checkbox("Vitals reviewed / instability assessed", key="vitals__v3")
        inputs["comorbidities_reviewed"] = st.checkbox("Major comorbidities reviewed", key="comorb__v3")

        # ---------- Consult question ----------
        st.subheader("Consult question")
        cq = st.selectbox(
            "What do you want Burn to do? (choose ONE)",
            ["Depth/TBSA confirmation", "Debridement/wound care plan", "Transfer/burn center eval", "Airway/inhalation concern", "Other"],
            key="cq_select__v3"
        )
        inputs["consult_question_defined"] = True
        add_detail(details, "Consult question (structured)", cq)
        cq_txt = st.text_area(
            "Additional consult details (free text)",
            height=70,
            placeholder="Extra concerns here (brief).",
            key="cq_txt__v3"
        )
        add_detail(details, "Consult question notes", cq_txt)

        # ---------- Special cases ----------
        st.subheader("Special cases")
        inputs["severe_skin_failure_flag"] = st.checkbox("Severe skin failure suspected (e.g., SJS/TEN pattern)", key="sjs__v3")

        # ---------- Mechanism-specific fields ----------
        st.subheader("Mechanism-specific fields")
        mech_type = inputs["mechanism_type"]

        # Chemical (enabled only if chemical)
        chem_disabled = (mech_type != "chemical")
        inputs["chemical_agent_known_if_chemical"] = st.checkbox(
            "If chemical: agent identified + decontamination documented",
            key="chem__v3",
            disabled=chem_disabled,
        )
        if not chem_disabled and inputs["chemical_agent_known_if_chemical"]:
            chem_txt = st.text_area(
                "Chemical details (free text)",
                height=60,
                placeholder="Agent, concentration, duration, decon, ocular exposure.",
                key="chem_txt__v3",
            )
            add_detail(details, "Chemical details", chem_txt)

        # Electrical (enabled only if electrical)
        elec_disabled = (mech_type != "electrical")
        inputs["electrical_voltage_known_if_electrical"] = st.checkbox(
            "If electrical: voltage/LOC/ECG documented",
            key="elec__v3",
            disabled=elec_disabled,
        )
        if not elec_disabled and inputs["electrical_voltage_known_if_electrical"]:
            elec_txt = st.text_area(
                "Electrical details (free text)",
                height=60,
                placeholder="Voltage, LOC, ECG, entry/exit wounds, CK/urine concerns.",
                key="elec_txt__v3",
            )
            add_detail(details, "Electrical details", elec_txt)

        # Submit
        submitted = st.form_submit_button("Update Output")

        if submitted:
            st.session_state.submitted_once = True
            st.session_state.latest_inputs = inputs
            st.session_state.latest_details = details

# =============================
# RIGHT: Output
# =============================
with right:
    st.header("Output")

    if not st.session_state.submitted_once:
        st.info("Fill out inputs on the left, then click **Update Output**.")
    else:
        use_inputs = st.session_state.latest_inputs
        use_details = st.session_state.latest_details

        readiness_pct, missing_keys = compute_readiness(use_inputs)
        scope, why = scope_triage(use_inputs)
        tier = recommendation(use_inputs, readiness_pct, scope)

        missing_labels = [LABELS.get(k, k) for k in missing_keys]
        msg = build_message(use_inputs, use_details, scope, tier, why, missing_labels)

        st.metric("Scope", scope)
        st.metric("Recommendation", tier)
        st.metric("Readiness %", f"{readiness_pct}%")

        st.markdown("### Paste-ready message")
        st.code(msg)

        st.markdown("### Top missing items")
        if missing_labels:
            for item in missing_labels[:8]:
                st.write(f"• {item}")
        else:
            st.write("None 🎯")
