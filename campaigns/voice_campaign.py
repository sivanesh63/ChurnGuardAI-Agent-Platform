# campaigns/voice_campaign.py

import re
import logging
from twilio.rest import Client
from campaigns.base_campaign import BaseCampaign

logger = logging.getLogger(__name__)

class VoiceCampaign(BaseCampaign):
    """Voice call campaign using Twilio"""
    
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
    
    def send(self, targets_df, phone_col, message_text="Hello! We value you as our customer. Please check your messages for a special offer."):
        """Make voice calls using Twilio with Text-to-Speech"""
        try:
            if not all([self.account_sid, self.auth_token, self.from_phone]):
                return {"success": False, "sent": 0, "failed": 0, "error": "Missing Twilio credentials"}

            self.client = Client(self.account_sid, self.auth_token)
            sent_count, failed_count = 0, 0
            failed_details = []

            for _, row in targets_df.iterrows():
                try:
                    phone = str(row.get(phone_col, "")).strip().replace(" ", "").replace("-", "")
                    if phone.startswith("+91"):
                        phone = phone[3:]
                    if not re.fullmatch(r"\d{10}", phone):
                        failed_count += 1
                        failed_details.append(f"Invalid phone: {phone}")
                        continue

                    call = self.client.calls.create(
                        twiml=f'<Response><Say>{message_text}</Say></Response>',
                        to=f"+91{phone}",
                        from_=self.from_phone
                    )

                    logger.info(f"📞 Call placed to {phone} (SID: {call.sid})")
                    sent_count += 1

                except Exception as e:
                    failed_count += 1
                    failed_details.append(f"{phone}: {e}")
                    logger.error(f"❌ Failed to call {phone}: {e}")

            return {
                "success": True,
                "sent": sent_count,
                "failed": failed_count,
                "details": failed_details[:10]
            }

        except Exception as e:
            logger.critical(f"❌ Call campaign failed: {e}")
            return {"success": False, "sent": 0, "failed": len(targets_df), "error": str(e)}