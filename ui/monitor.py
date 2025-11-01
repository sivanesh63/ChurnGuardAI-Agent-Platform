import pandas as pd
import streamlit as st
from datetime import datetime

def render_monitor():
    st.subheader("📊 Campaign Monitor & Logs")
    if "campaign_logs" in st.session_state and st.session_state.campaign_logs:
        logs = st.session_state.campaign_logs
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_campaigns = len(logs)
            st.metric("🚀 Total Campaigns", total_campaigns)
        with col2:
            total_sent = sum(log.get("sent", 0) for log in logs)
            st.metric("📤 Total Sent", f"{total_sent:,}")
        with col3:
            sms_campaigns = len([l for l in logs if l.get("type") == "SMS"])
            st.metric("📱 SMS Campaigns", sms_campaigns)
        with col4:
            email_campaigns = len([l for l in logs if l.get("type") == "Email"])
            st.metric("📧 Email Campaigns", email_campaigns)
        st.divider()
        st.markdown("### 📜 Campaign History")
        logs_data = []
        for i, log in enumerate(logs, 1):
            logs_data.append({
                "ID": i,
                "Time": log.get("time", "N/A"),
                "Type": log.get("type", "N/A"),
                "Targets": log.get("targets", log.get("sent", 0)),
                "Sent": log.get("sent", 0),
                "Failed": log.get("failed", 0),
                "Status": log.get("status", "✅ Success"),
                "Query": log.get("query", "N/A")[:50] + "..." if len(log.get("query", "")) > 50 else log.get("query", "N/A")
            })
        logs_df = pd.DataFrame(logs_data)
        col1, col2 = st.columns([1, 3])
        with col1:
            filter_type = st.selectbox("Filter by Type", ["All", "SMS", "Email"], key="log_filter")
        filtered_df = logs_df[logs_df["Type"] == filter_type] if filter_type != "All" else logs_df
        st.dataframe(filtered_df, width='stretch', hide_index=True)
        col1, col2, _ = st.columns([1, 1, 2])
        with col1:
            if st.button("📥 Export Logs"):
                csv = filtered_df.to_csv(index=False)
                st.download_button(label="Download CSV", data=csv, file_name=f"campaign_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv")
        with col2:
            if st.button("🗑️ Clear Logs"):
                if st.session_state.get("confirm_clear"):
                    st.session_state.campaign_logs = []
                    st.session_state.confirm_clear = False
                    st.success("Logs cleared!")
                    st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("Click again to confirm")
        st.divider()
        st.markdown("### 📈 Campaign Performance")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Success Rate")
            total_attempted = sum(log.get("sent", 0) + log.get("failed", 0) for log in logs)
            success_rate = (total_sent / total_attempted * 100) if total_attempted > 0 else 0
            st.progress(success_rate / 100)
            st.metric("Success Rate", f"{success_rate:.1f}%")
        with col2:
            st.markdown("#### Recent Activity")
            recent_logs = logs[-5:]
            for log in reversed(recent_logs):
                status_icon = "✅" if log.get("status") != "Failed" else "❌"
                st.text(f"{status_icon} {log.get('type')} - {log.get('sent', 0)} sent - {log.get('time')}")
        st.divider()
        st.markdown("### 📊 Campaign Breakdown")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### By Type")
            type_counts = {"SMS": sms_campaigns, "Email": email_campaigns}
            for ctype, count in type_counts.items():
                percentage = (count / total_campaigns * 100) if total_campaigns > 0 else 0
                st.write(f"**{ctype}**: {count} ({percentage:.0f}%)")
                st.progress(percentage / 100)
        with col2:
            st.markdown("#### Messages Sent Over Time")
            time_data = {}
            for log in logs:
                date = log.get("time", "").split()[0]
                if date:
                    time_data[date] = time_data.get(date, 0) + log.get("sent", 0)
            if time_data:
                for date, count in sorted(time_data.items())[-7:]:
                    st.write(f"**{date}**: {count:,} messages")
    else:
        st.info("📭 No campaigns logged yet. Launch your first campaign to see monitoring data!")
        st.markdown("""
        ### What you'll see here:
        - 📊 Real-time campaign metrics
        - 📜 Detailed campaign history
        - 📈 Performance analytics
        - 📥 Export logs to CSV
        - 🔍 Filter and search logs
        """)


