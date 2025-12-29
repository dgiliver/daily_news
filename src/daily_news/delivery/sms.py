"""SMS delivery via email-to-SMS gateway."""

import logging
import smtplib
from email.mime.text import MIMEText
from typing import ClassVar

from daily_news.config import settings
from daily_news.models import NewsDigest

logger = logging.getLogger(__name__)


class SMSDelivery:
    """Send headlines via email-to-SMS gateway."""

    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587

    # Common US carrier gateways
    CARRIER_GATEWAYS: ClassVar[dict[str, str]] = {
        "att": "txt.att.net",
        "verizon": "vtext.com",
        "tmobile": "tmomail.net",
        "sprint": "messaging.sprintpcs.com",
    }

    def __init__(self):
        if not settings.gmail_address or not settings.gmail_app_password:
            raise ValueError("Gmail credentials are required for SMS delivery")
        self.sender = settings.gmail_address
        self.password = settings.gmail_app_password
        self.gateway = settings.sms_carrier_gateway
        self.recipients = settings.sms_recipient_list

    def send_headlines(self, digest: NewsDigest) -> bool:
        """Send top headlines via SMS.

        Args:
            digest: NewsDigest containing headlines

        Returns:
            True if sent successfully to all recipients
        """
        if not self.recipients:
            logger.warning("No SMS recipients configured")
            return False

        message = self._format_sms(digest)
        success = True

        for phone in self.recipients:
            sms_email = f"{phone}@{self.gateway}"
            if not self._send_single_sms(sms_email, message):
                success = False

        return success

    def _send_single_sms(self, recipient: str, message: str) -> bool:
        """Send SMS to a single recipient."""
        msg = MIMEText(message)
        msg["From"] = self.sender
        msg["To"] = recipient
        # SMS gateways typically ignore subject

        try:
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)

            logger.info(f"SMS sent to {recipient}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"Failed to send SMS to {recipient}: {e}")
            return False
        except Exception as e:
            logger.error(f"SMS error for {recipient}: {e}")
            return False

    def _format_sms(self, digest: NewsDigest) -> str:
        """Format digest for SMS (160 char limit per segment).

        Args:
            digest: NewsDigest with headlines

        Returns:
            Formatted SMS message
        """
        lines = [f"News {digest.date.strftime('%m/%d')}:"]

        # Use the SMS headlines (top 5) from digest
        for i, article in enumerate(digest.sms_headlines, 1):
            # Truncate title to fit SMS constraints
            title = article.title
            if len(title) > 55:
                title = title[:52] + "..."
            lines.append(f"{i}. {title}")

        return "\n".join(lines)

    def send_breaking_alert(self, headline: str, _url: str) -> bool:
        """Send a breaking news alert.

        Args:
            headline: Breaking news headline
            url: Link to story

        Returns:
            True if sent successfully
        """
        if not self.recipients:
            return False

        # Truncate for SMS
        if len(headline) > 100:
            headline = headline[:97] + "..."

        message = f"BREAKING: {headline}"

        success = True
        for phone in self.recipients:
            sms_email = f"{phone}@{self.gateway}"
            if not self._send_single_sms(sms_email, message):
                success = False

        return success
