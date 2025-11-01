import re
import os
import logging
import pandas as pd
import streamlit as st
from twilio.rest import Client
from core.secrets import get_secret

logger = logging.getLogger(__name__)


def send_sms_campaign(targets_df, phone_col, name_col=None):
    try:
        account_sid = get_secret("TWILIO_ACCOUNT_SID")
        auth_token = get_secret("TWILIO_AUTH_TOKEN")
        from_phone = get_secret("TWILIO_PHONE_NUMBER")
        if not all([account_sid, auth_token, from_phone]):
            logger.error("❌ Missing Twilio credentials.")
            return {"success": False, "sent": 0, "failed": 0, "error": "Missing Twilio credentials in .env file"}
        client = Client(account_sid, auth_token)
        sent_count = 0
        failed_count = 0
        failed_details = []
        default_message = "🎁 Hi! We miss you! As a valued customer, here's an EXCLUSIVE 30% OFF just for you. Use code: COMEBACK30. Valid for 48 hours only!"
        for _, row in targets_df.iterrows():
            try:
                message = default_message
                if name_col and name_col in targets_df.columns:
                    name = str(row.get(name_col, "Customer"))
                    message = message.replace("Hi!", f"Hi {name}!")
                phone = str(row.get(phone_col, "")).strip().replace(" ", "").replace("-", "")
                if phone.startswith("+91"):
                    phone = phone[3:]
                if not re.fullmatch(r"\d{10}", phone):
                    logger.warning(f"⚠️ Skipping invalid phone number: {phone}")
                    failed_count += 1
                    failed_details.append(f"Invalid phone: {phone}")
                    continue
                message_obj = client.messages.create(body=message, from_=from_phone, to=f"+91{phone}")
                logger.info(f"✅ Sent to {phone} (SID: {message_obj.sid})")
                sent_count += 1
            except Exception as e:
                failed_count += 1
                failed_details.append(f"{phone}: {str(e)}")
                logger.error(f"❌ Failed to send to {phone}: {e}")
        return {"success": True, "sent": sent_count, "failed": failed_count, "details": failed_details[:10]}
    except Exception as e:
        logger.critical(f"❌ Campaign failed: {e}")
        return {"success": False, "sent": 0, "failed": len(targets_df), "error": str(e)}


def render_sms_campaign(df, model):
    with st.container():
        st.markdown("#### 📱 SMS Campaign")
        st.info("📝 **Default Message:** 🎁 Hi! We miss you! As a valued customer, here's an EXCLUSIVE 30% OFF just for you. Use code: COMEBACK30. Valid for 48 hours only!")
        target_query = st.text_input("🎯 Target Customers (natural language)", placeholder="e.g., customers named 'Rahul' with tenure > 6 months", key="sms_target")

        phone_col = "PhoneNo"
        name_col = "Name"

        col1, col2, _ = st.columns([1, 1, 2])
        with col1:
            if st.button("🔍 Preview (DB)", key="sms_preview_btn", width='stretch'):
                if not target_query:
                    st.warning("Enter target criteria")
                else:
                    try:
                        from db.turso import (
                            get_turso_client,
                            get_table_schema_sql,
                            generate_select_sql_from_prompt,
                            execute_select,
                            close_client,
                        )
                        client = get_turso_client()
                        if not client:
                            st.error("DB client unavailable")
                            return
                        table_name = st.session_state.get("turso_table")
                        if not table_name:
                            st.error("No synced table. Upload and sync data first.")
                            close_client(client)
                            return
                        schema_sql = get_table_schema_sql(client, table_name)
                        if not schema_sql:
                            st.error("Table schema not found.")
                            close_client(client)
                            return
                        # Encourage phone/name selection by mentioning columns in prompt
                        enriched_prompt = f"{target_query}. Return `{phone_col}` and `{name_col}` columns if relevant."
                        sql = generate_select_sql_from_prompt(enriched_prompt, table_name, schema_sql, model)
                        rows, columns = execute_select(client, sql)
                        close_client(client)
                        if not rows:
                            st.info("No matching customers.")
                            return
                        result_df = pd.DataFrame(rows, columns=columns if columns else None)
                        missing = [c for c in [phone_col] if c not in result_df.columns]
                        if missing:
                            st.error(f"Results missing required column(s): {', '.join(missing)}")
                            return
                        st.session_state.sms_targets = result_df
                        st.success(f"✅ Found {len(result_df)} targets (via DB).")
                        with st.expander("View Targets"):
                            st.dataframe(result_df[[phone_col]].head(20), width='stretch')
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col2:
            if st.button("📲 Send SMS", type="primary", key="sms_send_btn", width='stretch'):
                if "sms_targets" not in st.session_state:
                    st.warning("Preview targets first")
                else:
                    with st.spinner("Sending..."):
                        logger.info("📲 Sending SMS campaign")
                        result = send_sms_campaign(st.session_state.sms_targets, phone_col, name_col)
                        if result["success"]:
                            st.success(f"✅ Sent to {result['sent']} customers!")
                            if result.get('details') and result['failed'] > 0:
                                with st.expander(f"⚠️ View {result['failed']} Failed Messages"):
                                    for detail in result['details']:
                                        st.text(detail)
                            if "campaign_logs" not in st.session_state:
                                st.session_state.campaign_logs = []
                            st.session_state.campaign_logs.append({
                                "time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "type": "SMS",
                                "targets": len(st.session_state.sms_targets),
                                "sent": result['sent'],
                                "failed": result['failed'],
                                "status": "✅ Success",
                                "query": target_query
                            })
                        else:
                            st.error(f"Failed: {result.get('error', 'Unknown error')}")


