# campaigns/email_campaign.py

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from campaigns.base_campaign import BaseCampaign

logger = logging.getLogger(__name__)

class EmailCampaign(BaseCampaign):
    """Email campaign using Gmail SMTP"""
    
    def __init__(self, email_user: str, email_pass: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 465):
        super().__init__()
        self.email_user = email_user
        self.email_pass = email_pass
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
    
    def validate_targets(self, df, required_cols):
        """Validate email column exists"""
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            return False, f"Missing columns: {', '.join(missing)}"
        return True, "OK"
    
    def create_html_message(self, name: str) -> str:
        """Create HTML email content"""
        return f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <p>Hi {name},</p>
                <p>We miss you! Get <b>40% OFF</b> using code <b>WELCOME40</b>!</p>
                <p>Best,<br>Your ChurnGuard Team</p>
            </body>
        </html>
        """
    
    def send(self, targets_df, email_col: str = None, name_col: str = None):
        """Send personalized emails using Gmail SMTP"""
        
        # Testing mode: send all to fixed address
        TO_EMAIL = "sivaneshwarandr@gmail.com"
        
        if not self.email_user or not self.email_pass:
            return {"success": False, "error": "Missing email credentials"}

        sent_count, failed_count = 0, 0
        failed_details = []

        try:
            logger.info(f"📡 Connecting to {self.smtp_server}:{self.smtp_port}...")
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30) as server:
                server.login(self.email_user, self.email_pass)
                logger.info("✅ Logged into SMTP server")

                for _, row in targets_df.iterrows():
                    try:
                        email = TO_EMAIL  # Testing mode
                        name = str(row.get(name_col, "Valued Customer")) if name_col else "Valued Customer"

                        msg = MIMEMultipart("alternative")
                        msg["Subject"] = "We Miss You! Exclusive Offer Inside 🎁"
                        msg["From"] = self.email_user
                        msg["To"] = email

                        html_content = self.create_html_message(name)
                        msg.attach(MIMEText(html_content, "html"))

                        server.send_message(msg)
                        sent_count += 1
                        logger.info(f"✅ Email sent to {email}")

                    except Exception as e:
                        failed_count += 1
                        failed_details.append(f"{TO_EMAIL}: {e}")
                        logger.error(f"❌ Failed to send to {TO_EMAIL}: {e}")

            return {
                "success": True,
                "sent": sent_count,
                "failed": failed_count,
                "details": failed_details
            }

        except Exception as e:
            logger.critical(f"❌ Email campaign failed: {e}")
            return {"success": False, "error": str(e)}