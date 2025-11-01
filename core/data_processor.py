# core/data_processor.py

import pandas as pd
import streamlit as st

@st.cache_data
def preprocess_csv(uploaded_file) -> pd.DataFrame:
    """Load and preprocess uploaded CSV file"""
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    # Convert numeric strings
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col], errors="ignore")
            except:
                pass

    # Fill missing values
    for col in df.select_dtypes(include=["number"]).columns:
        if df[col].isna().any():
            df[col].fillna(df[col].median(), inplace=True)
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].isna().any():
            df[col].fillna("", inplace=True)
    return df


def validate_required_columns(df: pd.DataFrame, required_cols: list) -> tuple:
    """Validate that DataFrame has required columns"""
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return False, f"Missing columns: {', '.join(missing)}"
    return True, "OK"