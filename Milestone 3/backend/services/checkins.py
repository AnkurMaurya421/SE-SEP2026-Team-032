"""Weekly check-ins (Mentorship Pulse). One row per week for the student and one for the mentor of an active match."""
from datetime import timedelta

from constants import CHECKIN_WEEKS
from database import db
from models import CheckIn, Match, now
from services.pulse_review import review_check_in
from services.notifications import notify_admins


def weeks_for(duration):
    """How many weekly check-ins a mentorship of this duration gets."""
    if duration in CHECKIN_WEEKS:
        return CHECKIN_WEEKS[duration]
    return CHECKIN_WEEKS["Not sure yet"]


def schedule_check_ins(match):
    """Called when a match becomes active. Creates the rows for every week (only once)."""
    already_made = CheckIn.query.filter_by(match_id=match.id).count()
    if already_made > 0:
        return

    start = match.confirmed_at
    if start is None:
        start = now()

    total_weeks = weeks_for(match.student.expected_duration)
    # range(1, 5) gives 1, 2, 3, 4, so we add 1 to include the last week
    for week in range(1, total_weeks + 1):
        due = start + timedelta(days=7 * week)
        add_check_in(match, match.student.user_id, "student", week, due)
        add_check_in(match, match.mentor.user_id, "mentor", week, due)


def add_check_in(match, user_id, role, week, due):
    checkin = CheckIn(match_id=match.id, user_id=user_id, by_role=role, week=week, due_at=due)
    db.session.add(checkin)


def save_answer(checkin, rating, comment):
    """Stores the answer, reviews it and tells the admins when it was flagged."""
    checkin.rating = rating
    if comment is None:
        comment = ""
    checkin.comment = comment.strip()
    checkin.submitted_at = now()
    review_check_in(checkin)
    if checkin.review_status == "open":
        notify_admins(f"Mentorship Pulse: week {checkin.week} check-in from {checkin.user.full_name} "
                      f"is marked \"{checkin.review_verdict}\". Please review.", checkin.match_id)


def active_check_ins():
    """Every check-in that belongs to a match that is still active, earliest first."""
    query = CheckIn.query.join(Match, CheckIn.match_id == Match.id)  # join: look at the match of each check-in
    query = query.filter(Match.status == "active")
    query = query.order_by(CheckIn.due_at)
    return query.all()


def needs_admin(checkin):
    """True for an answer the review flagged, or a check-in nobody answered in time."""
    if checkin.review_status == "open":
        return True
    if checkin.review_status is not None:
        return False  # it was fine, or the admin already reviewed it
    if checkin.submitted_at is not None:
        return False
    return checkin.state() == "overdue"


def flagged_check_ins():
    """The check-ins the admin has to look at."""
    flagged = []
    for checkin in active_check_ins():
        if needs_admin(checkin):
            flagged.append(checkin)
    return flagged


def mark_reviewed(checkin, note):
    if checkin.review_verdict is None:  # an unanswered check-in has no review yet
        checkin.review_verdict = "needs attention"
        checkin.review_reason = "The check-in was not answered in time."
        checkin.review_source = "rules"
    checkin.review_status = "reviewed"
    if note is None:
        note = ""
    checkin.admin_note = note.strip()
