import streamlit as st

# =============================
# Page config
# =============================
st.set_page_config(page_title="Appendicitis Consult Readiness", layout="wide")

st.title("General Surgery – Appendicitis Consult Readiness")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

# =============================
# Helpers
# =============================
def add_detail(d: dict, label: str, value):
    """Add non-empty values into a dict for message output."""
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        value = ", ".join([str(v).strip() for v in value if str(v).strip()])
    value = str(value).strip()
    if value:
        d[label] = value

def yes_no_uncertain(label: str, key: str, disabled: bool):
    return st.radio(label, ["No", "Yes", "Uncertain"], index=2, disabled=disabled, key=key)

def compute_readiness(inputs: dict):
    """
    Readiness = "is this consult actionable?"
    We require core documentation, not that findings are positive.
    """
    required = [
        "vitals_reviewed",
        "pain_location_documented",
        "pain_duration_documented",
        "exam_documented",
        "cbc_reviewed",
        "pregnancy_addressed",
        "imaging_addressed",
        "consult_question_defined",
    ]
    done = [k for k in required if inputs.get(k) is True]
    missing = [k for k in required if inputs.get(k) is not True]

    pct = round((len(done) / len(required)) * 100, 1)

    labels = {
        "vitals_reviewed": "Vitals reviewed / stability assessed",
        "pain_location_documented": "Pain location documented (incl. migration)",
        "pain_duration_documented": "Duration / timeline documented",
        "exam_documented": "Focused abdominal exam documented",
        "cbc_reviewed": "CBC/WBC addressed",
        "pregnancy_addressed": "Pregnancy status addressed (if applicable)",
        "imaging_addressed": "Imaging plan/result addressed",
        "consult_question_defined": "Consult question defined",
    }
    return pct, [labels[m] for m in missing]

def triage_scope(inputs: dict):
    """
    NOT a diagnosis. This is urgency/scope triage for Gen Surg involvement.
    """
    unstable = inputs.get("hemodynamic_instability") is True
    peritonitis = inputs.get("peritonitis") is True
    sepsis = inputs.get("sepsis_concern") is True
    imaging_confirmed = inputs.get("imaging_impression") == "Confirmed appendicitis"
    complicated = inputs.get("complicated_features") is True  # perf/abscess/free air/phlegmon

    if unstable or peritonitis or sepsis or imaging_confirmed or complicated:
        return "HIGH RISK", "Red flags present (instability/peritonitis/sepsis/confirmed or complicated appendicitis)."

    suspicion = inputs.get("clinical_suspicion", "Uncertain")
    if suspicion in ["High", "Moderate"]:
        return "LIKELY", "Clinical picture reasonably consistent with appendicitis."
    if suspicion == "Low":
        return "UNLIKELY", "Clinical picture less consistent with appendicitis."
    return "UNCERTAIN", "Insufficient data to estimate likelihood."

def recommendation_tier(inputs: dict, readiness_pct: float, scope: str):
    if scope == "HIGH RISK":
        return "CONSULT NOW"

    suspicion = inputs.get("clinical_suspicion", "Uncertain")

    if suspicion == "High":
        return "STRONGLY RECOMMEND GEN SURG CONSULT"
    if suspicion == "Moderate":
        return "RECOMMEND GEN SURG CONSULT" if readiness_pct >= 60 else "LOW RECOMMENDATION (GET KEY INFO FIRST)"
    if suspicion == "Low":
        return "CONSIDER ALTERNATE SERVICE / OBSERVE"
    return "CONSIDER ALTERNATE SERVICE / GET MORE DATA"

def build_message(details: dict, tier: str, why: str, missing: list[str]):
    lines = [f"- {k}: {v}" for k, v in details.items() if str(v).strip()]
    key_block = "\n".join(lines).strip()
    missing_short = "; ".join(missing[:6]) if missing else ""

    msg = f"Recommend: {tier}. Rationale: {why}"
    if key_block:
        msg += f"\n\nKey details:\n{key_block}"
    if missing_short:
        msg += f"\n\nMissing items to make consult higher-yield: {missing_short}."
    return msg

# =============================
# UI (Sidebar)
# =============================
st.sidebar.header("Inputs")

inputs = {}
details = {}

# --- Clinical suspicion (forced one choice)
inputs["clinical_suspicion"] = st.sidebar.radio(
    "Clinical suspicion for appendicitis (choose ONE)",
    ["High", "Moderate", "Low", "Uncertain"],
    index=3,
)

st.sidebar.divider()

# =============================
# Vitals / stability (checkbox + numbers + free text)
# =============================
st.sidebar.subheader("Vitals / stability")

inputs["vitals_reviewed"] = st.sidebar.checkbox("Vitals reviewed / stability assessed", value=False, key="vitals_cb")

# Use disabled fields (stable layout)
v_disabled = not inputs["vitals_reviewed"]

colA, colB = st.sidebar.columns(2)
hr = colA.number_input("HR", min_value=0, max_value=250, value=0, step=1, disabled=v_disabled, key="hr")
sbp = colB.number_input("SBP", min_value=0, max_value=300, value=0, step=1, disabled=v_disabled, key="sbp")
colC, colD = st.sidebar.columns(2)
dbp = colC.number_input("DBP", min_value=0, max_value=200, value=0, step=1, disabled=v_disabled, key="dbp")
temp = colD.number_input("Temp (°C)", min_value=30.0, max_value=45.0, value=0.0, step=0.1, disabled=v_disabled, key="temp")

colE, colF = st.sidebar.columns(2)
rr = colE.number_input("RR", min_value=0, max_value=80, value=0, step=1, disabled=v_disabled, key="rr")
spo2 = colF.number_input("SpO₂ (%)", min_value=0, max_value=100, value=0, step=1, disabled=v_disabled, key="spo2")

lactate = st.sidebar.number_input("Lactate (optional)", min_value=0.0, max_value=30.0, value=0.0, step=0.1, disabled=v_disabled, key="lactate")

unstable_choice = st.sidebar.radio(
    "Hemodynamic instability/shock?",
    ["No", "Yes", "Uncertain"],
    index=2,
    disabled=v_disabled,
    key="unstable_radio",
)
inputs["hemodynamic_instability"] = (unstable_choice == "Yes")

sepsis_choice = st.sidebar.radio(
    "Sepsis concern?",
    ["No", "Yes", "Uncertain"],
    index=2,
    disabled=v_disabled,
    key="sepsis_radio",
)
inputs["sepsis_concern"] = (sepsis_choice == "Yes")

vitals_txt = st.sidebar.text_area(
    "Vitals/context (free text)",
    height=80,
    placeholder="Trends, fluids/pressors, appearance/toxic, pain control, etc.",
    disabled=v_disabled,
    key="vitals_txt",
)

if inputs["vitals_reviewed"]:
    # Only add meaningful values (ignore zeros)
    vitals_parts = []
    if hr: vitals_parts.append(f"HR {hr}")
    if sbp or dbp: vitals_parts.append(f"BP {sbp}/{dbp}")
    if temp: vitals_parts.append(f"T {temp:.1f}°C")
    if rr: vitals_parts.append(f"RR {rr}")
    if spo2: vitals_parts.append(f"SpO₂ {spo2}%")
    if lactate: vitals_parts.append(f"Lactate {lactate:.1f}")
    if vitals_parts:
        add_detail(details, "Vitals", ", ".join(vitals_parts))
    add_detail(details, "Vitals/context", vitals_txt)
    add_detail(details, "Hemodynamic instability", unstable_choice)
    add_detail(details, "Sepsis concern", sepsis_choice)

st.sidebar.divider()

# =============================
# Pain story (checkbox + full abdomen regions + free text)
# =============================
st.sidebar.subheader("Pain story")

inputs["pain_duration_documented"] = st.sidebar.checkbox("Duration / timeline documented", value=False, key="dur_cb")
dur_disabled = not inputs["pain_duration_documented"]

duration = st.sidebar.radio(
    "Duration (structured)",
    ["< 12 hours", "12–24 hours", "24–48 hours", "> 48 hours", "Unknown"],
    index=4,
    disabled=dur_disabled,
    key="dur_struct",
)
dur_txt = st.sidebar.text_area(
    "Timeline details (free text)",
    height=70,
    placeholder="Onset, progression, sudden vs gradual, worsening, prior episodes.",
    disabled=dur_disabled,
    key="dur_txt",
)

if inputs["pain_duration_documented"]:
    add_detail(details, "Duration", duration)
    add_detail(details, "Timeline details", dur_txt)

inputs["pain_location_documented"] = st.sidebar.checkbox("Pain location documented (incl. migration)", value=False, key="loc_cb")
loc_disabled = not inputs["pain_location_documented"]

locations = st.sidebar.multiselect(
    "Pain location (structured)",
    [
        "RUQ", "RLQ", "LUQ", "LLQ",
        "Epigastric", "Periumbilical", "Suprapubic",
        "Diffuse/generalized", "Flank", "Back", "Pelvic", "Other"
    ],
    disabled=loc_disabled,
    key="loc_multi",
)

migration = st.sidebar.radio(
    "Migratory pain (periumbilical → RLQ)?",
    ["No", "Yes", "Unclear"],
    index=2,
    disabled=loc_disabled,
    key="migration_radio",
)

pain_txt = st.sidebar.text_area(
    "Pain details (free text)",
    height=80,
    placeholder="Radiation, triggers, anorexia/N/V, bowel changes, urinary symptoms, etc.",
    disabled=loc_disabled,
    key="pain_txt",
)

if inputs["pain_location_documented"]:
    add_detail(details, "Pain location", locations)
    add_detail(details, "Migratory pain", migration)
    add_detail(details, "Pain details", pain_txt)

st.sidebar.divider()

# =============================
# Abdominal exam (checkbox + structured findings + free text)
# =============================
st.sidebar.subheader("Abdominal exam")

inputs["exam_documented"] = st.sidebar.checkbox("Abdominal exam documented", value=False, key="exam_cb")
exam_disabled = not inputs["exam_documented"]

exam_findings = st.sidebar.multiselect(
    "Exam (structured)",
    [
        "RLQ tenderness", "Guarding", "Rebound", "Peritoneal abdomen (diffuse)",
        "Rovsing", "Psoas", "Obturator",
        "CVA tenderness", "Distension", "Palpable mass",
        "Benign exam", "No focal tenderness"
    ],
    disabled=exam_disabled,
    key="exam_multi",
)

peritonitis_choice = st.sidebar.radio(
    "Peritonitis present?",
    ["No", "Yes", "Uncertain"],
    index=2,
    disabled=exam_disabled,
    key="peritonitis_radio",
)
inputs["peritonitis"] = (peritonitis_choice == "Yes")

exam_txt = st.sidebar.text_area(
    "Exam details (free text)",
    height=90,
    placeholder="Write what you'd put in the note. Include guarding/rebound, localization, change over time.",
    disabled=exam_disabled,
    key="exam_txt",
)

if inputs["exam_documented"]:
    add_detail(details, "Exam findings", exam_findings)
    add_detail(details, "Peritonitis", peritonitis_choice)
    add_detail(details, "Exam details", exam_txt)

st.sidebar.divider()

# =============================
# Labs (CBC/WBC addressed + numeric fields + free text)
# =============================
st.sidebar.subheader("Labs")

inputs["cbc_reviewed"] = st.sidebar.checkbox("CBC/WBC addressed", value=False, key="cbc_cb")
cbc_disabled = not inputs["cbc_reviewed"]

wbc = st.sidebar.number_input("WBC (x10^3/µL)", min_value=0.0, max_value=60.0, value=0.0, step=0.1, disabled=cbc_disabled, key="wbc")
anc = st.sidebar.number_input("ANC (optional)", min_value=0.0, max_value=60.0, value=0.0, step=0.1, disabled=cbc_disabled, key="anc")
crp = st.sidebar.number_input("CRP (optional)", min_value=0.0, max_value=500.0, value=0.0, step=0.5, disabled=cbc_disabled, key="crp")

labs_txt = st.sidebar.text_area(
    "Labs context (free text)",
    height=70,
    placeholder="Trends, immunosuppression/steroids, other labs (CMP/UA) if relevant.",
    disabled=cbc_disabled,
    key="labs_txt",
)

if inputs["cbc_reviewed"]:
    if wbc:
        add_detail(details, "WBC", f"{wbc:.1f}")
    if anc:
        add_detail(details, "ANC", f"{anc:.1f}")
    if crp:
        add_detail(details, "CRP", f"{crp:.1f}")
    add_detail(details, "Labs context", labs_txt)

# Pregnancy status addressed (if applicable)
inputs["pregnancy_addressed"] = st.sidebar.checkbox("Pregnancy status addressed (if applicable)", value=False, key="preg_cb")
preg_disabled = not inputs["pregnancy_addressed"]

preg_status = st.sidebar.radio(
    "Pregnancy status (structured)",
    ["Not applicable", "Negative", "Positive", "Unknown"],
    index=0,
    disabled=preg_disabled,
    key="preg_radio",
)
preg_txt = st.sidebar.text_area(
    "Pregnancy/GYN context (free text)",
    height=60,
    placeholder="LMP, contraception, pelvic symptoms, ovarian torsion concern, etc.",
    disabled=preg_disabled,
    key="preg_txt",
)

if inputs["pregnancy_addressed"]:
    add_detail(details, "Pregnancy status", preg_status)
    add_detail(details, "Pregnancy/GYN context", preg_txt)

st.sidebar.divider()

# =============================
# Imaging (checkbox + modality + key features + free text)
# =============================
st.sidebar.subheader("Imaging")

inputs["imaging_addressed"] = st.sidebar.checkbox("Imaging plan/result addressed", value=False, key="img_cb")
img_disabled = not inputs["imaging_addressed"]

imaging_status = st.sidebar.radio(
    "Imaging status (structured)",
    ["Not done", "Ordered/pending", "Completed"],
    index=0,
    disabled=img_disabled,
    key="img_status",
)

modality = st.sidebar.selectbox(
    "Modality (structured)",
    ["CT A/P w/ IV contrast", "CT A/P no contrast", "Ultrasound", "MRI", "Other/unknown"],
    disabled=img_disabled,
    key="img_modality",
)

inputs["imaging_impression"] = st.sidebar.radio(
    "Impression (choose ONE)",
    ["Not available", "Negative", "Equivocal", "Confirmed appendicitis"],
    index=0,
    disabled=img_disabled,
    key="img_impression",
)

key_features = st.sidebar.multiselect(
    "Key imaging features (structured)",
    [
        "Enlarged appendix", "Wall thickening/enhancement", "Periappendiceal fat stranding",
        "Appendicolith", "Free fluid", "Abscess", "Perforation/free air", "Phlegmon"
    ],
    disabled=img_disabled,
    key="img_features",
)

# Complicated features trigger
inputs["complicated_features"] = False
if inputs["imaging_addressed"] and ("Abscess" in key_features or "Perforation/free air" in key_features or "Phlegmon" in key_features):
    inputs["complicated_features"] = True

img_txt = st.sidebar.text_area(
    "Imaging details / report snippet (free text)",
    height=90,
    placeholder="Paste 1–2 lines of impression or describe key findings.",
    disabled=img_disabled,
    key="img_txt",
)

if inputs["imaging_addressed"]:
    add_detail(details, "Imaging status", imaging_status)
    add_detail(details, "Imaging modality", modality)
    add_detail(details, "Imaging impression", inputs["imaging_impression"])
    add_detail(details, "Imaging features", key_features)
    add_detail(details, "Imaging details", img_txt)

st.sidebar.divider()

# =============================
# Consult question (forced one choice + free text)
# =============================
st.sidebar.subheader("Consult question")

cq = st.sidebar.selectbox(
    "What do you want Gen Surg to do? (choose ONE)",
    [
        "Evaluate for appendectomy",
        "Guidance while workup ongoing",
        "Rule out complicated appendicitis",
        "Drain/abscess evaluation",
        "Admit to surgery vs medicine",
        "Other",
    ],
    key="cq_select",
)
inputs["consult_question_defined"] = True  # forced by selectbox
add_detail(details, "Consult question", cq)

cq_txt = st.sidebar.text_area(
    "Additional consult context (free text)",
    height=90,
    placeholder="Any constraints, anticoagulation, immunosuppression, social barriers, pain control, etc.",
    key="cq_txt",
)
add_detail(details, "Additional consult context", cq_txt)

# =============================
# Output
# =============================
readiness_pct, missing = compute_readiness(inputs)
scope, why = triage_scope(inputs)
tier = recommendation_tier(inputs, readiness_pct, scope)
msg = build_message(details, tier, why, missing)

st.header("Output")
st.write(f"**Scope:** {scope}")
st.write(f"**Recommendation:** {tier}")
st.write(f"**Readiness %:** {readiness_pct}%")

st.subheader("Paste-ready message")
st.text_area("", value=msg, height=260)

st.subheader("Top missing items")
if missing:
    for m in missing[:10]:
        st.write(f"• {m}")
else:
    st.write("None 🎯")
