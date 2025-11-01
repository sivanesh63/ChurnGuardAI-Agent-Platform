# core/code_executor.py

import pandas as pd
import numpy as np
import traceback

class SafeExecutor:
    """Safely execute pandas queries"""
    
    def __init__(self, model):
        self.model = model
    
    def safe_eval(self, expr: str, df: pd.DataFrame):
        """Safely evaluate a pandas expression"""
        safe_builtins = {
            "len": len, "sum": sum, "min": min, "max": max, "round": round,
            "abs": abs, "list": list, "dict": dict, "int": int, "float": float,
            "str": str, "bool": bool
        }
        allowed = {"df": df, "pd": pd, "np": np}

        if any(kw in expr for kw in ["os.", "sys.", "open(", "eval", "exec", "__import__"]):
            raise ValueError("⚠️ Unsafe code detected and blocked.")
        return eval(expr, {"__builtins__": safe_builtins}, allowed)
    
    def execute_and_summarize(self, query: str, df: pd.DataFrame, code: str) -> dict:
        """Complete query execution pipeline"""
        try:
            result = self.safe_eval(code, df)

            if isinstance(result, (pd.DataFrame, pd.Series)):
                result_str = result.head(10).to_string()
            else:
                result_str = str(result)

            summary_prompt = f"""User asked: "{query}"
Code executed: {code}
Result: {result_str}

Explain in 1-2 sentences what this result means."""
            summary = self.model.generate_content(summary_prompt).text

            return {"success": True, "code": code, "result": result, "summary": summary, "error": None}
        except Exception as e:
            return {
                "success": False,
                "code": code if 'code' in locals() else "N/A",
                "result": None,
                "summary": None,
                "error": f"Error: {str(e)}\n\n{traceback.format_exc()}"
            }