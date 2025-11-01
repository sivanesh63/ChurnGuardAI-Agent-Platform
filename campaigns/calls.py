import re
import os
import json
import time
import logging
import pandas as pd
import streamlit as st
from twilio.rest import Client
from datetime import datetime
from core.call_script_generator import generate_call_script
from core.secrets import get_secret

logger = logging.getLogger(__name__)


def _create_call_twiml(greeting: str, feedback_question: str) -> str:
    """
    Create TwiML for call with greeting, feedback question, recording, and transcription.
    Twilio will transcribe the recording automatically via API.
    """
    # Escape XML special characters in text
    def escape_xml(text):
        return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))
    
    greeting_escaped = escape_xml(greeting)
    question_escaped = escape_xml(feedback_question)
    
    # Build TwiML with Say and Record (transcription happens automatically via Twilio API)
    twiml = f'''<Response>
    <Say voice="alice">{greeting_escaped}</Say>
    <Pause length="2"/>
    <Say voice="alice">{question_escaped}</Say>
    <Pause length="1"/>
    <Say voice="alice">Please share your feedback after the beep. You have up to 30 seconds.</Say>
    <Record maxLength="30" transcribe="true" />
    <Say voice="alice">Thank you for your valuable feedback. Have a wonderful day!</Say>
</Response>'''
    return twiml


def _detect_name_column(df):
    """
    Auto-detect customer name column from common column names.
    Returns the first matching column name or None.
    """
    common_name_columns = [
        "CustomerName", "Name", "Customer Name", "FullName", "Full Name",
        "ContactName", "Contact Name", "ClientName", "Client Name",
        "FirstName", "First Name", "LastName", "Last Name"
    ]
    for col in common_name_columns:
        if col in df.columns:
            logger.info(f"✅ Auto-detected name column: {col}")
            return col
    logger.info("ℹ️ No name column detected, personalization will be limited")
    return None


def _normalize_phone_number(phone_str: str) -> tuple:
    """
    Normalize phone number to E.164 format (with country code).
    Supports various input formats:
    - +1234567890 (already in E.164)
    - +91 1234567890 (with spaces/dashes)
    - 911234567890 (without +)
    - 00911234567890 (with 00 prefix)
    - 1234567890 (assumes it might be missing country code)
    
    Returns:
        tuple: (normalized_phone: str, is_valid: bool, error_message: str)
    """
    if not phone_str:
        return ("", False, "Empty phone number")
    
    # Convert to string and remove all spaces, dashes, parentheses, dots
    phone = re.sub(r'[\s\-\(\)\.]', '', str(phone_str))
    
    if not phone:
        return ("", False, "Empty after cleaning")
    
    # If already in E.164 format (starts with +), validate and return
    if phone.startswith("+"):
        # Remove + and validate it contains only digits
        digits = phone[1:]
        if digits and digits.isdigit() and len(digits) >= 7 and len(digits) <= 15:
            logger.info(f"✅ Phone already in E.164 format: {phone}")
            return (phone, True, "")
        else:
            return ("", False, f"Invalid E.164 format: {phone}")
    
    # Handle 00 prefix (international dialing code, remove it)
    if phone.startswith("00"):
        phone = "+" + phone[2:]
        digits = phone[1:]
        if digits and digits.isdigit() and len(digits) >= 7 and len(digits) <= 15:
            logger.info(f"✅ Converted 00 prefix to E.164: {phone}")
            return (phone, True, "")
        else:
            return ("", False, f"Invalid format after 00 removal: {phone}")
    
    # If it starts with country code digits (no +), try to add +
    # Common patterns: starts with 1-3 digits (country code) followed by 7-14 digits (phone)
    # This is a heuristic - if it's 10-15 digits, assume it has country code
    if phone.isdigit():
        if len(phone) >= 10 and len(phone) <= 15:
            # Add + prefix
            normalized = "+" + phone
            logger.info(f"✅ Added + prefix to phone: {normalized}")
            return (normalized, True, "")
        elif len(phone) >= 7 and len(phone) < 10:
            # Too short, might be missing country code
            return ("", False, f"Phone too short, possibly missing country code: {phone}")
        else:
            return ("", False, f"Invalid phone length: {len(phone)} digits")
    
    # Contains non-digit characters (excluding + which we already handled)
    return ("", False, f"Contains invalid characters: {phone_str}")


def _validate_phone_for_twilio(phone: str) -> bool:
    """
    Validate phone number format for Twilio.
    Twilio requires E.164 format: +[country code][number]
    """
    if not phone or not phone.startswith("+"):
        return False
    digits = phone[1:]
    return digits.isdigit() and len(digits) >= 7 and len(digits) <= 15


def send_call_campaign(targets_df, phone_col, name_col=None, model=None):
    """
    Send LLM-powered call campaign with recording and transcription.
    Each call uses a personalized script generated by LLM.
    """
    try:
        account_sid = get_secret("TWILIO_ACCOUNT_SID")
        auth_token = get_secret("TWILIO_AUTH_TOKEN")
        from_phone = get_secret("TWILIO_PHONE_NUMBER")
        if not all([account_sid, auth_token, from_phone]):
            logger.error("❌ Missing Twilio credentials in .env file")
            return {"success": False, "sent": 0, "failed": 0, "error": "Missing Twilio credentials"}
        
        if not model:
            logger.warning("⚠️ No LLM model provided, using default script")
        
        client = Client(account_sid, auth_token)
        sent_count, failed_count = 0, 0
        failed_details = []
        call_details = []
        
        for _, row in targets_df.iterrows():
            try:
                phone_raw = row.get(phone_col, "")
                if pd.isna(phone_raw):
                    failed_count += 1
                    failed_details.append(f"Empty phone number in row")
                    continue
                
                # Normalize phone number to E.164 format (supports all country codes)
                normalized_phone, is_valid, error_msg = _normalize_phone_number(phone_raw)
                
                if not is_valid:
                    failed_count += 1
                    failed_details.append(f"Invalid phone '{phone_raw}': {error_msg}")
                    logger.warning(f"⚠️ Invalid phone format: {phone_raw} - {error_msg}")
                    continue
                
                # Validate for Twilio
                if not _validate_phone_for_twilio(normalized_phone):
                    failed_count += 1
                    failed_details.append(f"Invalid Twilio format: {normalized_phone}")
                    logger.warning(f"⚠️ Phone not in Twilio E.164 format: {normalized_phone}")
                    continue
                
                # Generate LLM call script (standard greeting, no personalization)
                script = generate_call_script(model=model)
                logger.info(f"📝 Generated script for {normalized_phone}: {script.get('full_script', 'N/A')[:50]}...")
                
                # Create TwiML with recording and transcription
                twiml = _create_call_twiml(
                    script["greeting"],
                    script["feedback_question"]
                )
                
                # Place call with recording and transcription enabled (transcription via API)
                # normalized_phone is already in E.164 format (e.g., +1234567890, +911234567890, +441234567890)
                call = client.calls.create(
                    twiml=twiml,
                    to=normalized_phone,  # Use normalized phone directly (already has country code)
                    from_=from_phone,
                    record=True  # Enable call recording (transcription handled automatically)
                )
                
                logger.info(f"📞 Call placed to {normalized_phone} (SID: {call.sid})")
                call_details.append({
                    "phone": normalized_phone,
                    "sid": call.sid,
                    "status": call.status,
                    "script": script["full_script"],
                    "greeting": script["greeting"],
                    "feedback_question": script["feedback_question"]
                })
                sent_count += 1
            except Exception as e:
                failed_count += 1
                phone_display = str(row.get(phone_col, "Unknown")) if phone_col else "Unknown"
                failed_details.append(f"{phone_display}: {e}")
                logger.error(f"❌ Failed to call {phone_display}: {e}")
        
        result = {
            "success": True,
            "sent": sent_count,
            "failed": failed_count,
            "details": failed_details[:10],
            "call_details": call_details
        }
        logger.info(f"✅ Call campaign completed: {sent_count} sent, {failed_count} failed")
        return result
    except Exception as e:
        logger.critical(f"❌ Call campaign failed: {e}")
        return {"success": False, "sent": 0, "failed": len(targets_df), "error": str(e)}


def fetch_transcripts_from_twilio(call_sids: list = None, limit: int = 20):
    """
    Fetch transcripts directly from Twilio API (no webhook needed).
    Can fetch by specific call SIDs or get recent transcripts.
    """
    try:
        account_sid = get_secret("TWILIO_ACCOUNT_SID")
        auth_token = get_secret("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            logger.error("❌ Missing Twilio credentials for fetching transcripts")
            return []
        
        client = Client(account_sid, auth_token)
        transcripts = []
        
        if call_sids:
            # Fetch transcripts for specific call SIDs
            logger.info(f"🔍 Fetching transcripts for {len(call_sids)} call SIDs...")
            for call_sid in call_sids:
                try:
                    call = client.calls(call_sid).fetch()
                    logger.info(f"📞 Processing call {call_sid} (Status: {call.status})")
                    
                    # Get recordings for this call
                    recordings = client.calls(call_sid).recordings.list()
                    logger.info(f"📼 Found {len(recordings)} recording(s) for call {call_sid}")
                    
                    for recording in recordings:
                        try:
                            # Fetch transcriptions for this specific recording
                            # Twilio stores transcriptions linked to recordings
                            trans_list = client.recordings(recording.sid).transcriptions.list()
                            
                            if not trans_list:
                                # Try fetching all transcriptions and match by recording_sid
                                logger.info(f"⚠️ No transcriptions directly linked, searching all transcriptions...")
                                all_transcriptions = client.transcriptions.list(limit=100)
                                trans_list = [t for t in all_transcriptions if hasattr(t, 'recording_sid') and t.recording_sid == recording.sid]
                            
                            for trans in trans_list:
                                if trans.status == "completed":
                                    # Get transcription text
                                    try:
                                        trans_text = trans.transcription_text or ""
                                        if not trans_text and hasattr(trans, 'fetch'):
                                            trans_full = trans.fetch()
                                            trans_text = trans_full.transcription_text or ""
                                    except Exception as e:
                                        logger.warning(f"Could not get transcription text: {e}")
                                        trans_text = ""
                                    
                                    recording_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                                    
                                    # Get date
                                    try:
                                        date_created = getattr(recording, 'date_created', None) or getattr(trans, 'date_created', None)
                                        if date_created:
                                            date_str = date_created.isoformat() if hasattr(date_created, 'isoformat') else str(date_created)
                                        else:
                                            date_str = datetime.now().isoformat()
                                    except:
                                        date_str = datetime.now().isoformat()
                                    
                                    transcript_data = {
                                        "timestamp": date_str,
                                        "call_sid": call_sid,
                                        "transcription_sid": trans.sid,
                                        "recording_sid": recording.sid,
                                        "recording_url": recording_url,
                                        "transcript": trans_text,
                                        "phone": getattr(call, 'to_formatted', None) or str(getattr(call, 'to', 'Unknown')),
                                        "status": trans.status,
                                        "language": getattr(trans, 'language', 'en-US'),
                                        "duration": str(call.duration) if hasattr(call, 'duration') and call.duration else ""
                                    }
                                    transcripts.append(transcript_data)
                                    logger.info(f"✅ Found completed transcript for call {call_sid}, recording {recording.sid}")
                                else:
                                    logger.info(f"⏳ Transcription {trans.sid} status: {trans.status}")
                        except Exception as rec_e:
                            logger.warning(f"Error processing recording {recording.sid}: {rec_e}")
                except Exception as e:
                    logger.warning(f"Could not fetch transcript for call {call_sid}: {e}", exc_info=True)
        else:
            # Fetch recent transcriptions (all completed ones)
            logger.info(f"🔍 Fetching recent transcriptions (limit: {limit})...")
            try:
                all_transcriptions = client.transcriptions.list(limit=limit * 2)  # Get more to filter
                logger.info(f"📋 Found {len(all_transcriptions)} total transcriptions")
                
                for trans in all_transcriptions:
                    if trans.status == "completed":
                        # Try to get call info from recording
                        call_sid = "Unknown"
                        phone = "Unknown"
                        duration = ""
                        recording_url = None
                        
                        recording_sid = getattr(trans, 'recording_sid', None)
                        if recording_sid:
                            try:
                                recording = client.recordings(recording_sid).fetch()
                                call_sid = getattr(recording, 'call_sid', 'Unknown')
                                recording_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
                                
                                if call_sid != "Unknown":
                                    try:
                                        call = client.calls(call_sid).fetch()
                                        phone = getattr(call, 'to_formatted', None) or str(getattr(call, 'to', 'Unknown'))
                                        duration = str(call.duration) if hasattr(call, 'duration') and call.duration else ""
                                    except Exception as call_e:
                                        logger.debug(f"Could not fetch call info: {call_e}")
                            except Exception as rec_e:
                                logger.debug(f"Could not fetch recording info: {rec_e}")
                        
                        # Get transcription text
                        try:
                            trans_text = getattr(trans, 'transcription_text', None) or ""
                            if not trans_text:
                                trans_full = trans.fetch()
                                trans_text = getattr(trans_full, 'transcription_text', None) or ""
                        except Exception as e:
                            logger.debug(f"Could not get transcription text: {e}")
                            trans_text = ""
                        
                        # Parse date
                        try:
                            date_created = getattr(trans, 'date_created', None)
                            if date_created:
                                date_str = date_created.isoformat() if hasattr(date_created, 'isoformat') else str(date_created)
                            else:
                                date_str = datetime.now().isoformat()
                        except:
                            date_str = datetime.now().isoformat()
                        
                        transcript_data = {
                            "timestamp": date_str,
                            "call_sid": call_sid,
                            "transcription_sid": trans.sid,
                            "recording_sid": recording_sid,
                            "recording_url": recording_url,
                            "transcript": trans_text,
                            "phone": phone,
                            "status": trans.status,
                            "language": getattr(trans, 'language', 'en-US'),
                            "duration": duration
                        }
                        transcripts.append(transcript_data)
                        logger.info(f"✅ Added transcript {trans.sid} for call {call_sid}")
                        
                        # Limit results
                        if len(transcripts) >= limit:
                            break
            except Exception as e:
                logger.error(f"Error fetching recent transcriptions: {e}", exc_info=True)
        
        logger.info(f"✅ Fetched {len(transcripts)} transcripts from Twilio API")
        return transcripts
    except Exception as e:
        logger.error(f"❌ Error fetching transcripts from Twilio: {e}", exc_info=True)
        return []


def render_call_campaign(df, model):
    with st.container():
        st.markdown("### 📞 LLM-Powered Customer Feedback Call Campaign")
        st.info("🤖 This campaign uses AI to generate personalized greetings and feedback questions. Calls are recorded and transcribed via Twilio API.")
        st.success("✅ Transcripts will be fetched directly from Twilio API - no setup needed!")
        
        st.markdown("#### 🎯 Select Target Customers")
        target_query = st.text_input("Enter Targeting Condition (natural language)", placeholder="e.g., customers named 'Rahul' with PhoneNo present", key="call_target")
        phone_col = "PhoneNo"
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔍 Preview Customers (DB)", key="call_preview_btn", width='stretch'):
                if not target_query:
                    st.warning("⚠️ Please enter a targeting condition.")
                    return
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
                    enriched_prompt = f"{target_query}. Return `{phone_col}` column if relevant."
                    sql = generate_select_sql_from_prompt(enriched_prompt, table_name, schema_sql, model)
                    rows, columns = execute_select(client, sql)
                    close_client(client)
                    if not rows:
                        st.info("No matching customers.")
                        return
                    result_df = pd.DataFrame(rows, columns=columns if columns else None)
                    if phone_col not in result_df.columns:
                        st.error("Results missing required column: PhoneNo")
                        return
                    st.session_state.call_targets = result_df
                    st.success(f"✅ Found {len(result_df)} target customers.")
                    with st.expander("📋 View Target List"):
                        st.dataframe(result_df[[phone_col]].head(20), width='stretch')
                except Exception as e:
                    st.error(f"❌ Query Error: {e}")
        with col2:
            if st.button("📞 Start Reminder Calls", type="primary", key="call_send_btn", width='stretch'):
                if "call_targets" not in st.session_state:
                    st.warning("⚠️ Please preview the target customers first.")
                    return
                
                with st.spinner("📞 Placing AI-powered calls with recording... Please wait ⏳"):
                    logger.info("📞 Starting LLM-powered call campaign with transcription")
                    # Auto-detect name column in background
                    auto_name_col = _detect_name_column(st.session_state.call_targets)
                    result = send_call_campaign(
                        st.session_state.call_targets,
                        phone_col,
                        name_col=auto_name_col,
                        model=model
                    )
                    if result["success"]:
                        st.success(f"✅ Calls successfully placed to {result['sent']} customers.")
                        
                        # Store call SIDs for later transcript fetching
                        if result.get("call_details"):
                            call_sids = [d["sid"] for d in result["call_details"]]
                            st.session_state.last_call_sids = call_sids
                            
                            # Show generated scripts preview
                            with st.expander("📝 View Generated Call Scripts"):
                                for detail in result["call_details"][:5]:
                                    st.markdown(f"**{detail['phone']}** (SID: `{detail['sid']}`)")
                                    st.text(f"Greeting: {detail['greeting']}")
                                    st.text(f"Question: {detail['feedback_question']}")
                                    st.divider()
                        
                        if result.get("failed", 0) > 0:
                            with st.expander("⚠️ Failed Calls"):
                                for d in result["details"]:
                                    st.text(d)
                        
                        if "campaign_logs" not in st.session_state:
                            st.session_state.campaign_logs = []
                        st.session_state.campaign_logs.append({
                            "time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "Call (AI)",
                            "targets": len(st.session_state.call_targets),
                            "sent": result["sent"],
                            "failed": result["failed"],
                            "status": "✅ Success",
                            "query": target_query
                        })
                        
                        st.info("💡 Use the 'Fetch Transcripts' button below to retrieve transcripts after calls complete (wait 1-2 minutes for transcription).")
                    else:
                        st.error(f"❌ Call campaign failed: {result.get('error', 'Unknown error')}")
        
        # Fetch transcripts buttons
        st.markdown("---")
        st.markdown("#### 📋 Fetch Call Transcripts")
        col_fetch1, col_fetch2 = st.columns([1, 1])
        with col_fetch1:
            if st.button("🔄 Fetch Recent Transcripts", key="fetch_transcripts_btn"):
                with st.spinner("⏳ Fetching transcripts from Twilio API..."):
                    # Wait a bit for transcriptions to process
                    time.sleep(2)
                    try:
                        # If we have last campaign SIDs, only fetch those; otherwise fetch recent
                        if "last_call_sids" in st.session_state and st.session_state.last_call_sids:
                            transcripts = fetch_transcripts_from_twilio(call_sids=st.session_state.last_call_sids)
                        else:
                            transcripts = fetch_transcripts_from_twilio(limit=20)
                        
                        if transcripts:
                            # Replace transcripts (only show last campaign)
                            st.session_state.call_transcripts = transcripts
                            st.success(f"✅ Fetched {len(transcripts)} transcript(s)!")
                        else:
                            st.warning("⚠️ No transcripts found. Possible reasons:\n- Calls haven't completed yet (wait 1-2 minutes)\n- Transcription is still processing\n- No calls were recorded\n\nCheck the logs for more details.")
                    except Exception as e:
                        st.error(f"❌ Error fetching transcripts: {str(e)}")
                        logger.error(f"Error in UI fetch: {e}", exc_info=True)
        
        with col_fetch2:
            if st.button("🔄 Fetch Transcripts for Last Campaign", key="fetch_last_campaign_btn"):
                if "last_call_sids" in st.session_state and st.session_state.last_call_sids:
                    with st.spinner("⏳ Fetching transcripts for last campaign calls..."):
                        time.sleep(2)
                        try:
                            transcripts = fetch_transcripts_from_twilio(call_sids=st.session_state.last_call_sids)
                            if transcripts:
                                # Replace transcripts in session state (only keep last campaign)
                                st.session_state.call_transcripts = transcripts
                                st.success(f"✅ Fetched {len(transcripts)} transcript(s) for last campaign!")
                            else:
                                st.warning(f"⚠️ No transcripts found for {len(st.session_state.last_call_sids)} call(s).\n- Transcription may still be processing (wait 1-2 minutes)\n- Check if recordings exist for these calls\n- Verify transcription is enabled in TwiML")
                        except Exception as e:
                            st.error(f"❌ Error fetching transcripts: {str(e)}")
                            logger.error(f"Error in UI fetch for last campaign: {e}", exc_info=True)
                else:
                    st.warning("⚠️ No recent campaign calls found. Start a campaign first.")
        
        # Show stored transcripts if available
        if "call_transcripts" in st.session_state and st.session_state.call_transcripts:
            st.markdown("---")
            st.markdown("#### 📋 Call Transcripts")
            
            # Filter transcripts to only show last campaign if available
            transcripts_to_show = []
            if "last_call_sids" in st.session_state and st.session_state.last_call_sids:
                # Filter to only show transcripts from the last campaign
                last_campaign_sids = set(st.session_state.last_call_sids)
                for t in st.session_state.call_transcripts:
                    call_sid = t.get("call_sid", "")
                    if call_sid in last_campaign_sids:
                        transcripts_to_show.append(t)
                
                if not transcripts_to_show:
                    # Fallback: show all if no matches (maybe transcripts from different campaign format)
                    logger.info("No transcripts matched last campaign SIDs, showing all transcripts")
                    transcripts_to_show = st.session_state.call_transcripts
            else:
                # No last campaign info, show all
                transcripts_to_show = st.session_state.call_transcripts
            
            # Deduplicate by transcription_sid
            seen = set()
            unique_transcripts = []
            for t in transcripts_to_show:
                sid = t.get("transcription_sid") or t.get("call_sid")
                if sid and sid not in seen:
                    seen.add(sid)
                    unique_transcripts.append(t)
            
            if unique_transcripts:
                st.info(f"📊 Showing {len(unique_transcripts)} transcript(s) from last campaign")
                for transcript in unique_transcripts[-10:]:  # Show last 10
                    phone_display = transcript.get('phone', 'Unknown')
                    timestamp_display = transcript.get('timestamp', 'N/A')
                    if isinstance(timestamp_display, str) and len(timestamp_display) > 19:
                        timestamp_display = timestamp_display[:19]
                    with st.expander(f"📞 {phone_display} - {timestamp_display}"):
                        if transcript.get("transcript"):
                            st.markdown(f"**Transcript:** {transcript['transcript']}")
                        st.json(transcript)
            else:
                st.info("ℹ️ No transcripts to display. Wait 1-2 minutes after calls complete and try fetching again.")


