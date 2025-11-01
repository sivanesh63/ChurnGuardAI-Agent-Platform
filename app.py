import logging
import streamlit as st
from dotenv import load_dotenv

from ui.sidebar import render_sidebar
from chat import render_chat_history, handle_user_query
from campaigns.sms import render_sms_campaign
from campaigns.email import render_email_campaign
from campaigns.calls import render_call_campaign
from ui.monitor import render_monitor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
load_dotenv()

# ---------------------- CONFIG --------------------------
st.set_page_config(page_title="ChurnGuard AI Agent", page_icon="📊", layout="wide")


def render_campaigns():
    """Render campaign sections in main page"""
    st.divider()
    st.subheader("🚀 Launch Campaigns")

    df = st.session_state.df
    model = st.session_state.model

    campaign_type = st.radio(
        "Select Campaign Type",
        ["📱 SMS Campaign", "📧 Email Campaign", "📞 Call Campaign"],
        horizontal=True,
        key="campaign_type",
    )

    if campaign_type == "📱 SMS Campaign":
        render_sms_campaign(df, model)
    elif campaign_type == "📧 Email Campaign":
        render_email_campaign(df, model)
    elif campaign_type == "📞 Call Campaign":
        render_call_campaign(df, model)


# ---------------------- MAIN APP --------------------------
def main():
    st.title("📊 ChurnGuard – AI Agent")
    st.markdown("**Upload data, ask questions, and launch retention campaigns**")

    model = render_sidebar()
    if model is None:
        st.warning("⚠️ Configure API key in sidebar")
        return

    if "df" not in st.session_state:
        st.info("👈 Upload CSV to get started")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 🤖 AI Assistant")
            st.markdown("Ask questions about your data in plain English")
        with col2:
            st.markdown("### 📱 SMS Campaigns")
            st.markdown("Target customers with personalized messages")
        with col3:
            st.markdown("### 📧 Email Campaigns")
            st.markdown("Send retention emails to specific segments")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = []

    df = st.session_state.df
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Records", f"{len(df):,}")
    with col2:
        st.metric("📋 Columns", len(df.columns))
    with col3:
        campaigns = len(st.session_state.get("campaign_logs", []))
        st.metric("🚀 Campaigns", campaigns)
    with col4:
        if "campaign_logs" in st.session_state:
            total_sent = sum(log["sent"] for log in st.session_state.campaign_logs)
            st.metric("📤 Messages Sent", f"{total_sent:,}")
        else:
            st.metric("📤 Messages Sent", "0")

    tab1, tab2, tab3 = st.tabs(["💬 Chat Assistant", "🚀 Campaigns", "📊 Monitor"])

    with tab1:
        render_chat_history()
        if prompt := st.chat_input("Ask about your data..."):
            handle_user_query(prompt, model)

    with tab2:
        render_campaigns()

    with tab3:
        render_monitor()


if __name__ == "__main__":
    main()
