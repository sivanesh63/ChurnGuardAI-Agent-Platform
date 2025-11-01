import re
import pandas as pd
import numpy as np
import traceback

def sanitize_code(code: str) -> str:
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
    if not messages:
        return "No previous chat history."
    recent_msgs = messages[-(max_turns * 2):]
    lines = []
    for msg in recent_msgs:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)


def generate_pandas_query(query: str, df: pd.DataFrame, model) -> tuple:
    schema = "\n".join([f"- {col} ({dtype})" for col, dtype in df.dtypes.items()])
    prompt = f"""
You are a Python data analyst helping the user filter or query data.

DataFrame schema:
{schema}

Sample data (first 3 rows):
{df.head(3).to_string()}

User question: {query}

Return ONLY a single-line pandas expression that answers this.
"""
    response = model.generate_content(prompt)
    code = sanitize_code(response.text)
    return code, response.text


def safe_eval(expr: str, df: pd.DataFrame):
    safe_builtins = {
        "len": len, "sum": sum, "min": min, "max": max, "round": round,
        "abs": abs, "list": list, "dict": dict, "int": int, "float": float,
        "str": str, "bool": bool
    }
    allowed = {"df": df, "pd": pd, "np": np}
    if any(kw in expr for kw in ["os.", "sys.", "open(", "eval", "exec", "__import__"]):
        raise ValueError("⚠️ Unsafe code detected and blocked.")
    return eval(expr, {"__builtins__": safe_builtins}, allowed)


def execute_and_summarize(query: str, df: pd.DataFrame, model) -> dict:
    try:
        code, raw = generate_pandas_query(query, df, model)
        result = safe_eval(code, df)
        if isinstance(result, (pd.DataFrame, pd.Series)):
            result_str = result.head(10).to_string()
        else:
            result_str = str(result)
        summary_prompt = f"""User asked: "{query}"
Code executed: {code}
Result: {result_str}

Explain in 1-2 sentences what this result means."""
        summary = model.generate_content(summary_prompt).text
        return {"success": True, "code": code, "result": result, "summary": summary, "error": None}
    except Exception as e:
        return {
            "success": False,
            "code": code if 'code' in locals() else "N/A",
            "result": None,
            "summary": None,
            "error": f"Error: {str(e)}\n\n{traceback.format_exc()}"
        }


