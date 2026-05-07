"""
RailYatri — Streamlit Frontend (v2).

Modern conversational UI for the RailYatri railway assistant.
Uses st.chat_message / st.chat_input for native chat layout.
Dispatches rendering based on response_type from backend:
  - TEXT       → plain chat bubble
  - TRAIN_LIST → visual train cards
  - ERROR      → styled error message

Run with:  streamlit run frontend/app.py
"""

import streamlit as st
import requests
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = "http://localhost:8000"
AUTH_REGISTER = f"{API_BASE_URL}/auth/register"
AUTH_LOGIN    = f"{API_BASE_URL}/auth/login"
QUERY_URL     = f"{API_BASE_URL}/api/v1/query"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RailYatri — AI Railway Assistant",
    page_icon="🚆",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Inter', sans-serif;
    background: #0f1117;
    color: #e5e7eb;
}

/* ── Header ─────────────────────────────────────────── */
.ry-header {
    text-align: center;
    padding: 1.8rem 0 1rem;
}
.ry-header h1 {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
    margin-bottom: 0.2rem;
}
.ry-header p {
    color: #6b7280;
    font-size: 0.92rem;
    margin: 0;
}

/* ── Auth card ───────────────────────────────────────── */
.auth-card {
    max-width: 440px;
    margin: 1.5rem auto;
    padding: 2rem 2.2rem;
    border-radius: 20px;
    background: linear-gradient(145deg, #1a1d2e 0%, #141720 100%);
    border: 1px solid #2d3148;
    box-shadow: 0 8px 32px rgba(99, 102, 241, 0.1);
}

/* ── User bar ────────────────────────────────────────── */
.user-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.55rem 1rem;
    background: #1a1d2e;
    border-radius: 10px;
    border: 1px solid #2d3148;
    font-size: 0.83rem;
    color: #9ca3af;
    margin-bottom: 0.8rem;
}
.user-bar strong { color: #a5b4fc; }

/* ── Train card ──────────────────────────────────────── */
.train-card {
    background: linear-gradient(145deg, #1a1d2e 0%, #1e2235 100%);
    border: 1px solid #2d3148;
    border-left: 4px solid #6366f1;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin: 0.6rem 0;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.train-card:hover {
    border-left-color: #a855f7;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.2);
    transform: translateY(-1px);
}
.train-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.6rem;
}
.train-name {
    font-weight: 700;
    font-size: 1rem;
    color: #a5b4fc;
}
.train-number {
    font-size: 0.78rem;
    color: #6b7280;
    margin-top: 0.1rem;
}
.train-timing {
    font-size: 1.1rem;
    font-weight: 700;
    color: #e5e7eb;
    letter-spacing: 0.3px;
}
.train-arrow { color: #6366f1; margin: 0 0.4rem; }
.train-duration {
    font-size: 0.8rem;
    color: #9ca3af;
    margin-top: 0.2rem;
}
.train-meta {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.65rem;
}
.meta-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.73rem;
    font-weight: 500;
}
.pill-class    { background: #1e3a5f; color: #93c5fd; }
.pill-avail    { background: #14532d; color: #86efac; }
.pill-waitlist { background: #713f12; color: #fcd34d; }
.pill-fare     { background: #1e1b4b; color: #c4b5fd; }
.pill-days     { background: #1f2937; color: #9ca3af; }

/* ── Empty state ─────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #4b5563;
}
.empty-state .icon { font-size: 3.5rem; margin-bottom: 0.5rem; }
.empty-state h3 { color: #6b7280; font-weight: 500; margin-bottom: 0.5rem; }
.example-query {
    display: inline-block;
    margin: 0.2rem 0.3rem;
    padding: 0.4rem 0.9rem;
    background: #1a1d2e;
    border: 1px solid #2d3148;
    border-radius: 20px;
    font-size: 0.82rem;
    color: #a5b4fc;
    cursor: pointer;
}

/* ── Divider ─────────────────────────────────────────── */
.ry-divider {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #2d3148, transparent);
    margin: 0.8rem 0;
}

/* ── Error message ───────────────────────────────────── */
.error-msg {
    background: #1c0d0d;
    border: 1px solid #7f1d1d;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    color: #fca5a5;
    font-size: 0.88rem;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

if "token"      not in st.session_state: st.session_state.token      = None
if "user_email" not in st.session_state: st.session_state.user_email = None
if "messages"   not in st.session_state: st.session_state.messages   = []
if "auth_page"  not in st.session_state: st.session_state.auth_page  = "login"


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_register(email: str, password: str) -> dict:
    resp = requests.post(AUTH_REGISTER, json={"email": email, "password": password}, timeout=15)
    return {"status": resp.status_code, "data": resp.json()}


def api_login(email: str, password: str) -> dict:
    resp = requests.post(AUTH_LOGIN, json={"email": email, "password": password}, timeout=15)
    return {"status": resp.status_code, "data": resp.json()}


def api_query(query: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(QUERY_URL, json={"query": query}, headers=headers, timeout=60)
    return {"status": resp.status_code, "data": resp.json()}


# ---------------------------------------------------------------------------
# Train card rendering
# ---------------------------------------------------------------------------

def render_train_cards(data: dict) -> None:
    """Render train search results as visual cards using Streamlit components."""
    trains = data.get("trains", [])
    total  = data.get("total", 0)
    echoed = data.get("query_echoed", {})

    if total == 0:
        st.markdown(
            f'<div class="error-msg">🔍 No trains found from '
            f'<strong>{echoed.get("origin", "?")}</strong> to '
            f'<strong>{echoed.get("destination", "?")}</strong> '
            f'on {echoed.get("date", "?")}.<br>'
            f'Try a different date or nearby stations.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<div style="color:#9ca3af;font-size:0.88rem;margin-bottom:0.5rem;">'
        f'🚆 Found <strong style="color:#a5b4fc">{total} train(s)</strong> '
        f'· {echoed.get("origin","?")} → {echoed.get("destination","?")} '
        f'· {echoed.get("date","?")}</div>',
        unsafe_allow_html=True,
    )

    for train in trains:
        avail = train.get("availability", {})
        status = avail.get("status", "")
        fare   = avail.get("fare_inr", "N/A")
        cls    = avail.get("class", "N/A")
        days   = ", ".join(train.get("days_of_run", [])) or "—"

        # Status pill type
        if "WL" in str(status).upper() or "WAITLIST" in str(status).upper():
            avail_class = "pill-waitlist"
        else:
            avail_class = "pill-avail"

        card_html = f"""
        <div class="train-card">
            <div class="train-card-header">
                <div>
                    <div class="train-name">🚆 {train.get('train_name', '—')}</div>
                    <div class="train-number">#{train.get('train_number', '—')}</div>
                </div>
                <div style="text-align:right;">
                    <div class="train-timing">
                        {train.get('departure_time','?')}
                        <span class="train-arrow">→</span>
                        {train.get('arrival_time','?')}
                    </div>
                    <div class="train-duration">⏱ {train.get('duration','?')}</div>
                </div>
            </div>
            <div class="train-meta">
                <span class="meta-pill pill-class">🎫 {cls}</span>
                <span class="meta-pill {avail_class}">● {status or 'Available'}</span>
                <span class="meta-pill pill-fare">₹ {fare}</span>
                <span class="meta-pill pill-days">📅 {days}</span>
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Message rendering
# ---------------------------------------------------------------------------

def render_message(msg: dict) -> None:
    """Render a single chat message using st.chat_message."""
    role         = msg["role"]
    content      = msg["content"]
    response_type = msg.get("response_type", "TEXT")
    data         = msg.get("data")

    with st.chat_message(role, avatar="🧑" if role == "user" else "🚆"):
        if role == "assistant" and response_type == "TRAIN_LIST" and data:
            # Plain text summary first
            st.markdown(content)
            # Then visual cards
            render_train_cards(data)
        elif role == "assistant" and response_type == "ERROR":
            st.markdown(
                f'<div class="error-msg">{content}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(content)


# ---------------------------------------------------------------------------
# Auth UI
# ---------------------------------------------------------------------------

def render_auth() -> None:
    st.markdown("""
    <div class="ry-header">
        <h1>🚆 RailYatri</h1>
        <p>Your AI-powered Indian railway assistant</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "🔑 Sign In", use_container_width=True,
            type="primary" if st.session_state.auth_page == "login" else "secondary",
            key="btn_login_tab",
        ):
            st.session_state.auth_page = "login"
            st.rerun()
    with col2:
        if st.button(
            "📝 Register", use_container_width=True,
            type="primary" if st.session_state.auth_page == "register" else "secondary",
            key="btn_register_tab",
        ):
            st.session_state.auth_page = "register"
            st.rerun()

    st.markdown('<hr class="ry-divider">', unsafe_allow_html=True)

    if st.session_state.auth_page == "login":
        _render_login()
    else:
        _render_register()


def _render_login() -> None:
    with st.form("login_form", clear_on_submit=False):
        st.markdown("#### 🔑 Welcome Back")
        email    = st.text_input("Email", placeholder="you@example.com", key="login_email")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="login_pw")
        submitted = st.form_submit_button("Sign In →", use_container_width=True, type="primary")

    if submitted:
        if not email or not password:
            st.error("Please fill in both fields.")
            return
        with st.spinner("Signing in…"):
            try:
                result = api_login(email, password)
                if result["status"] == 200:
                    st.session_state.token      = result["data"]["access_token"]
                    st.session_state.user_email = email
                    st.session_state.messages   = []
                    st.rerun()
                else:
                    st.error(f"❌ {result['data'].get('detail', 'Login failed')}")
            except requests.ConnectionError:
                st.error("🔌 Cannot reach the backend. Is the server running?")
            except Exception as exc:
                st.error(f"⚠️ {exc}")


def _render_register() -> None:
    with st.form("register_form", clear_on_submit=False):
        st.markdown("#### 📝 Create Your Account")
        email     = st.text_input("Email", placeholder="you@example.com", key="reg_email")
        password  = st.text_input("Password", type="password", placeholder="Min 6 characters", key="reg_pw")
        password2 = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="reg_pw2")
        submitted = st.form_submit_button("Create Account →", use_container_width=True, type="primary")

    if submitted:
        if not email or not password or not password2:
            st.error("Please fill in all fields.")
            return
        if password != password2:
            st.error("Passwords do not match.")
            return
        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return
        with st.spinner("Creating account…"):
            try:
                result = api_register(email, password)
                if result["status"] == 201:
                    st.success("✅ Account created! Please sign in.")
                    st.session_state.auth_page = "login"
                    st.rerun()
                else:
                    st.error(f"❌ {result['data'].get('detail', 'Registration failed')}")
            except requests.ConnectionError:
                st.error("🔌 Cannot reach the backend. Is the server running?")
            except Exception as exc:
                st.error(f"⚠️ {exc}")


# ---------------------------------------------------------------------------
# Chat UI
# ---------------------------------------------------------------------------

def render_chat() -> None:
    # Header
    st.markdown("""
    <div class="ry-header">
        <h1>🚆 RailYatri</h1>
        <p>Ask me about trains — routes, schedules, availability & more</p>
    </div>
    """, unsafe_allow_html=True)

    # User bar + logout
    col1, col2 = st.columns([5, 1])
    with col1:
        st.markdown(
            f'<div class="user-bar">👤 Logged in as '
            f'<strong>{st.session_state.user_email}</strong></div>',
            unsafe_allow_html=True,
        )
    with col2:
        if st.button("Logout", key="logout_btn", use_container_width=True):
            st.session_state.token      = None
            st.session_state.user_email = None
            st.session_state.messages   = []
            st.rerun()

    st.markdown('<hr class="ry-divider">', unsafe_allow_html=True)

    # Chat history
    if not st.session_state.messages:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🚆</div>
            <h3>Start a conversation</h3>
            <p style="font-size:0.85rem;margin-bottom:1rem;">Try one of these:</p>
            <span class="example-query">Trains from Delhi to Mumbai on 15 June</span>
            <span class="example-query">Sleeper trains from Surat to Chennai tomorrow</span>
            <span class="example-query">Hi!</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.messages:
            render_message(msg)

    st.markdown('<hr class="ry-divider">', unsafe_allow_html=True)

    # Chat input (native Streamlit component)
    user_input = st.chat_input(
        "Ask about trains… e.g. 'Trains from Surat to Mumbai on 20 June'",
        key="chat_input",
    )

    if user_input:
        # Immediately display user message
        st.session_state.messages.append({
            "role":          "user",
            "content":       user_input,
            "response_type": "TEXT",
            "data":          None,
        })

        # Call API
        with st.spinner("🔍 Thinking…"):
            try:
                result = api_query(user_input, st.session_state.token)

                if result["status"] == 200:
                    resp_data     = result["data"]
                    message       = resp_data.get("message", "No response received.")
                    response_type = resp_data.get("response_type", "TEXT")
                    data          = resp_data.get("data")

                    st.session_state.messages.append({
                        "role":          "assistant",
                        "content":       message,
                        "response_type": response_type,
                        "data":          data,
                    })

                elif result["status"] == 401:
                    st.error("🔒 Session expired. Please log in again.")
                    st.session_state.token = None
                    st.rerun()

                else:
                    detail = result["data"].get("detail", "An error occurred.")
                    st.session_state.messages.append({
                        "role":          "assistant",
                        "content":       f"⚠️ {detail}",
                        "response_type": "ERROR",
                        "data":          None,
                    })

            except requests.ConnectionError:
                st.session_state.messages.append({
                    "role":          "assistant",
                    "content":       "🔌 Cannot connect to the backend. Is the server running?",
                    "response_type": "ERROR",
                    "data":          None,
                })
            except Exception as exc:
                st.session_state.messages.append({
                    "role":          "assistant",
                    "content":       f"⚠️ Unexpected error: {exc}",
                    "response_type": "ERROR",
                    "data":          None,
                })

        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if st.session_state.token:
        render_chat()
    else:
        render_auth()


if __name__ == "__main__":
    main()
else:
    main()
