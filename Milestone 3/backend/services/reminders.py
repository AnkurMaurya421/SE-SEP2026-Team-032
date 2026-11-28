"""The weekly reminder job. A scheduler (GitHub Actions) calls POST /api/jobs/reminders; this does the work."""
from models import now
from services.checkins import active_check_ins
from services.emailer import send_email


def needs_reminder(checkin):
    """True when the check-in is waiting for an answer and no reminder was sent yet."""
    if checkin.reminder_sent_at is not None:
        return False
    return checkin.state() in ["due", "overdue"]


def send_due_reminders():
    """Emails everyone who needs a reminder. Returns how many emails were handled."""
    sent = 0
    for checkin in active_check_ins():
        if not needs_reminder(checkin):
            continue
        message = f"Your week {checkin.week} check-in is ready. Please answer it on your Check-ins page."
        send_email(checkin.user, "Check-in reminder", message, checkin.match_id)
        checkin.reminder_sent_at = now()  # so we do not remind this person again
        sent += 1
    return sent
