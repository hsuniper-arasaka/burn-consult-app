import streamlit as st

# =============================
# Config
# =============================
st.set_page_config(page_title="Burn Consult Readiness Tool", layout="wide")
st.title("Burn Consult Readiness Tool")
st.caption("Decision support only. Adapt to local protocols.")

# =============================
# Helper utilities
# =============================
def add_detail(details: dict, label: str, value: str):
    value = (value or "").strip()
    if value:
        details[label] = value

def two_col_checkboxes(options, key_prefix: str):
    """Return list of selected options; uses stable unique keys."""
    col1, col2 = st.columns(2)
    selected = []
    half = (len(options) + 1) // 2
    left = options[:half]
    right = options[half:]

    for i, opt in enumerate(left):
        k = f"{key_prefix}__L__{i}__{opt}"
        if col1.checkbox(opt, key=k):
            selected.append(opt)
    for i, opt in enumerate(right):
        k = f"{key_prefix}__R__{i}__{opt}"
        if col2.checkbox(opt, key=k):
            selected.append(opt)
    return selected

# =============================
# Labels
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
    "consult_question_defined": "Consult question defined (choose ONE)",
    "severe_skin_failure_flag": "Severe skin failure suspected (e.g., SJS/TEN pattern)",
}

# =============================
# Core logic
# =============================
def burn_consult_readiness(inputs: dict):
    mech_type = inputs.get("mechanism_type", "unknown")

    # REQUIRED = things you want *documented*, not necessarily "present"
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
        "inhalation_risk_assessed",  # assessed is required, present is NOT required
    ]

    if mech_type == "chemical":
        required.append("chemical_agent_known_if_chemical")
    if mech_type == "electrical":
        required.append("electrical_voltage_known_if_electrical")

    done = [k for k in required if inputs.get(k) is True]
    missing = [k for k in required if inputs.get(k) is not True]

    pct = round((len(done) / len(required)) * 100, 1) if required else 0.0
    return {
        "completeness_pct": pct,
        "missing_items": [CHECKLIST.get(k, k) for k in missing],
    }

def scope_triage(inputs: dict):
    mech = inputs.get("mechanism_documented") is True
    morph = inputs.get("morphology_burn_consistent") is True

    special = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if special:
        return "WITHIN SCOPE", "Special burn mechanism present (chemical/electrical/inhalation)."
    if mech and morph:
        return "WITHIN SCOPE", "Burn-consistent mechanism and morphology."
    return "OUTSIDE SCOPE", "Mechanism and/or morphology not consistent with burn."

def recommendation_tier(inputs: dict, completeness: float, scope: str):
    high_risk = inputs.get("location_high_risk_checked") is True
    special_present = (
        inputs.get("chemical_agent_known_if_chemical") is True
        or inputs.get("electrical_voltage_known_if_electrical") is True
        or inputs.get("inhalation_risk_present") is True
    )

    if scope == "OUTSIDE SCOPE":
        return "CONSIDER ALTERNATE SERVICE"

    if special_present or high_risk:
        return "CONSULT NOW"

    if completeness >= 70:
        return "STRONGLY RECOMMEND BURN SURGERY CONSULT"
    return "LOW RECOMMENDATION FOR BURN SURGERY CONSULT"

def generate_message(inputs, scope, tier, rationale, missing_items, details):
    missing_short = "; ".join(missing_items[:4]) if missing_items else ""
    severe_skin = inputs.get("severe_skin_failure_flag") is True

    # Build "key details documented" section
    key_lines = []
    for k, v in details.items():
        key_lines.append(f"- {k}: {v}")

    key_details = "\n".join(key_lines).strip()

    if scope == "OUTSIDE SCOPE":
        if severe_skin:
            msg = (
                f"{rationale} The presentation suggests a severe non-burn skin process. "
                "Recommend urgent multidisciplinary evaluation per local protocol. "
                "Escalate appropriately. Burn Surgery can be re-consulted if burn features emerge."
            )
        else:
            msg = (
                f"{rationale} Burn Surgery involvement is not clearly indicated at this time. "
                "Recommend evaluation by the appropriate alternate service per local workflow. "
                "Re-consult Burn Surgery if burn-consistent features develop or special mechanisms are suspected."
            )
        if key_details:
            msg += f"\n\nKey details documented:\n{key_details}"
        if missing_short:
            msg += f"\n\nMissing elements: {missing_short}."
        return msg

    msg = (
        f"Recommend Burn Surgery consultation. Tier: {tier}. "
        f"Rationale: {rationale}"
    )
    if key_details:
        msg += f"\n\nKey details documented:\n{key_details}"
    if missing_short:
        msg += f"\n\nMissing elements being obtained in parallel: {missing_short}."
    return msg

# =============================
# UI (Sidebar form)
# =============================
inputs = {}
details = {}

with st.sidebar:
    st.header("Inputs")

    with st.form("burn_form", clear_on_submit=False):
        inputs["mechanism_type"] = st.selectbox(
            "Mechanism type (overall)",
            ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
            key="mech_type__v2"
        )

        # --- Core burn assessment ---
        st.subheader("Core burn assessment")

        inputs["mechanism_documented"] = st.checkbox(CHECKLIST["mechanism_documented"], key="mech_doc__v2")
        mech_opts = []
        if inputs["mechanism_documented"]:
            mech_opts = ["Scald", "Flame", "Contact", "Flash", "Steam", "Friction", "Hot oil/grease", "Unknown/unclear"]
            sel = two_col_checkboxes(mech_opts, "mech_opts__v2")
            add_detail(details, "Mechanism (structured)", ", ".join(sel))
            mech_txt = st.text_area(
                "Mechanism details (free text)",
                height=70,
                placeholder="Example: hot water scald to R forearm while cooking; no chemical/electrical exposure; occurred ~18:30.",
                key="mech_txt__v2",
            )
            add_detail(details, "Mechanism details", mech_txt)

        inputs["time_of_injury"] = st.checkbox(CHECKLIST["time_of_injury"], key="toi__v2")
        if inputs["time_of_injury"]:
            timeframe = st.radio(
                "Timeframe (structured)",
                ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
                horizontal=True,
                key="timeframe__v2",
            )
            add_detail(details, "Timeframe (structured)", timeframe)
            toi_txt = st.text_area(
                "Time of injury details (free text)",
                height=60,
                placeholder="Include approx time + delayed presentation + progression since injury.",
                key="toi_txt__v2",
            )
            add_detail(details, "Time of injury details", toi_txt)

        inputs["morphology_burn_consistent"] = st.checkbox(CHECKLIST["morphology_burn_consistent"], key="morph__v2")
        if inputs["morphology_burn_consistent"]:
            morph_sel = two_col_checkboxes(
                ["Blistering", "Eschar", "Tissue loss", "Charred/white/leathery", "Weeping/moist", "Dry/waxy"],
                "morph_opts__v2"
            )
            add_detail(details, "Morphology (structured)", ", ".join(morph_sel))
            morph_txt = st.text_area(
                "Morphology details (free text)",
                height=60,
                placeholder="Describe appearance + borders + tenderness + cap refill + progression.",
                key="morph_txt__v2",
            )
            add_detail(details, "Morphology details", morph_txt)

        inputs["depth_estimated"] = st.checkbox(CHECKLIST["depth_estimated"], key="depth__v2")
        if inputs["depth_estimated"]:
            depth = st.radio(
                "Depth estimate (structured)",
                ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
                horizontal=True,
                key="depth_radio__v2",
            )
            add_detail(details, "Depth (structured)", depth)

        inputs["tbsa_estimated"] = st.checkbox(CHECKLIST["tbsa_estimated"], key="tbsa__v2")
        if inputs["tbsa_estimated"]:
            tbsa_val = st.number_input("TBSA % (structured)", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="tbsa_val__v2")
            tbsa_method = st.selectbox("TBSA method (structured)", ["Rule of 9s", "Palmar method", "Lund-Browder", "Other/uncertain"], key="tbsa_method__v2")
            add_detail(details, "TBSA % (structured)", f"{tbsa_val:.1f}%")
            add_detail(details, "TBSA method (structured)", tbsa_method)

        inputs["location_high_risk_checked"] = st.checkbox(CHECKLIST["location_high_risk_checked"], key="hi_risk__v2")
        if inputs["location_high_risk_checked"]:
            hi_sel = two_col_checkboxes(["Face", "Hands", "Feet", "Genitals", "Perineum", "Major joints"], "hi_risk_opts__v2")
            add_detail(details, "High-risk areas (structured)", ", ".join(hi_sel))

        inputs["circumferential_checked"] = st.checkbox(CHECKLIST["circumferential_checked"], key="circ__v2")
        if inputs["circumferential_checked"]:
            circ_sel = st.radio("Circumferential involvement (structured)", ["No", "Yes", "Uncertain"], horizontal=True, key="circ_radio__v2")
            add_detail(details, "Circumferential involvement (structured)", circ_sel)

        # --- Inhalation ---
        st.subheader("Inhalation")
        inputs["inhalation_risk_assessed"] = st.checkbox(CHECKLIST["inhalation_risk_assessed"], key="inh_assessed__v2")
        inputs["inhalation_risk_present"] = False  # default
        if inputs["inhalation_risk_assessed"]:
            present = st.radio(
                "Inhalation injury present?",
                ["No", "Yes", "Uncertain"],
                horizontal=True,
                key="inh_present_radio__v2",
            )
            inputs["inhalation_risk_present"] = (present == "Yes")
            add_detail(details, "Inhalation present (structured)", present)
            inh_txt = st.text_area(
                "Inhalation details (free text)",
                height=60,
                placeholder="Enclosed space? soot? singed hairs? voice change? stridor? O2 needs?",
                key="inh_txt__v2",
            )
            add_detail(details, "Inhalation details", inh_txt)

        # --- Vitals / context ---
        st.subheader("Vitals / context")
        inputs["vitals_reviewed"] = st.checkbox(CHECKLIST["vitals_reviewed"], key="vitals__v2")
        inputs["comorbidities_reviewed"] = st.checkbox(CHECKLIST["comorbidities_reviewed"], key="comorb__v2")

        # --- Consult question (ONE choice) ---
        st.subheader("Consult question")
        cq = st.selectbox(
            "What do you want Burn to do? (choose one)",
            ["Depth/TBSA confirmation", "Debridement/wound care plan", "Transfer/burn center eval", "Airway/inhalation concern", "Other"],
            key="cq_select__v2"
        )
        inputs["consult_question_defined"] = True
        add_detail(details, "Consult question (structured)", cq)
        cq_txt = st.text_area(
            "Additional consult details (free text)",
            height=70,
            placeholder="Add extra concerns here (keep brief).",
            key="cq_txt__v2"
        )
        add_detail(details, "Consult question details", cq_txt)

        # --- Special cases ---
        st.subheader("Special cases")
        inputs["severe_skin_failure_flag"] = st.checkbox(CHECKLIST["severe_skin_failure_flag"], key="sjs__v2")

        # --- Mechanism-specific fields (always visible; disabled unless relevant) ---
        st.subheader("Mechanism-specific fields")
        mech_type = inputs["mechanism_type"]

        chem_disabled = (mech_type != "chemical")
        elec_disabled = (mech_type != "electrical")

        inputs["chemical_agent_known_if_chemical"] = st.checkbox(
            CHECKLIST["chemical_agent_known_if_chemical"],
            key="chem__v2",
            disabled=chem_disabled
        )
        if not chem_disabled and inputs["chemical_agent_known_if_chemical"]:
            chem_txt = st.text_area(
                "Chemical details (free text)",
                height=60,
                placeholder="Agent, concentration, duration of exposure, decontamination, eye exposure.",
                key="chem_txt__v2"
            )
            add_detail(details, "Chemical details", chem_txt)

        inputs["electrical_voltage_known_if_electrical"] = st.checkbox(
            CHECKLIST["electrical_voltage_known_if_electrical"],
            key="elec__v2",
            disabled=elec_disabled
        )
        if not elec_disabled and inputs["electrical_voltage_known_if_electrical"]:
            elec_txt = st.text_area(
                "Electrical details (free text)",
                height=60,
                placeholder="Voltage (low/high), LOC, ECG, arrhythmia, entry/exit wounds, CK/urine concerns.",
                key="elec_txt__v2"
            )
            add_detail(details, "Electrical details", elec_txt)

        submitted = st.form_submit_button("Update Output")

# =============================
# Output (Main page)
# =============================
if "submitted_once" not in st.session_state:
    st.session_state.submitted_once = False

if submitted:
    st.session_state.submitted_once = True
    st.session_state.latest_inputs = inputs
    st.session_state.latest_details = details

colL, colR = st.columns([1, 1])

with colR:
    st.header("Output")

    if not st.session_state.submitted_once:
        st.info("Fill out inputs in the sidebar, then click **Update Output**.")
    else:
        inputs_use = st.session_state.latest_inputs
        details_use = st.session_state.latest_details

        r = burn_consult_readiness(inputs_use)
        scope, rationale = scope_triage(inputs_use)
        tier = recommendation_tier(inputs_use, r["completeness_pct"], scope)
        msg = generate_message(inputs_use, scope, tier, rationale, r["missing_items"], details_use)

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

with colL:
    st.header("Notes")
    st.write(
        "- Inputs are entered in the sidebar and only update the output when you click **Update Output**.\n"
        "- This prevents scroll-jump and disappearing sections.\n"
        "- Inhalation: **assessed** contributes to readiness; **present** does not (it affects scope/tier if yes).\n"
        "- Mechanism-specific fields stay visible but are disabled unless that mechanism is selected."
    )
