import smtplib
from email.message import EmailMessage
from flask import current_app


def send_email(to, subject, body):
    c = current_app.config
    if not c["MAIL_SERVER"]:
        print(f"\n[DEV EMAIL] To: {to}\nSubject: {subject}\n{body}\n")  # no SMTP configured
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = c["MAIL_FROM"], to, subject
    msg.set_content(body)
    with smtplib.SMTP(c["MAIL_SERVER"], c["MAIL_PORT"], timeout=15) as s:
        s.starttls()
        if c["MAIL_USERNAME"]:
            s.login(c["MAIL_USERNAME"], c["MAIL_PASSWORD"])
        s.send_message(msg)
