import os
import streamlit as st
import pandas as pd
import google.generativeai as genai
from core.secrets import get_secret, validate_secrets

@st.cache_data
def preprocess_csv(uploaded_file) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    # Try numeric conversion safely without deprecated errors="ignore"
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                # keep as object if conversion fails
                pass

    # Fill missing numeric values without chained assignment
    for col in df.select_dtypes(include=["number"]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    # Fill missing object values without chained assignment
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna("")

    return df


def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Setup")
        api_key = get_secret("GEMINI_API_KEY")
        if not api_key:
            st.error("❌ GEMINI_API_KEY missing")
            st.info("💡 Add to Streamlit secrets or .env file")
            with st.expander("📋 How to configure"):
                st.markdown("""
                **Streamlit Cloud:**
                1. Go to app settings
                2. Open "Secrets" section
                3. Add `GEMINI_API_KEY` with your key
                
                **Local Development:**
                - Add to `.env` file or `.streamlit/secrets.toml`
                """)
            return None
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            st.success("✅ API Ready")
        except Exception as e:
            st.error(f"❌ {e}")
            return None

        st.divider()
        uploaded_file = st.file_uploader("📂 Upload CSV", type=["csv"])
        if uploaded_file:
            df = preprocess_csv(uploaded_file)
            st.session_state.df = df
            st.session_state.model = model
            st.success(f"✅ {len(df)} rows loaded")
            with st.expander("📋 Preview"):
                st.dataframe(df.head(10), width='stretch')

            # Build a stable source signature for this upload
            try:
                filename = getattr(uploaded_file, 'name', '') or ''
            except Exception:
                filename = ''
            source_sig = f"{filename}:{len(df)}:{','.join(list(df.columns))}"

            # Generate table name only when source changes; otherwise reuse
            new_source = st.session_state.get("turso_source_sig") != source_sig
            if new_source:
                import re as _re
                from datetime import datetime as _dt
                base = "uploaded_data"
                try:
                    name = filename.rsplit('.', 1)[0] if filename else base
                    name = _re.sub(r"[^A-Za-z0-9_]+", "_", name)[:20] or base
                except Exception:
                    name = base
                suffix = _dt.now().strftime("%Y%m%d_%H%M%S")
                st.session_state.turso_table = f"{name}_{suffix}"
                st.session_state.turso_source_sig = source_sig
                st.session_state.turso_synced = False
                st.info(f"📦 Target table: `{st.session_state.turso_table}`")
            else:
                # Reuse previous table for this upload session
                st.info(f"📦 Target table: `{st.session_state.get('turso_table','uploaded_data')}`")

            # One-time DB sync per upload
            if not st.session_state.get("turso_synced"):
                try:
                    from db.turso import (
                        get_turso_client,
                        generate_create_table_sql,
                        create_table_if_needed,
                        batch_insert_dataframe,
                        close_client,
                    )
                    client = get_turso_client()
                except Exception as _imp_err:
                    client = None
                    st.warning(f"⚠️ DB helpers unavailable: {_imp_err}")
                if client:
                    try:
                        with st.spinner("🔄 Syncing to Turso (one-time)..."):
                            create_sql = generate_create_table_sql(df, st.session_state.turso_table, model)
                            ok, err = create_table_if_needed(client, create_sql)
                            if ok:
                                inserted, ierr = batch_insert_dataframe(client, df, st.session_state.turso_table)
                                if ierr:
                                    st.warning(f"⚠️ Insert error after {inserted} rows: {ierr}")
                                else:
                                    st.info(f"🗃️ Synced {inserted} rows to `{st.session_state.turso_table}`")
                                    st.session_state.turso_synced = True
                            else:
                                st.warning(f"⚠️ Table creation failed: {err}")
                    finally:
                        try:
                            close_client(client)
                        except Exception:
                            pass
                else:
                    st.info("ℹ️ Skipping DB sync (client unavailable)")
            else:
                st.info("🗃️ Data already synced to Turso (skipping)")

        st.divider()
        if "messages" in st.session_state and st.session_state.messages:
            if st.button("🗑️ Clear Chat"):
                st.session_state.messages = []
                st.rerun()
        return st.session_state.get("model", None)