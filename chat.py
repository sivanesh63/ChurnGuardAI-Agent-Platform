import pandas as pd
import streamlit as st
import logging
from core.llm import execute_and_summarize

logger = logging.getLogger(__name__)


def render_chat_history():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "code" in message:
                with st.expander("🔍 Code"):
                    st.code(message["code"], language="python")
            # Show actual data if user requested it
            if message.get("show_data") and isinstance(message.get("result_data"), pd.DataFrame):
                result_df = message["result_data"]
                if not result_df.empty:
                    with st.expander("📊 View Data"):
                        st.dataframe(result_df, width='stretch')
            # Do not auto-render raw dataframes; show compact metadata if present
            if message.get("result_meta"):
                st.caption(message["result_meta"]) 


def _is_data_availability_query(prompt: str) -> bool:
    if not prompt:
        return False
    p = prompt.lower()
    keywords = [
        "how many", "count", "total", "available", "exists", "present",
        "show me", "display", "list", "see", "view", "get data", "fetch data"
    ]
    return any(kw in p for kw in keywords)


def _wants_actual_data(prompt: str) -> bool:
    if not prompt:
        return False
    p = prompt.lower()
    keywords = ["show", "display", "list", "see", "view", "get", "fetch", "give me", "give me the"]
    return any(kw in p for kw in keywords)


def _is_general_question(prompt: str) -> bool:
    if not prompt:
        return True
    p = prompt.lower()
    # Heuristic: general knowledge or open questions that don't mention table/data concepts
    data_terms = [
        "data", "dataset", "table", "column", "row", "filter", "query", "sql", "pandas",
        "select ", "where ", "like ", "limit ", "from ", "join ", "group by",
    ]
    # If none of the data terms appear, treat as general question
    return not any(term in p for term in data_terms)


def _answer_general_question(prompt: str, model):
    sys = (
        "You are a helpful assistant. Provide a concise, accurate answer in 2-4 sentences. "
        "Avoid code unless explicitly requested."
    )
    resp = model.generate_content(f"{sys}\n\nUser: {prompt}")
    text = (resp.text or "").strip()
    if not text:
        text = "I'm not sure yet, but I can look it up if you provide more details."
    return text


def handle_user_query(prompt: str, model):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("🤔 Analyzing..."):
            response = None
            client = None
            show_data = _wants_actual_data(prompt)
            try:
                # Check if we have DB access and data first
                try:
                    from db.turso import (
                        get_turso_client,
                        get_table_schema_sql,
                        generate_select_sql_from_prompt,
                        execute_select,
                        close_client,
                    )
                except Exception as _imp_err:
                    get_turso_client = None
                    get_table_schema_sql = None
                    generate_select_sql_from_prompt = None
                    execute_select = None
                    close_client = None

                client = get_turso_client() if get_turso_client else None
                table_name = st.session_state.get("turso_table")
                has_db = client and table_name

                # If DB available, prioritize DB queries for any data-related questions (even general-sounding)
                if has_db and ("df" in st.session_state or not _is_general_question(prompt) or _is_data_availability_query(prompt)):
                    schema_sql = get_table_schema_sql(client, table_name)
                    if schema_sql:
                        logger.info("🔎 Answering via Turso DB path")
                        sql_error = None
                        sql = None
                        # up to 2 attempts: initial + with error feedback
                        for attempt in range(2):
                            sql = generate_select_sql_from_prompt(prompt, table_name, schema_sql, model, prior_error=sql_error)
                            try:
                                rows, columns = execute_select(client, sql)
                                df_ans = pd.DataFrame(rows, columns=columns if columns else None)
                                preview = df_ans.head(10).to_string() if not df_ans.empty else "<no rows>"
                                meta = f"Matched {len(df_ans)} rows across {len(df_ans.columns)} columns."
                                
                                # Build context-aware summary prompt
                                if _is_data_availability_query(prompt):
                                    summary_prompt = (
                                        f"User asked about data availability: {prompt}\n"
                                        f"SQL executed: {sql}\n"
                                        f"Result: {len(df_ans)} rows found.\n"
                                        f"Answer concisely about what data exists in the database."
                                    )
                                elif show_data:
                                    # Check if this is a churn-related query
                                    is_churn_related = any(keyword in prompt.lower() for keyword in [
                                        "churn", "high risk", "high-risk", "at risk", "risk customer",
                                        "churn risk", "likely to churn", "retention", "losing customer"
                                    ])
                                    churn_context = ""
                                    if is_churn_related:
                                        churn_context = "Note: This query uses predictive churn analysis based on data characteristics to identify high-risk customers. "
                                    summary_prompt = (
                                        f"User asked to see data: {prompt}\n"
                                        f"{churn_context}SQL executed: {sql}\n"
                                        f"Preview:\n{preview}\n"
                                        f"Provide a brief 1-sentence description. The actual data will be shown separately."
                                    )
                                else:
                                    # Check if this is a churn-related query
                                    is_churn_related = any(keyword in prompt.lower() for keyword in [
                                        "churn", "high risk", "high-risk", "at risk", "risk customer",
                                        "churn risk", "likely to churn", "retention", "losing customer"
                                    ])
                                    churn_context = ""
                                    if is_churn_related:
                                        churn_context = "Note: This query uses predictive churn analysis based on data characteristics (e.g., low engagement, payment issues, support tickets) to identify high-risk customers, since no explicit churn column exists in the dataset. "
                                    summary_prompt = (
                                        f"Answer succinctly (2-4 sentences) based strictly on the query result.\n"
                                        f"{churn_context}User asked: {prompt}\nSQL executed: {sql}\nPreview:\n{preview}"
                                    )
                                
                                summary = model.generate_content(summary_prompt).text
                                response = {
                                    "success": True,
                                    "code": sql,
                                    "result": df_ans,
                                    "summary": summary,
                                    "meta": meta,
                                    "show_data": show_data and not df_ans.empty
                                }
                                break
                            except Exception as exec_err:
                                sql_error = str(exec_err)
                                logger.warning(f"DB execution failed, retrying SQL generation with error hint: {sql_error}")
                        if response is None and "df" in st.session_state:
                            logger.info("🔁 Falling back to pandas path after DB retries failed")
                            response = execute_and_summarize(prompt, st.session_state.df, model)
                    else:
                        if "df" in st.session_state:
                            logger.info("🔁 Falling back to pandas path (no schema)")
                            response = execute_and_summarize(prompt, st.session_state.df, model)
                        else:
                            summary = _answer_general_question(prompt, model)
                            response = {"success": True, "code": None, "result": None, "summary": summary, "meta": None}
                elif "df" in st.session_state and not _is_general_question(prompt):
                    # Fallback to pandas if DB unavailable but data exists
                    logger.info("🔁 Using pandas path (no DB)")
                    response = execute_and_summarize(prompt, st.session_state.df, model)
                else:
                    # Pure general question, no data context
                    summary = _answer_general_question(prompt, model)
                    response = {"success": True, "code": None, "result": None, "summary": summary, "meta": None}
            except Exception as _db_e:
                logger.warning(f"DB path failed, using LLM generic answer: {_db_e}")
                summary = _answer_general_question(prompt, model)
                response = {"success": True, "code": None, "result": None, "summary": summary, "meta": None}
            finally:
                # Close DB client when used
                try:
                    if client and close_client:
                        close_client(client)
                except Exception:
                    pass
        if response["success"]:
            st.markdown(response["summary"])
            if response.get("code"):
                with st.expander("🔍 View SQL"):
                    st.code(response["code"], language="sql" if "SELECT" in str(response["code"]) else "python")
            # Show actual data if user requested it
            if response.get("show_data") and isinstance(response.get("result"), pd.DataFrame):
                result_df = response["result"]
                if not result_df.empty:
                    with st.expander("📊 View Data"):
                        st.dataframe(result_df, width='stretch')
            meta = response.get("meta")
            if meta:
                st.caption(meta)
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["summary"],
                "code": response.get("code"),
                "result_meta": meta,
                "show_data": response.get("show_data", False),
                "result_data": response.get("result") if response.get("show_data") else None,
            })
        else:
            st.error(response["error"])
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ {response['error']}"
            })


