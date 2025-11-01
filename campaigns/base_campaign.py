# campaigns/base_campaign.py

from abc import ABC, abstractmethod
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BaseCampaign(ABC):
    """Abstract base class for all campaign types"""
    
    def __init__(self):
        self.campaign_type = self.__class__.__name__.replace("Campaign", "")
    
    @abstractmethod
    def validate_targets(self, df: pd.DataFrame, required_cols: list) -> tuple:
        """Validate target DataFrame has required columns
        
        Returns:
            tuple: (success: bool, message: str)
        """
        pass
    
    @abstractmethod
    def send(self, targets_df: pd.DataFrame, **kwargs) -> dict:
        """Send campaign to targets
        
        Returns:
            dict: {
                "success": bool,
                "sent": int,
                "failed": int,
                "details": list,
                "error": str (optional)
            }
        """
        pass
    
    def log_campaign(self, result: dict, query: str = "N/A"):
        """Log campaign results to session state"""
        import streamlit as st
        
        if "campaign_logs" not in st.session_state:
            st.session_state.campaign_logs = []
        
        st.session_state.campaign_logs.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": self.campaign_type,
            "targets": result.get("sent", 0) + result.get("failed", 0),
            "sent": result.get("sent", 0),
            "failed": result.get("failed", 0),
            "status": "✅ Success" if result.get("success") else "❌ Failed",
            "query": query
        })