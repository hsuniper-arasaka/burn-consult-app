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
# Helpers
# =============================
def add_detail(details: dict, label: str, value):
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        value = ", ".join([str(v).strip() for v in value if str(v).strip()])
    value = str(value).strip()
    if value:
        details[label] = value

def compute_readiness(inputs: dict):
    """
    Readiness = completeness of core documentation.
    IMPORTANT: inhalation PRESENT is NOT required. Only "assessed" is required.
    """
    mech_type = inputs.get("mechanism_type", "unknown")

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

    # WITHIN SCOPE
    msg = f"Recommend Burn Surgery consultation. Tier: {tier}. Rationale: {why}"
    if key_block:
        msg += f"\n\nKey details documented:\n{key_block}"
    if missing_short:
        msg += f"\n\nMissing elements being obtained in parallel: {missing_short}."
    return msg


# =============================
# SIDEBAR INPUTS (stable; no disappearing sections)
# =============================
st.sidebar.header("Inputs")

inputs = {}
details = {}

# Mechanism type (overall)
inputs["mechanism_type"] = st.sidebar.selectbox(
    "Mechanism type (overall)",
    ["thermal", "scald", "chemical", "electrical", "inhalation", "friction", "unknown"],
    key="mech_type",
)

st.sidebar.subheader("Core burn assessment")

# Mechanism documented
inputs["mechanism_documented"] = st.sidebar.checkbox("Mechanism documented", key="mech_doc")
mech_opts = ["Scald", "Flame", "Contact", "Flash", "Steam", "Friction", "Hot oil/grease", "Unknown/unclear"]
mech_sel = st.sidebar.multiselect(
    "Mechanism (structured)",
    mech_opts,
    key="mech_struct",
    disabled=not inputs["mechanism_documented"],
)
add_detail(details, "Mechanism (structured)", mech_sel if inputs["mechanism_documented"] else None)

mech_txt = st.sidebar.text_area(
    "Mechanism details (free text)",
    height=70,
    placeholder="Example: hot water scald to R forearm; no chemical/electrical exposure; occurred ~18:30.",
    key="mech_txt",
    disabled=not inputs["mechanism_documented"],
)
add_detail(details, "Mechanism details", mech_txt if inputs["mechanism_documented"] else None)

# Time of injury
inputs["time_of_injury"] = st.sidebar.checkbox("Time of injury documented", key="toi")
tf = st.sidebar.radio(
    "Timeframe (structured)",
    ["< 1 hour", "1–6 hours", "6–24 hours", "24–72 hours", "> 72 hours", "Unknown"],
    key="timeframe",
    disabled=not inputs["time_of_injury"],
)
add_detail(details, "Timeframe (structured)", tf if inputs["time_of_injury"] else None)

toi_txt = st.sidebar.text_area(
    "Time of injury details (free text)",
    height=60,
    placeholder="Approx time, delayed presentation, progression since injury.",
    key="toi_txt",
    disabled=not inputs["time_of_injury"],
)
add_detail(details, "Time of injury details", toi_txt if inputs["time_of_injury"] else None)

# Morphology
inputs["morphology_burn_consistent"] = st.sidebar.checkbox("Morphology consistent with burn", key="morph")
morph_opts = ["Blistering", "Eschar", "Tissue loss", "Charred/white/leathery", "Weeping/moist", "Dry/waxy"]
morph_sel = st.sidebar.multiselect(
    "Morphology (structured)",
    morph_opts,
    key="morph_struct",
    disabled=not inputs["morphology_burn_consistent"],
)
add_detail(details, "Morphology (structured)", morph_sel if inputs["morphology_burn_consistent"] else None)

morph_txt = st.sidebar.text_area(
    "Morphology details (free text)",
    height=60,
    placeholder="Describe appearance, borders, tenderness, cap refill, progression.",
    key="morph_txt",
    disabled=not inputs["morphology_burn_consistent"],
)
add_detail(details, "Morphology details", morph_txt if inputs["morphology_burn_consistent"] else None)

# Depth
inputs["depth_estimated"] = st.sidebar.checkbox("Depth estimated", key="depth")
depth = st.sidebar.radio(
    "Depth estimate (structured)",
    ["Superficial", "Superficial partial", "Deep partial", "Full thickness", "Uncertain"],
    key="depth_radio",
    disabled=not inputs["depth_estimated"],
)
add_detail(details, "Depth (structured)", depth if inputs["depth_estimated"] else None)

# TBSA
inputs["tbsa_estimated"] = st.sidebar.checkbox("TBSA estimated", key="tbsa")
tbsa_val = st.sidebar.number_input(
    "TBSA %",
    0.0, 100.0, 0.0, 0.5,
    key="tbsa_val",
    disabled=not inputs["tbsa_estimated"],
)
tbsa_method = st.sidebar.selectbox(
    "TBSA method",
    ["Rule of 9s", "Palmar method", "Lund-Browder", "Other/uncertain"],
    key="tbsa_method",
    disabled=not inputs["tbsa_estimated"],
)
add_detail(details, "TBSA % (structured)", f"{tbsa_val:.1f}%" if inputs["tbsa_estimated"] else None)
add_detail(details, "TBSA method (structured)", tbsa_method if inputs["tbsa_estimated"] else None)

# High-risk areas
inputs["location_high_risk_checked"] = st.sidebar.checkbox("High-risk areas assessed", key="hi_risk")
hi_opts = ["Face", "Hands", "Feet", "Genitals", "Perineum", "Major joints"]
hi_sel = st.sidebar.multiselect(
    "High-risk areas (structured)",
    hi_opts,
    key="hi_struct",
    disabled=not inputs["location_high_risk_checked"],
)
add_detail(details, "High-risk areas (structured)", hi_sel if inputs["location_high_risk_checked"] else None)

# Circumferential
inputs["circumferential_checked"] = st.sidebar.checkbox("Circumferential involvement assessed", key="circ")
circ = st.sidebar.radio(
    "Circumferential involvement",
    ["No", "Yes", "Uncertain"],
    key="circ_radio",
    disabled=not inputs["circumferential_checked"],
)
add_detail(details, "Circumferential involvement (structured)", circ if inputs["circumferential_checked"] else None)

# =============================
# Inhalation (always rendered; disabled until assessed)
# =============================
st.sidebar.subheader("Inhalation")

inputs["inhalation_risk_assessed"] = st.sidebar.checkbox("Inhalation risk assessed", key="inh_assessed")

inh_findings = st.sidebar.multiselect(
    "Inhalation findings (structured)",
    ["Enclosed space exposure", "Smoke exposure", "Soot in nares/oropharynx", "Singed nasal hairs",
     "Hoarseness/voice change", "Wheezing", "Stridor"],
    key="inh_findings",
    disabled=not inputs["inhalation_risk_assessed"],
)
inh_notes = st.sidebar.text_area(
    "Inhalation notes (free text)",
    height=60,
    placeholder="Airway exam, O2 requirement, COHb/ABG if obtained.",
    key="inh_notes",
    disabled=not inputs["inhalation_risk_assessed"],
)
inh_result = st.sidebar.radio(
    "Inhalation injury result (choose ONE)",
    ["Not present", "Present", "Uncertain"],
    key="inh_result",
    disabled=not inputs["inhalation_risk_assessed"],
)

inputs["inhalation_risk_present"] = bool(inputs["inhalation_risk_assessed"] and (inh_result == "Present"))

if inputs["inhalation_risk_assessed"]:
    add_detail(details, "Inhalation findings (structured)", inh_findings)
    add_detail(details, "Inhalation notes", inh_notes)
    add_detail(details, "Inhalation result (structured)", inh_result)

# =============================
# Vitals / context
# =============================
st.sidebar.subheader("Vitals / context")
inputs["vitals_reviewed"] = st.sidebar.checkbox("Vitals reviewed / instability assessed", key="vitals")
inputs["comorbidities_reviewed"] = st.sidebar.checkbox("Major comorbidities reviewed", key="comorb")

# =============================
# Consult question (one choice + text)
# =============================
st.sidebar.subheader("Consult question")
cq = st.sidebar.selectbox(
    "What do you want Burn to do? (choose ONE)",
    ["Depth/TBSA confirmation", "Debridement/wound care plan", "Transfer/burn center eval", "Airway/inhalation concern", "Other"],
    key="cq_struct",
)
inputs["consult_question_defined"] = True
add_detail(details, "Consult question (structured)", cq)

cq_txt = st.sidebar.text_area("Additional consult details (free text)", height=70, key="cq_txt")
add_detail(details, "Consult question notes", cq_txt)

# =============================
# Special cases
# =============================
st.sidebar.subheader("Special cases")
inputs["severe_skin_failure_flag"] = st.sidebar.checkbox("Severe skin failure suspected (e.g., SJS/TEN pattern)", key="sjs")

# =============================
# Mechanism-specific fields
# =============================
st.sidebar.subheader("Mechanism-specific fields")

if inputs["mechanism_type"] == "chemical":
    inputs["chemical_agent_known_if_chemical"] = st.sidebar.checkbox(
        "If chemical: agent identified + decontamination documented", key="chem_doc"
    )
    chem_txt = st.sidebar.text_area("Chemical details (free text)", height=60, key="chem_txt", disabled=not inputs["chemical_agent_known_if_chemical"])
    if inputs["chemical_agent_known_if_chemical"]:
        add_detail(details, "Chemical details", chem_txt)
else:
    inputs["chemical_agent_known_if_chemical"] = False

if inputs["mechanism_type"] == "electrical":
    inputs["electrical_voltage_known_if_electrical"] = st.sidebar.checkbox(
        "If electrical: voltage/LOC/ECG documented", key="elec_doc"
    )
    elec_txt = st.sidebar.text_area("Electrical details (free text)", height=60, key="elec_txt", disabled=not inputs["electrical_voltage_known_if_electrical"])
    if inputs["electrical_voltage_known_if_electrical"]:
        add_detail(details, "Electrical details", elec_txt)
else:
    inputs["electrical_voltage_known_if_electrical"] = False


# =============================
# MAIN OUTPUT (no columns, stable)
# =============================
st.header("Output")

readiness_pct, missing_labels = compute_readiness(inputs)
scope, why = scope_triage(inputs)
tier = recommend_tier(inputs, readiness_pct, scope)
msg = build_message(inputs, details, scope, tier, why, missing_labels)

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
