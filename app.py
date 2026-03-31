import streamlit as st
import json
from core.pipeline import run_full_pipeline

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Support Agent",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# CUSTOM CSS — clean, modern, dark-accented
# ─────────────────────────────────────────────
st.markdown("""
<style>
.main {
    max-width: 95% !important;
    padding-left: 2rem;
    padding-right: 2rem;
}

.block-container {
    padding-top: 2rem;
}

h1, h2, h3, h4 {
    color: #A8E6CF !important;
}

/* Global font */
html, body, [class*="css"] {
    font-family: 'Segoe UI', system-ui, sans-serif;
}

/* Hero header */
.hero {
    background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
    border-radius: 16px;
    padding: 2.4rem 2rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
    color: white;
}
.hero h1 {
    font-size: 2.5rem;
    font-weight: 700;
    margin: 0 0 0.3rem;
    letter-spacing: -0.5px;
    color: white !important;
}
.hero p {
    font-size: 1.1rem;
    color: #f1faee;
    margin: 0;
}

/* Card wrapper */
.card {
    background: #1e1e1e;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.card-title {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #a8e6cf;
    margin-bottom: 0.5rem;
}
.card-body {
    font-size: 1rem;
    color: #f1faee;
    line-height: 1.6;
}

/* Citation pill */
.citation-pill {
    display: inline-block;
    background: #2d3748;
    border: 1px solid #4a5568;
    border-radius: 8px;
    padding: 0.45rem 0.85rem;
    font-size: 0.88rem;
    color: #a8e6cf;
    margin: 0.25rem 0;
    width: 100%;
    box-sizing: border-box;
}

/* PASS / FAIL banner */
.compliance-pass {
    background: #1c4532;
    border: 1.5px solid #2f855a;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    font-weight: 600;
    color: #9ae6b4;
    font-size: 1rem;
}
.compliance-fail {
    background: #63171b;
    border: 1.5px solid #9b2c2c;
    border-radius: 10px;
    padding: 0.9rem 1.2rem;
    font-weight: 600;
    color: #feb2b2;
    font-size: 1rem;
}

/* Button style */
div.stButton > button {
    background: linear-gradient(90deg, #56ab2f, #a8e063);
    color: #1a1a2e;
    font-weight: 700;
    font-size: 1.1rem;
    border: none;
    border-radius: 10px;
    padding: 0.75rem 2rem;
    width: 100%;
    transition: transform 0.2s, opacity 0.2s;
}
div.stButton > button:hover {
    opacity: 0.9;
    transform: translateY(-2px);
}

/* Input box */
.stTextArea textarea {
    background-color: #1e1e1e !important;
    color: #f1faee !important;
    border-radius: 10px !important;
    border: 1.5px solid #4a5568 !important;
}

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Divider */
hr { border-color: #4a5568; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HERO HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🛒 Smart Support Agent</h1>
    <p>Policy-grounded AI decisions with built-in compliance verification</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MAIN INPUT
# ─────────────────────────────────────────────
st.markdown("#### 💬 Describe your issue")
user_query = st.text_area(
    label="",
    placeholder="e.g. My camera arrived with a cracked lens. I'd like a refund.",
    height=110,
    label_visibility="collapsed"
)

run_btn = st.button("🔍 Resolve Issue")

# ─────────────────────────────────────────────
# RESOLUTION PIPELINE
# ─────────────────────────────────────────────
if run_btn:
    if not user_query.strip():
        st.warning("⚠️ Please enter your issue before submitting.")
    else:
        with st.spinner("🤖 Processing your request through the AI Pipeline..."):
            result = run_full_pipeline(user_query)
            resolution = result["resolution"]
            compliance = result["compliance"]
            decision = result["decision"]
            decision_status = decision["status"]

        st.markdown("---")

        # ── Error gate ──────────────────────────────
        if "error" in resolution:
            st.error(f"❌ Resolution Error: `{resolution['error']}`")
            st.stop()

        col_left, col_right = st.columns([2, 1])

        with col_left:
            # ── Response ────────────────────────────────
            st.subheader("📢 Response")
            st.success(resolution.get('user_message', '—'))

            # ── Justification ───────────────────────────
            st.subheader("📖 Justification")
            st.markdown(f"""
            <div class="card">
                <div class="card-title">Internal Reasoning</div>
                <div class="card-body">{resolution.get('justification', '—')}</div>
            </div>
            """, unsafe_allow_html=True)

            # ── Citations ───────────────────────────────
            st.subheader("📚 Policy Citations")
            citations = resolution.get("citations", [])
            if citations:
                for c in citations:
                    st.info(c.get('policy_text', ''))
            else:
                st.markdown("_No citations returned._")

            # ── Next Steps ──────────────────────────────
            st.subheader("🚀 Next Steps")
            st.write(resolution.get('next_steps', '—'))

        with col_right:
            # ── Decision ────────────────────────────────
            st.subheader("🏷️ Decision")
            st.metric("Status", decision_status)
            st.write(f"Action: {decision.get('action', 'NONE')}")
            st.write(f"Reason: {decision.get('reason', '—')}")

            # ── Compliance ──────────────────────────────
            st.subheader("🛡️ Compliance")
            if compliance["status"] == "PASS":
                st.success("✅ Verified Response")
            else:
                st.error("❌ Issues Detected")
                for issue in compliance.get("issues", []):
                    st.warning(issue)

            st.metric("Confidence", f"{int(compliance['confidence_score']*100)}%")

        st.markdown("---")
        # ── Raw JSON expandable ─────────────────────
        st.expander("🔍 View Raw JSON Output").json(result)
