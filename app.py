import streamlit as st

st.set_page_config(page_title="Consult Readiness Platform", layout="wide")

st.title("Consult Readiness Platform")
st.caption("Decision support only. Adapt to local protocols. Do not enter PHI on hosted versions.")

st.markdown("""
### Available modules
Use the left sidebar to choose a consult module:

- **Burn Consult Readiness**
- **Acute Appendicitis Consult Readiness**
""")

st.info("Tip: Streamlit automatically creates the page list from files inside the `pages/` folder.")
