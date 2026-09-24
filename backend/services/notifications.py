"""Email / SMS dispatch. Falls back to a logged dev-mode 'SENT' status when
no provider API key is configured, so the app and test suite run fully
offline. Provider calls are wrapped so a provider error marks the
notification FAILED rather than raising."""
from flask import current_app

from backend.extensions import db
from backend.models import Notification, User


def send_email(recipient: User, subject: str, body: str) -> Notification | None:
    if recipient.opt_out_email:
        return None
    notif = Notification(recipient_id=recipient.id, type="EMAIL", subject=subject, body=body, status="PENDING")
    db.session.add(notif)
    db.session.commit()

    api_key = current_app.config.get("SENDGRID_API_KEY")
    if not api_key:
        notif.status = "SENT"
        db.session.commit()
        return notif

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email="noreply@rentalpro.example",
            to_emails=recipient.email,
            subject=subject,
            plain_text_content=body,
        )
        SendGridAPIClient(api_key).send(message)
        notif.status = "SENT"
    except Exception:
        notif.status = "FAILED"
        notif.retry_count += 1
    db.session.commit()
    return notif


def send_email_raw(to_email: str, subject: str, body: str) -> bool:
    """Sends to an address with no User row yet (e.g. a tenant invitation
    sent before the invitee has an account) — not logged as a Notification
    since that table's recipient_id is a required FK to users.id."""
    api_key = current_app.config.get("SENDGRID_API_KEY")
    if not api_key:
        return True
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(from_email="noreply@rentalpro.example", to_emails=to_email, subject=subject, plain_text_content=body)
        SendGridAPIClient(api_key).send(message)
        return True
    except Exception:
        return False


def send_sms(recipient: User, body: str) -> Notification | None:
    if recipient.opt_out_sms:
        return None
    notif = Notification(recipient_id=recipient.id, type="SMS", body=body, status="PENDING")
    db.session.add(notif)
    db.session.commit()

    sid = current_app.config.get("TWILIO_ACCOUNT_SID")
    token = current_app.config.get("TWILIO_AUTH_TOKEN")
    from_number = current_app.config.get("TWILIO_FROM_NUMBER")
    if not (sid and token and from_number):
        notif.status = "SENT"
        db.session.commit()
        return notif

    try:
        from twilio.rest import Client

        client = Client(sid, token)
        client.messages.create(body=body, from_=from_number, to=getattr(recipient, "phone", "") or "")
        notif.status = "SENT"
    except Exception:
        notif.status = "FAILED"
        notif.retry_count += 1
    db.session.commit()
    return notif
