import streamlit as st

st.set_page_config(page_title="Appendicitis Consult Readiness", layout="wide")

st.title("Acute Appendicitis Consult Readiness")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

# -----------------------------
# Helpers
# -----------------------------
def add_detail(d: dict, label: str, value):
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        value = ", ".join([str(v).strip() for v in value if str(v).strip()])
    value = str(value).strip()
    if value:
        d[label] = value

def compute_readiness(inputs: dict):
    """
    Readiness = "do we have enough info for a useful Gen Surg consult?"
    """
    required = [
        "vitals_reviewed",
        "pregnancy_checked_if_applicable",
        "pain_duration_documented",
        "pain_location_documented",
        "exam_documented",
        "wbc_checked",
        "imaging_addressed",
        "consult_question_defined",
    ]
    done = [k for k in required if inputs.get(k) is True]
    missing = [k for k in required if inputs.get(k) is not True]
    pct = round((len(done) / len(required)) * 100, 1)

    labels = {
        "vitals_reviewed": "Vitals reviewed / instability assessed",
        "pregnancy_checked_if_applicable": "Pregnancy test/gestation addressed (if applicable)",
        "pain_duration_documented": "Duration / timeline documented",
        "pain_location_documented": "Pain location + migration documented",
        "exam_documented": "Abdominal exam documented (guarding/rebound/peritonitis?)",
        "wbc_checked": "CBC/WBC addressed",
        "imaging_addressed": "Imaging plan/result addressed (US/CT/MRI)",
        "consult_question_defined": "Consult question defined",
    }
    return pct, [labels[m] for m in missing]

def triage_scope(inputs: dict):
    """
    Scope/status (not a diagnosis):
    - "CONSULT NOW" if unstable/peritonitis/sepsis/imaging-confirmed/perforation concern.
    - Otherwise tier based on suspicion.
    """
    unstable = inputs.get("unstable") is True
    peritonitis = inputs.get("peritonitis") is True
    sepsis = inputs.get("sepsis") is True
    imaging_confirmed = inputs.get("imaging_confirmed") is True
    perf_or_abscess = inputs.get("perforation_or_abscess") is True

    if unstable or peritonitis or sepsis or imaging_confirmed or perf_or_abscess:
        return "HIGH RISK", "Red flags present (unstable/peritonitis/sepsis/confirmed or complicated appendicitis)."

    suspicion = inputs.get("clinical_suspicion", "uncertain")
    if suspicion in ["high", "moderate"]:
        return "LIKELY", "Clinical picture reasonably consistent with appendicitis."
    if suspicion == "low":
        return "UNLIKELY", "Clinical picture less consistent with appendicitis."
    return "UNCERTAIN", "Insufficient data to estimate likelihood."

def recommendation_tier(inputs: dict, readiness_pct: float, scope: str):
    if scope == "HIGH RISK":
        return "CONSULT NOW"

    suspicion = inputs.get("clinical_suspicion", "uncertain")

    if suspicion == "high":
        return "STRONGLY RECOMMEND GEN SURG CONSULT"
    if suspicion == "moderate":
        return "RECOMMEND GEN SURG CONSULT" if readiness_pct >= 60 else "LOW RECOMMENDATION (GET KEY INFO FIRST)"
    if suspicion == "low":
        return "CONSIDER ALTERNATE SERVICE / OBSERVE"
    return "CONSIDER ALTERNATE SERVICE / GET MORE DATA"

def build_message(inputs: dict, details: dict, tier: str, why: str, missing: list[str]):
    key_lines = [f"- {k}: {v}" for k, v in details.items() if str(v).strip()]
    key_block = "\n".join(key_lines).strip()
    missing_short = "; ".join(missing[:6]) if missing else ""

    msg = f"Recommend: **{tier}**. Rationale: {why}"
    if key_block:
        msg += f"\n\nKey details:\n{key_block}"
    if missing_short:
        msg += f"\n\nMissing items to make consult higher-yield: {missing_short}."
    return msg

# -----------------------------
# UI (Sidebar inputs)
# -----------------------------
st.sidebar.header("Inputs")

details = {}
inputs = {}

# Clinical suspicion (forced one choice)
inputs["clinical_suspicion"] = st.sidebar.radio(
    "Clinical suspicion for appendicitis (choose ONE)",
    ["high", "moderate", "low", "uncertain"],
    index=3,
)

# Vitals / instability
inputs["vitals_reviewed"] = st.sidebar.checkbox("Vitals reviewed", value=False)
inputs["unstable"] = st.sidebar.checkbox("Hemodynamic instability / shock", value=False)
inputs["sepsis"] = st.sidebar.checkbox("Sepsis concern (fever + tachy + toxic)", value=False)

st.sidebar.divider()

# Timeline / pain story
inputs["pain_duration_documented"] = st.sidebar.checkbox("Duration documented", value=False)
dur = st.sidebar.radio(
    "Duration (structured)",
    ["< 12h", "12–24h", "24–48h", "> 48h", "Unknown"],
    index=4,
)
add_detail(details, "Duration (structured)", dur)

inputs["pain_location_documented"] = st.sidebar.checkbox("Pain location/migration documented", value=False)
pain_loc = st.sidebar.multiselect(
    "Pain location (structured)",
    ["Periumbilical", "RLQ", "Diffuse", "Suprapubic", "Flank/back", "RUQ", "Other"],
)
add_detail(details, "Pain location (structured)", pain_loc)

migration = st.sidebar.radio(
    "Migratory pain to RLQ?",
    ["Yes", "No", "Unclear"],
    index=2,
)
add_detail(details, "Migratory pain", migration)

st.sidebar.divider()

# Exam
inputs["exam_documented"] = st.sidebar.checkbox("Abdominal exam documented", value=False)
inputs["peritonitis"] = st.sidebar.checkbox("Peritonitis (rebound/rigidity/guarding)", value=False)

exam_findings = st.sidebar.multiselect(
    "Exam (structured)",
    ["RLQ tenderness", "Guarding", "Rebound", "Rovsing", "Psoas", "Obturator", "No focal tenderness"],
)
add_detail(details, "Exam (structured)", exam_findings)

st.sidebar.divider()

# Labs
inputs["wbc_checked"] = st.sidebar.checkbox("CBC/WBC addressed", value=False)
wbc = st.sidebar.radio(
    "WBC (structured)",
    ["Normal/unknown", "Mildly elevated", "Elevated", "Very high", "Not obtained"],
    index=0,
)
add_detail(details, "WBC (structured)", wbc)

st.sidebar.divider()

# Pregnancy / UA (if applicable)
inputs["pregnancy_checked_if_applicable"] = st.sidebar.checkbox("Pregnancy status addressed (if applicable)", value=False)
preg = st.sidebar.radio(
    "Pregnancy status (structured)",
    ["Not applicable", "Negative", "Positive", "Unknown"],
    index=0,
)
add_detail(details, "Pregnancy status (structured)", preg)

st.sidebar.divider()

# Imaging
inputs["imaging_addressed"] = st.sidebar.checkbox("Imaging plan/result addressed", value=False)
imaging = st.sidebar.radio(
    "Imaging status (choose ONE)",
    ["Not done yet", "Ordered/pending", "Negative", "Equivocal", "Confirmed appendicitis"],
    index=0,
)
add_detail(details, "Imaging status (structured)", imaging)

inputs["imaging_confirmed"] = (imaging == "Confirmed appendicitis")
inputs["perforation_or_abscess"] = st.sidebar.checkbox("Perforation/abscess concern (CT/clinical)", value=False)

st.sidebar.divider()

# Consult question (forced one choice)
inputs["consult_question_defined"] = True
cq = st.sidebar.selectbox(
    "What do you want Gen Surg to do? (choose ONE)",
    ["Evaluate for appendectomy", "Rule out complicated appendicitis", "Drain/abscess eval", "Admit to surgery vs medicine", "Other"],
)
add_detail(details, "Consult question (structured)", cq)

cq_txt = st.sidebar.text_area("Extra context (free text)", height=90)
add_detail(details, "Additional context", cq_txt)

# -----------------------------
# Output
# -----------------------------
readiness_pct, missing = compute_readiness(inputs)
scope, why = triage_scope(inputs)
tier = recommendation_tier(inputs, readiness_pct, scope)
msg = build_message(inputs, details, tier, why, missing)

st.header("Output")
st.write(f"**Scope:** {scope}")
st.write(f"**Recommendation:** {tier}")
st.write(f"**Readiness %:** {readiness_pct}%")

st.subheader("Paste-ready message")
st.text_area("", value=msg, height=220)

st.subheader("Top missing items")
if missing:
    for m in missing[:10]:
        st.write(f"• {m}")
else:
    st.write("None 🎯")
