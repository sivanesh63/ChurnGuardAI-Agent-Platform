# core/query_generator.py

import re
import pandas as pd
import streamlit as st

def sanitize_code(code: str) -> str:
    """Extract valid Python expression from LLM response"""
    match = re.search(r"```(?:python)?\s*(.*?)```", code, re.DOTALL)
    if match:
        code = match.group(1).strip()
    code = code.strip('`').strip()
    lines = [l.strip() for l in code.split("\n") if l.strip() and not l.strip().startswith("#")]
    if lines:
        code = lines[0]
    code = code.strip('`').split("#")[0].strip()
    return code


def build_chat_context(messages, max_turns=3):
    """Build chat context from last few turns"""
    if not messages:
        return "No previous chat history."
    recent_msgs = messages[-(max_turns * 2):]
    lines = []
    for msg in recent_msgs:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


class QueryGenerator:
    """Generate pandas queries from natural language"""
    
    def __init__(self, model):
        self.model = model
    
    def generate_query(self, query: str, df: pd.DataFrame) -> tuple:
        """Generate pandas query from natural language"""
        schema = "\n".join([f"- {col} ({dtype})" for col, dtype in df.dtypes.items()])
        chat_context = build_chat_context(st.session_state.get("messages", []))
        
        prompt = f"""
You are a Python data analyst helping the user filter or query data.

Chat history:
{chat_context}

DataFrame schema:
{schema}

Sample data (first 3 rows):
{df.head(3).to_string()}

User question: {query}

Return ONLY a single-line pandas expression that answers this.
Examples:
- df[df['churn'] > 0.8]
- df[df['age'] < 30]
- df[(df['status'] == 'active') & (df['days_since_purchase'] > 90)]
"""
        response = self.model.generate_content(prompt)
        code = sanitize_code(response.text)
        return code, response.text