import os
import re
import logging
import smtplib
import pandas as pd
import streamlit as st
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_email_campaign(targets_df: pd.DataFrame, email_col: str = None, name_col: str = None):
    EMAIL_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_PASS = os.getenv("EMAIL_HOST_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
    detected_email_col = email_col or "Email"
    if detected_email_col not in targets_df.columns:
        logger.error("❌ Could not find an email column in results")
        return {"success": False, "error": "Email column not found in results"}
    if not EMAIL_USER or not EMAIL_PASS:
        logger.critical("❌ Missing email credentials in .env")
        return {"success": False, "error": "Missing email credentials in .env"}
    sent_count, failed_count = 0, 0
    failed_details = []
    try:
        logger.info(f"📡 Connecting securely to {SMTP_SERVER}:{SMTP_PORT}...")
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            logger.info("✅ Logged into SMTP server successfully")
            email_regex = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
            for _, row in targets_df.iterrows():
                try:
                    email = str(row.get(detected_email_col, "")).strip()
                    if not email or not email_regex.match(email):
                        failed_count += 1
                        failed_details.append(f"Invalid email: {email if email else 'EMPTY'}")
                        logger.warning(f"⚠️ Skipping invalid email: {email if email else 'EMPTY'}")
                        continue
                    name = str(row.get(name_col or "Name", "Valued Customer"))
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = "We Miss You! Exclusive Offer Inside 🎁"
                    msg["From"] = EMAIL_USER
                    msg["To"] = email
                    html_content = f"""
                    <html>
                        <body style="font-family: Arial, sans-serif; color: #333;">
                            <p>Hi {name},</p>
                            <p>We miss you! Get <b>40% OFF</b> using code <b>WELCOME40</b>!</p>
                            <p>Best,<br>Your ChurnGuard Team</p>
                        </body>
                    </html>
                    """
                    msg.attach(MIMEText(html_content, "html"))
                    server.send_message(msg)
                    sent_count += 1
                    logger.info(f"✅ Email sent to {email}")
                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{email if 'email' in locals() else 'N/A'}: {e}")
                    logger.error(f"❌ Failed to send to {email if 'email' in locals() else 'N/A'}: {e}")
        logger.info(f"📊 Campaign complete — Sent: {sent_count}, Failed: {failed_count}")
        return {"success": True, "sent": sent_count, "failed": failed_count, "details": failed_details}
    except Exception as e:
        logger.critical(f"❌ Email campaign failed: {e}")
        return {"success": False, "error": str(e)}


def render_email_campaign(df, model):
    with st.container():
        st.markdown("### 📧 Email Campaign")
        st.info("💌 **Default Email Content:**\n**Subject:** *We Miss You! Exclusive Offer Inside 🎁*\n\n**Body:** Personalized message with customer name and a 40% discount offer.")
        col1, col2 = st.columns([2, 1])
        with col1:
            target_query = st.text_input("🎯 Target Customers (natural language)", placeholder="e.g., customers with Email ending '@gmail.com' and EngagementScore > 50", key="email_target")
        with col2:
            email_col = "Email"
        cols = st.columns([1, 1, 2])
        with cols[0]:
            if st.button("🔍 Preview (DB)", key="email_preview_btn", width='stretch'):
                if not target_query:
                    st.warning("⚠️ Please enter a targeting condition first.")
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
                        enriched_prompt = f"{target_query}. Return `{email_col}` and `Name` columns if relevant."
                        sql = generate_select_sql_from_prompt(enriched_prompt, table_name, schema_sql, model)
                        rows, columns = execute_select(client, sql)
                        close_client(client)
                        if not rows:
                            st.info("No matching customers.")
                            return
                        result_df = pd.DataFrame(rows, columns=columns if columns else None)
                        if email_col not in result_df.columns:
                            st.error("Results missing required column: Email")
                            return
                        st.session_state.email_targets = result_df
                        st.success(f"✅ Found {len(result_df)} target customers (via DB).")
                        with st.expander("📋 View Targeted Email List"):
                            st.dataframe(result_df[[email_col]].head(20), width='stretch')
                    except Exception as e:
                        st.error(f"⚠️ Query Error: {e}")
        with cols[1]:
            if st.button("📨 Send Emails", type="primary", key="email_send_btn", width='stretch'):
                if "email_targets" not in st.session_state:
                    st.warning("⚠️ Please preview the target customers first.")
                    return
                with st.spinner("📤 Sending emails... Please wait ⏳"):
                    logger.info("📤 Sending email campaign")
                    result = send_email_campaign(st.session_state.email_targets, email_col, "Name")
                    if result.get("success"):
                        st.success(f"✅ Sent to {result['sent']} customers successfully!")
                        if result.get("failed", 0) > 0:
                            with st.expander(f"⚠️ {result['failed']} Failed Emails"):
                                for detail in result.get("details", []):
                                    st.text(detail)
                        if "campaign_logs" not in st.session_state:
                            st.session_state.campaign_logs = []
                        st.session_state.campaign_logs.append({
                            "time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "Email",
                            "targets": len(st.session_state.email_targets),
                            "sent": result['sent'],
                            "failed": result['failed'],
                            "status": "✅ Success",
                            "query": target_query
                        })
                    else:
                        st.error(f"❌ Failed to send emails: {result.get('error', 'Unknown error occurred')}")


