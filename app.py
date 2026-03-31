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
# HERO HEADER  (centered column)
# ─────────────────────────────────────────────
_pad_l, _center, _pad_r = st.columns([1, 2, 1])
with _center:
    st.markdown("""
    <div class="hero">
        <h1>🛒 Smart Support Agent</h1>
        <p>Policy-grounded AI decisions with built-in compliance verification</p>
    </div>
    """, unsafe_allow_html=True)

    # ─────────────────────────────────────────
    # MAIN INPUT  (same centered column)
    # ─────────────────────────────────────────
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
            state = result["state"]
            clarifying_questions = result.get("clarifying_questions", [])
            decision_status = decision["status"]

        st.markdown("---")

        # ── Clarifying Questions banner ──────────────
        if clarifying_questions:
            st.markdown(f"""
            <div style="
                background-color:#2d2005;
                border-left:4px solid #f59e0b;
                border-radius:10px;
                padding:14px 18px;
                margin-bottom:16px;
            ">
                <div style="font-weight:700; color:#fbbf24; margin-bottom:8px;">
                    ⚠️ Clarifying Questions
                </div>
                {''.join(f'<div style="color:#fde68a; font-size:0.9rem; margin-bottom:4px;">• {q}</div>' for q in clarifying_questions)}
            </div>
            """, unsafe_allow_html=True)

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
                    source  = c.get("source", "Unknown")
                    section = c.get("section", "")
                    st.markdown(f"""
                    <div style="
                        background-color:#1e2a38;
                        padding:12px;
                        border-radius:10px;
                        margin-bottom:10px;
                        border-left:4px solid #4CAF50;
                    ">
                        <b>{c.get('policy_text', '')}</b><br>
                        <span style="color:#9ecfff; font-size:12px;">
                        📂 {source}{f' &bull; {section}' if section else ''}
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("_No citations returned._")

            # ── Next Steps ──────────────────────────────
            st.subheader("🚀 Next Steps")
            st.write(resolution.get('next_steps', '—'))

        with col_right:
            # ── Classification card ──────────────────────
            intent     = state.get("intent", "Unknown")
            confidence = state.get("confidence", None)
            conf_html  = f'<div style="color:#9ca3af; margin-top:6px; font-size:0.8rem;">Confidence: <b>{confidence}</b></div>' if confidence else ""
            st.markdown(f"""
            <div style="
                background-color:#1a1f2e;
                padding:20px;
                border-radius:12px;
                text-align:center;
                border:1px solid #2d3a55;
                margin-bottom:15px;
            ">
                <div style="font-size:0.75rem; font-weight:700; letter-spacing:1px;
                            text-transform:uppercase; color:#93c5fd; margin-bottom:8px;">
                    🧠 Classification
                </div>
                <div style="font-size:1.3rem; font-weight:800; color:#60a5fa;">
                    {intent}
                </div>
                {conf_html}
            </div>
            """, unsafe_allow_html=True)

            # ── Decision card ────────────────────────────
            status_color = "#4CAF50" if decision_status in ("APPROVED", "FULL_REFUND", "PARTIAL_REFUND") else "#FF4B4B"
            st.markdown(f"""
            <div style="
                background-color:#1f2937;
                padding:20px;
                border-radius:12px;
                text-align:center;
                border:1px solid #374151;
                margin-bottom:15px;
            ">
                <div style="font-size:0.75rem; font-weight:700; letter-spacing:1px;
                            text-transform:uppercase; color:#a8e6cf; margin-bottom:8px;">
                    🏷️ Decision
                </div>
                <div style="font-size:1.8rem; font-weight:800; color:{status_color};">
                    {decision_status}
                </div>
                <div style="color:#cbd5e0; margin-top:8px; font-size:0.9rem;">
                    Action: <b>{decision.get('action', 'NONE')}</b>
                </div>
                <div style="color:#9ca3af; margin-top:6px; font-size:0.8rem;">
                    {decision.get('reason', '')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Compliance card ──────────────────────────
            comp_color = "#4CAF50" if compliance["status"] == "PASS" else "#FF4B4B"
            comp_bg    = "#14291f" if compliance["status"] == "PASS" else "#2d1515"
            comp_border= "#2f855a" if compliance["status"] == "PASS" else "#9b2c2c"
            comp_icon  = "✅" if compliance["status"] == "PASS" else "❌"
            confidence = int(compliance['confidence_score'] * 100)
            st.markdown(f"""
            <div style="
                background-color:{comp_bg};
                padding:20px;
                border-radius:12px;
                text-align:center;
                border:1px solid {comp_border};
            ">
                <div style="font-size:0.75rem; font-weight:700; letter-spacing:1px;
                            text-transform:uppercase; color:#a8e6cf; margin-bottom:8px;">
                    🛡️ Compliance
                </div>
                <div style="font-size:1.8rem; font-weight:800; color:{comp_color};">
                    {comp_icon} {compliance['status']}
                </div>
                <div style="color:#cbd5e0; margin-top:8px; font-size:0.9rem;">
                    Confidence: <b>{confidence}%</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ── Compliance issues (if any) ───────────────
            if compliance["status"] != "PASS":
                for issue in compliance.get("issues", []):
                    st.warning(issue)

        st.markdown("---")
        # ── Raw JSON expandable ─────────────────────
        st.expander("🔍 View Raw JSON Output").json(result)
