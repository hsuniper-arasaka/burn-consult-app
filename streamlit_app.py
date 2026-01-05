import streamlit as st

st.set_page_config(layout="wide")
st.title("Burn Consult Tool — Minimal Test")
st.sidebar.header("Inputs")

assessed = st.sidebar.checkbox("Inhalation risk assessed", key="t_inh_assessed")

findings = st.sidebar.multiselect(
    "Inhalation findings",
    ["Soot", "Hoarseness", "Enclosed space", "Stridor"],
    disabled=not assessed,
    key="t_inh_findings",
)

notes = st.sidebar.text_area(
    "Inhalation notes",
    disabled=not assessed,
    key="t_inh_notes",
)

result = st.sidebar.radio(
    "Inhalation result",
    ["Not present", "Present", "Uncertain"],
    disabled=not assessed,
    key="t_inh_result",
)

present = assessed and (result == "Present")

st.header("Output")
st.write("Assessed:", assessed)
st.write("Present:", present)
st.write("Findings:", findings)
st.write("Notes:", notes if notes else "(none)")
