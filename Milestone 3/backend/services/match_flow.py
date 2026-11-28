"""What happens to a match after it is proposed (US-C03, US-C04).
Both sides answer. The admin confirms the match only when both accepted, or cancels it. Each function returns an
error message, or None when it worked. The route commits the change."""
from constants import MATCH_NEXT
from database import db
from models import MatchStatusLog, now
from services.checkins import schedule_check_ins
from services.emailer import send_email
from services.notifications import notify, notify_admins


def both_accepted(match):
    return match.mentor_response == "accepted" and match.student_response == "accepted"


def record_answer(match, who, answer):
    """who is 'mentor' or 'student'; answer is 'accepted' or 'declined'."""
    if match.status != "proposed":
        return "This match is no longer waiting for an answer."

    if who == "student":
        if match.student_response != "pending":
            return "You have already answered this proposal."
        match.student_response = answer
        match.student_responded_at = now()
        person_name = match.student.user.full_name
    else:
        if match.mentor_response != "pending":
            return "You have already answered this proposal."
        match.mentor_response = answer
        match.mentor_responded_at = now()
        person_name = match.mentor.user.full_name

    names = pair_names(match)
    # an f"..." string puts the value of each {name} into the text
    notify_admins(f"{person_name} ({who}) {answer} the proposed match {names}.", match.id)
    if both_accepted(match):
        notify_admins(f"Both accepted: {names} is ready for you to confirm.", match.id)
    return None


def pair_names(match):
    """For example "Asha Verma / Dr. Meera Iyer"."""
    return f"{match.student.user.full_name} / {match.mentor.user.full_name}"


def change_status(match, new_status, admin):
    """The admin moves the match to its next status."""
    allowed_next = MATCH_NEXT[match.status]
    if new_status not in allowed_next:
        return f"A {match.status} match cannot become {new_status}."
    if match.status == "proposed" and new_status == "active" and not both_accepted(match):
        return "Both the mentor and the student must accept before the match can be confirmed."

    # write down who changed what, then change it
    entry = MatchStatusLog(match_id=match.id, old_status=match.status, new_status=new_status, changed_by=admin.id)
    db.session.add(entry)
    match.status = new_status

    if new_status == "active":
        start_mentorship(match)

    tell_everyone_about_status(match, new_status)
    return None


def start_mentorship(match):
    """The things that happen once, when a match becomes active."""
    match.confirmed_at = now()
    schedule_check_ins(match)
    introduce(match)


def tell_everyone_about_status(match, new_status):
    student = match.student
    mentor = match.mentor
    notify(student.user_id, f"Your mentoring match with {mentor.user.full_name} is now {new_status}.", match.id)
    notify(mentor.user_id, f"Your match with {student.user.full_name} is now {new_status}.", match.id)
    notify_admins(f"Match {pair_names(match)} is now {new_status}.", match.id)


def introduce(match):
    """When a match becomes active, each person gets an email with the other person's email address."""
    student = match.student.user
    mentor = match.mentor.user
    send_email(student, "Your mentor is confirmed",
               f"{mentor.full_name} is now your mentor. You can reach them at {mentor.email}.", match.id)
    send_email(mentor, "Your student is confirmed",
               f"{student.full_name} is now your student. You can reach them at {student.email}.", match.id)
