import json
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Burn Consult Tool", layout="wide")
st.title("Burn Consult Tool (TBSA Click Map Prototype)")

# --- TBSA mapping (adult rule-of-nines-ish big regions) ---
# These are simplified. You can refine later (e.g., split arms into ant/post).
TBSA = {
    "head_ant": 4.5,
    "torso_ant": 18.0,
    "r_arm_ant": 4.5,
    "l_arm_ant": 4.5,
    "r_leg_ant": 9.0,
    "l_leg_ant": 9.0,
    "perineum": 1.0,

    "head_post": 4.5,
    "torso_post": 18.0,
    "r_arm_post": 4.5,
    "l_arm_post": 4.5,
    "r_leg_post": 9.0,
    "l_leg_post": 9.0,
}

# --- Minimal SVG: two panels (Anterior/Posterior) with clickable regions ---
# Each region is a <rect> with id matching TBSA keys above.
SVG = """
<div style="display:flex; gap:24px; align-items:flex-start;">
  <div style="flex:1;">
    <div style="font-weight:600; margin-bottom:8px;">Anterior</div>
    <svg id="svg_ant" width="280" height="520" viewBox="0 0 280 520" style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:16px;">
      <!-- head -->
      <rect id="head_ant" x="115" y="30" width="50" height="50" rx="18" class="region"/>
      <!-- torso -->
      <rect id="torso_ant" x="90" y="85" width="100" height="150" rx="18" class="region"/>
      <!-- arms -->
      <rect id="l_arm_ant" x="40" y="95" width="45" height="140" rx="16" class="region"/>
      <rect id="r_arm_ant" x="195" y="95" width="45" height="140" rx="16" class="region"/>
      <!-- legs -->
      <rect id="l_leg_ant" x="95" y="240" width="55" height="220" rx="18" class="region"/>
      <rect id="r_leg_ant" x="150" y="240" width="55" height="220" rx="18" class="region"/>
      <!-- perineum -->
      <rect id="perineum" x="130" y="220" width="20" height="20" rx="6" class="region"/>
    </svg>
  </div>

  <div style="flex:1;">
    <div style="font-weight:600; margin-bottom:8px;">Posterior</div>
    <svg id="svg_post" width="280" height="520" viewBox="0 0 280 520" style="background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.08); border-radius:16px;">
      <!-- head -->
      <rect id="head_post" x="115" y="30" width="50" height="50" rx="18" class="region"/>
      <!-- torso -->
      <rect id="torso_post" x="90" y="85" width="100" height="150" rx="18" class="region"/>
      <!-- arms -->
      <rect id="l_arm_post" x="40" y="95" width="45" height="140" rx="16" class="region"/>
      <rect id="r_arm_post" x="195" y="95" width="45" height="140" rx="16" class="region"/>
      <!-- legs -->
      <rect id="l_leg_post" x="95" y="240" width="55" height="220" rx="18" class="region"/>
      <rect id="r_leg_post" x="150" y="240" width="55" height="220" rx="18" class="region"/>
    </svg>
  </div>
</div>
"""

# --- JS bridge: toggles selected class, sums TBSA, returns JSON to Streamlit ---
# Streamlit Cloud supports postMessage via the standard component protocol.
COMPONENT = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body {{
    margin: 0;
    color: #E5E7EB;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  }}
  .region {{
    fill: rgba(255,255,255,0.06);
    stroke: rgba(255,255,255,0.22);
    stroke-width: 1;
    cursor: pointer;
    transition: 120ms ease-in-out;
  }}
  .region:hover {{
    fill: rgba(99,102,241,0.18);
    stroke: rgba(99,102,241,0.65);
  }}
  .region.selected {{
    fill: rgba(99,102,241,0.35);
    stroke: rgba(99,102,241,0.95);
    stroke-width: 1.2;
  }}
  .meta {{
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(255,255,255,0.03);
    line-height: 1.35;
  }}
  .meta b {{ font-weight: 650; }}
</style>
</head>
<body>
  {SVG}
  <div class="meta">
    <div><b>Selected regions:</b> <span id="sel">(none)</span></div>
    <div><b>Estimated TBSA:</b> <span id="tbsa">0.0</span>%</div>
    <div style="opacity:0.75; margin-top:6px;">Click a region to toggle. This is a simplified demo map.</div>
  </div>

<script>
  const TBSA = {json.dumps(TBSA)};
  const selected = new Set();

  function compute() {{
    let total = 0.0;
    selected.forEach(k => {{
      if (TBSA[k] !== undefined) total += TBSA[k];
    }});
    return Math.round(total * 10) / 10;
  }}

  function updateUI() {{
    const selArr = Array.from(selected);
    document.getElementById("sel").textContent = selArr.length ? selArr.join(", ") : "(none)";
    const total = compute();
    document.getElementById("tbsa").textContent = total.toFixed(1);

    // Send value to Streamlit
    const payload = {{ selected: selArr, tbsa: total }};
    // Streamlit component protocol
    window.parent.postMessage(
      {{ isStreamlitMessage: true, type: "streamlit:setComponentValue", value: payload }},
      "*"
    );
  }}

  function toggle(id) {{
    const el = document.getElementById(id);
    if (!el) return;
    if (selected.has(id)) {{
      selected.delete(id);
      el.classList.remove("selected");
    }} else {{
      selected.add(id);
      el.classList.add("selected");
    }}
    updateUI();
  }}

  // Wire up all regions
  Object.keys(TBSA).forEach(id => {{
    const el = document.getElementById(id);
    if (el) {{
      el.addEventListener("click", () => toggle(id));
    }}
  }});

  // Initial push
  updateUI();
</script>
</body>
</html>
"""

st.markdown("### TBSA selector (clickable prototype)")
result = components.html(COMPONENT, height=640)

# Streamlit receives `result` only after a click triggers postMessage updates.
st.markdown("### TBSA output received by Streamlit")
st.write(result)

# If you want to use it downstream:
if isinstance(result, dict):
    st.success(f"TBSA = {result.get('tbsa', 0)}%")
    st.write("Regions:", result.get("selected", []))
else:
    st.info("Click regions above to calculate TBSA.")
