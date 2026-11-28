"""Sending emails through Brevo (https://www.brevo.com). Without a BREVO_API_KEY nothing is sent:
the email is only saved in the email log (status "not_configured"), and the person still gets an in-app notification."""
import json
import urllib.request

from flask import current_app

from database import db
from models import EmailLog
from services.notifications import notify

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def post_to_brevo(user, subject, body):
    """Calls the Brevo API. Returns True when Brevo accepted the email."""
    config = current_app.config
    message_to_send = {
        "sender": {"name": config["EMAIL_FROM_NAME"], "email": config["EMAIL_FROM"]},
        "to": [{"email": user.email, "name": user.full_name}],
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "api-key": config["BREVO_API_KEY"],
        "content-type": "application/json",
        "accept": "application/json",
    }
    data = json.dumps(message_to_send).encode("utf-8")  # web requests send bytes, not text
    request = urllib.request.Request(BREVO_URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            # status codes from 200 to 299 mean "it worked"
            return response.status >= 200 and response.status < 300
    except Exception:  # network problem, wrong key, and so on: the caller records "failed"
        return False


def email_is_set_up():
    """Both the Brevo key and the sender address are needed."""
    config = current_app.config
    return config["BREVO_API_KEY"] != "" and config["EMAIL_FROM"] != ""


def deliver(user, subject, body):
    """Tries to send the email and returns the word we save in the log."""
    if not email_is_set_up():
        return "not_configured"
    if post_to_brevo(user, subject, body):
        return "sent"
    return "failed"


def send_email(user, subject, body, match_id=None):
    """Emails one user, logs it, and also leaves an in-app notification. Returns the EmailLog row. The caller commits."""
    status = deliver(user, subject, body)
    row = EmailLog(user_id=user.id, to_email=user.email, subject=subject, body=body, status=status)
    db.session.add(row)
    notify(user.id, subject + ": " + body, match_id)
    return row
