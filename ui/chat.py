# ui/chat.py

import streamlit as st
from core.query_generator import QueryGenerator
from core.code_executor import SafeExecutor
import pandas as pd
def render_chat_history():
    """Render chat message history"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "code" in message:
                with st.expander("🔍 Code"):
                    st.code(message["code"], language="python")
            if "result" in message and message["result"] is not None:
                result_str = str(message["result"])
                if len(result_str) > 500:
                    st.info(f"**Result:** {result_str[:500]}...")
                else:
                    st.info(f"**Result:** {message['result']}")


def handle_user_query(prompt: str, model):
    """Handle user query and generate response"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("🤔 Analyzing..."):
            # Generate query
            query_gen = QueryGenerator(model)
            code, _ = query_gen.generate_query(prompt, st.session_state.df)
            
            # Execute query
            executor = SafeExecutor(model)
            response = executor.execute_and_summarize(prompt, st.session_state.df, code)
        
        if response["success"]:
            st.markdown(response["summary"])
            
            with st.expander("🔍 View Code"):
                st.code(response["code"], language="python")
            
            if isinstance(response["result"], (pd.DataFrame, pd.Series)):
                st.dataframe(response["result"], use_container_width=True)
            else:
                st.info(f"**Result:** {response['result']}")
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["summary"],
                "code": response["code"],
                "result": str(response["result"])[:500]
            })
        else:
            st.error(response["error"])
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ {response['error']}"
            })