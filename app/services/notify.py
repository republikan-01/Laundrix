from flask import current_app
from ..extensions import db
from ..models import Notification, User


def notify(user_id, message):
    """Create an in-app notification and optionally send configured SMS/WhatsApp."""
    user = db.session.get(User, user_id)
    if not user or not user.notifications_enabled:
        return
    db.session.add(Notification(user_id=user_id, message=message[:255]))
    # Twilio is optional. No external message is sent unless credentials are configured.
    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    sender = current_app.config.get("TWILIO_FROM")
    channel = current_app.config.get("TWILIO_CHANNEL", "sms").lower()
    if sid and token and sender and user.phone:
        try:
            import requests
            raw_phone = user.phone.replace(" ", "").replace("-", "")
            if raw_phone.startswith("0") and len(raw_phone) == 11:
                to = "+234" + raw_phone[1:]
            elif raw_phone.startswith("234"):
                to = "+" + raw_phone
            else:
                to = raw_phone if raw_phone.startswith("+") else "+" + raw_phone
            frm = sender
            if channel == "whatsapp":
                to = "whatsapp:" + to
                frm = sender if sender.startswith("whatsapp:") else "whatsapp:" + sender
            requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"From": frm, "To": to, "Body": message[:1500]},
                auth=(sid, token), timeout=8
            ).raise_for_status()
        except Exception as exc:
            current_app.logger.warning("Optional Twilio notification failed: %s", exc)
