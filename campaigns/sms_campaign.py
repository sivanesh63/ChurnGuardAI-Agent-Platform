# campaigns/sms_campaign.py

import re
import logging
from twilio.rest import Client
from campaigns.base_campaign import BaseCampaign

logger = logging.getLogger(__name__)

class SMSCampaign(BaseCampaign):
    """SMS campaign using Twilio"""
    
    def __init__(self, account_sid: str, auth_token: str, from_phone: str):
        super().__init__()
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_phone = from_phone
        self.client = None
    
    def validate_targets(self, df, required_cols):
        """Validate phone column exists"""
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            return False, f"Missing columns: {', '.join(missing)}"
        return True, "OK"
    
    def send(self, targets_df, phone_col, name_col=None):
        """Send SMS campaign with proper validation and personalization"""
        try:
            if not all([self.account_sid, self.auth_token, self.from_phone]):
                return {"success": False, "sent": 0, "failed": 0, "error": "Missing Twilio credentials"}

            self.client = Client(self.account_sid, self.auth_token)
            sent_count, failed_count = 0, 0
            failed_details = []

            # Default message
            default_message = "🎁 Hi! We miss you! As a valued customer, here's an EXCLUSIVE 30% OFF just for you. Use code: COMEBACK30. Valid for 48 hours only!"

            for _, row in targets_df.iterrows():
                try:
                    message = default_message
                    
                    # Personalize with name
                    if name_col and name_col in targets_df.columns:
                        name = str(row.get(name_col, "Customer"))
                        message = message.replace("Hi!", f"Hi {name}!")

                    # Validate phone
                    phone = str(row.get(phone_col, "")).strip().replace(" ", "").replace("-", "")
                    if phone.startswith("+91"):
                        phone = phone[3:]
                    if not re.fullmatch(r"\d{10}", phone):
                        failed_count += 1
                        failed_details.append(f"Invalid phone: {phone}")
                        continue

                    # Send SMS
                    message_obj = self.client.messages.create(
                        body=message,
                        from_=self.from_phone,
                        to=f"+91{phone}"
                    )

                    logger.info(f"✅ Sent to {phone} (SID: {message_obj.sid})")
                    sent_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{phone}: {str(e)}")
                    logger.error(f"❌ Failed to send to {phone}: {e}")

            return {
                "success": True,
                "sent": sent_count,
                "failed": failed_count,
                "details": failed_details[:10]
            }

        except Exception as e:
            logger.critical(f"❌ SMS campaign failed: {e}")
            return {"success": False, "sent": 0, "failed": len(targets_df), "error": str(e)}