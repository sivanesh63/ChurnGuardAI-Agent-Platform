# ui/campaign_ui.py

import streamlit as st
import pandas as pd
from datetime import datetime
from config.settings import Config
from campaigns.sms_campaign import SMSCampaign
from campaigns.email_campaign import EmailCampaign
from campaigns.voice_campaign import VoiceCampaign
from core.query_generator import QueryGenerator
from core.code_executor import SafeExecutor

def render_campaigns():
    """Render campaign sections in main page"""
    st.divider()
    st.subheader("🚀 Launch Campaigns")

    df = st.session_state.df
    model = st.session_state.model

    # Campaign type selection
    campaign_type = st.radio(
        "Select Campaign Type",
        ["📱 SMS Campaign", "📧 Email Campaign", "📞 Call Campaign"],
        horizontal=True,
        key="campaign_type"
    )

    if campaign_type == "📱 SMS Campaign":
        render_sms_campaign(df, model)
    elif campaign_type == "📧 Email Campaign":
        render_email_campaign(df, model)
    elif campaign_type == "📞 Call Campaign":
        render_call_campaign(df, model)


def render_sms_campaign(df, model):
    """Render SMS campaign interface"""
    with st.container():
        st.markdown("#### 📱 SMS Campaign")
        
        st.info("📝 **Default Message:** 🎁 Hi! We miss you! As a valued customer, here's an EXCLUSIVE 30% OFF just for you. Use code: COMEBACK30. Valid for 48 hours only!")

        target_query = st.text_input(
            "🎯 Target Customers",
            placeholder="e.g., churn_probability > 0.8",
            key="sms_target"
        )

        phone_col = "PhoneNo"
        if phone_col not in df.columns:
            st.error("❌ 'PhoneNo' column not found in dataset.")
            return
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("🔍 Preview", key="sms_preview_btn", use_container_width=True):
                if target_query:
                    with st.spinner("Finding targets..."):
                        try:
                            query_gen = QueryGenerator(model)
                            code, _ = query_gen.generate_query(target_query, df)
                            executor = SafeExecutor(model)
                            result = executor.safe_eval(code, df)
                            if isinstance(result, pd.Series):
                                result = df[result]
                            st.session_state.sms_targets = result
                            st.success(f"✅ Found {len(result)} targets")
                            with st.expander("View Targets"):
                                st.dataframe(result.head(20))
                        except Exception as e:
                            st.error(f"Error: {e}")
                else:
                    st.warning("Enter target criteria")
        
        with col2:
            if st.button("📲 Send SMS", type="primary", key="sms_send_btn", use_container_width=True):
                if "sms_targets" not in st.session_state:
                    st.warning("Preview targets first")
                else:
                    with st.spinner("Sending..."):
                        config = Config()
                        campaign = SMSCampaign(
                            config.TWILIO_ACCOUNT_SID,
                            config.TWILIO_AUTH_TOKEN,
                            config.TWILIO_PHONE_NUMBER
                        )
                        result = campaign.send(st.session_state.sms_targets, phone_col)
                        
                        if result["success"]:
                            st.success(f"✅ Sent to {result['sent']} customers!")
                            
                            if result.get('details') and result['failed'] > 0:
                                with st.expander(f"⚠️ View {result['failed']} Failed Messages"):
                                    for detail in result['details']:
                                        st.text(detail)
                            
                            campaign.log_campaign(result, target_query)
                        else:
                            st.error(f"Failed: {result.get('error', 'Unknown error')}")


def render_email_campaign(df, model):
    """Render Email Campaign interface"""
    with st.container():
        st.markdown("### 📧 Email Campaign")

        st.info(
            "💌 **Default Email Content:**\n"
            "**Subject:** *We Miss You! Exclusive Offer Inside 🎁*\n\n"
            "**Body:** Personalized message with customer name and a 40% discount offer."
        )

        col1, col2 = st.columns([2, 1])

        with col1:
            target_query = st.text_input(
                "🎯 Target Customers",
                placeholder="e.g., churn_probability > 0.8",
                key="email_target"
            )

        with col2:
            email_col = "Email"
            if email_col not in df.columns:
                st.error("❌ The dataset must include an 'Email' column.")
                return

        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            if st.button("🔍 Preview", key="email_preview_btn", use_container_width=True):
                if not target_query:
                    st.warning("⚠️ Please enter a targeting condition first.")
                    return

                try:
                    query_gen = QueryGenerator(model)
                    code, _ = query_gen.generate_query(target_query, df)
                    executor = SafeExecutor(model)
                    result = executor.safe_eval(code, df)

                    if isinstance(result, pd.Series):
                        result = df[result]

                    st.session_state.email_targets = result
                    st.success(f"✅ Found {len(result)} target customers.")

                    with st.expander("📋 View Targeted Email List"):
                        st.dataframe(result[[email_col]].head(20))

                except Exception as e:
                    st.error(f"⚠️ Query Error: {e}")

        with col2:
            if st.button("📨 Send Emails", type="primary", key="email_send_btn", use_container_width=True):
                if "email_targets" not in st.session_state:
                    st.warning("⚠️ Please preview the target customers first.")
                    return

                with st.spinner("📤 Sending emails... Please wait ⏳"):
                    config = Config()
                    campaign = EmailCampaign(
                        config.EMAIL_HOST_USER,
                        config.EMAIL_HOST_PASSWORD,
                        config.SMTP_SERVER,
                        config.SMTP_PORT
                    )
                    result = campaign.send(st.session_state.email_targets, email_col)

                    if result.get("success"):
                        st.success(f"✅ Sent to {result['sent']} customers successfully!")

                        if result.get("failed", 0) > 0:
                            with st.expander(f"⚠️ {result['failed']} Failed Emails"):
                                for detail in result.get("details", []):
                                    st.text(detail)

                        campaign.log_campaign(result, target_query)
                    else:
                        error_msg = result.get("error", "Unknown error occurred")
                        st.error(f"❌ Failed to send emails: {error_msg}")


def render_call_campaign(df, model):
    """Render the Automated Call Campaign interface"""
    with st.container():
        st.markdown("### 📞 Customer Reminder Call Campaign")

        st.info(
            "📢 This campaign will automatically call customers using Twilio's voice feature "
            "and deliver a default reminder message."
        )

        reminder_message = (
            "Hello! This is a friendly reminder from ChurnGuard AI. "
            "We noticed you haven't engaged recently. "
            "We value your time and loyalty — please check your email or messages for a special offer. "
            "Thank you and have a great day!"
        )

        st.success("✅ Default Reminder Message:")
        st.write(f"🗣️ *{reminder_message}*")

        st.markdown("#### 🎯 Select Target Customers")
        target_query = st.text_input(
            "Enter Targeting Condition",
            placeholder="e.g., churn_probability > 0.8",
            key="call_target"
        )

        phone_col = "PhoneNo"
        if phone_col not in df.columns:
            st.error("❌ The dataset must include a 'PhoneNo' column.")
            return

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("🔍 Preview Customers", key="call_preview_btn", use_container_width=True):
                if not target_query:
                    st.warning("⚠️ Please enter a targeting condition.")
                    return

                try:
                    query_gen = QueryGenerator(model)
                    code, _ = query_gen.generate_query(target_query, df)
                    executor = SafeExecutor(model)
                    result = executor.safe_eval(code, df)
                    if isinstance(result, pd.Series):
                        result = df[result]
                    st.session_state.call_targets = result

                    st.success(f"✅ Found {len(result)} target customers.")
                    with st.expander("📋 View Target List"):
                        st.dataframe(result[[phone_col]].head(20))

                except Exception as e:
                    st.error(f"❌ Query Error: {e}")

        with col2:
            if st.button("📞 Start Reminder Calls", type="primary", key="call_send_btn", use_container_width=True):
                if "call_targets" not in st.session_state:
                    st.warning("⚠️ Please preview the target customers first.")
                    return

                with st.spinner("📞 Placing reminder calls... Please wait ⏳"):
                    config = Config()
                    campaign = VoiceCampaign(
                        config.TWILIO_ACCOUNT_SID,
                        config.TWILIO_AUTH_TOKEN,
                        config.TWILIO_PHONE_NUMBER
                    )
                    result = campaign.send(st.session_state.call_targets, phone_col, reminder_message)

                    if result["success"]:
                        st.success(f"✅ Calls successfully placed to {result['sent']} customers.")

                        if result.get("failed", 0) > 0:
                            with st.expander("⚠️ Failed Calls"):
                                for d in result["details"]:
                                    st.text(d)

                        campaign.log_campaign(result, target_query)
                    else:
                        st.error(f"❌ Call campaign failed: {result.get('error', 'Unknown error')}")