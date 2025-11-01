"""
Secrets management utility for Streamlit Cloud deployment.
Supports both Streamlit secrets and local .env files.
"""
import os
import streamlit as st
from dotenv import load_dotenv

# Load .env for local development (doesn't affect Streamlit Cloud)
load_dotenv()


def get_secret(key: str, default: str = None) -> str:
    """
    Get secret from Streamlit secrets first, then fall back to environment variable.
    
    Args:
        key: Secret key name
        default: Default value if not found
        
    Returns:
        Secret value or default
    """
    try:
        # Try Streamlit secrets first (for Streamlit Cloud)
        if hasattr(st, 'secrets') and key in st.secrets:
            value = st.secrets[key]
            if value:
                return str(value).strip()
    except Exception:
        pass
    
    # Fall back to environment variable (for local development)
    value = os.getenv(key, default)
    if value:
        return str(value).strip()
    
    return default


def get_all_secrets() -> dict:
    """
    Get all configured secrets as a dictionary.
    
    Returns:
        Dictionary of all secrets
    """
    secrets = {}
    
    # Get from Streamlit secrets
    try:
        if hasattr(st, 'secrets'):
            for key in st.secrets:
                secrets[key] = st.secrets[key]
    except Exception:
        pass
    
    # Merge with environment variables (env vars take precedence if already set)
    env_keys = [
        "GEMINI_API_KEY",
        "TURSO_DB_URL",
        "TURSO_DB_AUTH_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "SMTP_SERVER",
        "SMTP_PORT",
    ]
    
    for key in env_keys:
        if key not in secrets:
            value = os.getenv(key)
            if value:
                secrets[key] = value
    
    return secrets


def validate_secrets(required_keys: list = None) -> tuple:
    """
    Validate that required secrets are present.
    
    Args:
        required_keys: List of required secret keys
        
    Returns:
        Tuple of (is_valid: bool, missing_keys: list)
    """
    if required_keys is None:
        required_keys = ["GEMINI_API_KEY"]
    
    missing = []
    for key in required_keys:
        value = get_secret(key)
        if not value:
            missing.append(key)
    
    return len(missing) == 0, missing

