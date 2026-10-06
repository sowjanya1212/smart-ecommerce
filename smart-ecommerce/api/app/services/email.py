import logging
import smtplib
import threading
from email.message import EmailMessage

from ..config import settings

log = logging.getLogger("email")


def _send(to: str, subject: str, body: str):
    if not settings.SMTP_HOST:
        log.info("EMAIL (console mode)\n  To: %s\n  Subject: %s\n  %s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.EMAIL_FROM, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_TLS:
                smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception:
        log.exception("Failed to send email to %s", to)


def send_email(to: str, subject: str, body: str):
    """Fire-and-forget so requests never wait on SMTP."""
    threading.Thread(target=_send, args=(to, subject, body), daemon=True).start()
