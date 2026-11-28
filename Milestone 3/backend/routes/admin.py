"""The admin (client) dashboard: overview, search of both profile types, and editing mentors
(US-C01, US-C05, US-C06). Every route here is for admins only; students and mentors get 403."""
from flask import Blueprint, jsonify, request

import validators
from auth_utils import role_required
from constants import MATCH_STATUSES
from database import db
from models import EmailLog, Match, MentorProfile, StudentProfile, names_of
from responses import error, json_body, to_dict_list
from services import profiles as profile_service
from services.analytics import capacity_summary, feedback_summary, pulse_summary
from services.matching import waiting_students

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def on_dashboard(mentor):
    """A mentor shows up for the admin once the profile is complete (or when already verified)."""
    return mentor.profile_complete or mentor.profile_status == "verified"


def contains(text, search):
    """True when the search words appear in the text. Capital letters do not matter."""
    if text is None:
        text = ""
    return search.lower() in text.lower()


def dashboard_mentors():
    mentors = []
    for mentor in MentorProfile.query.all():
        if on_dashboard(mentor):
            mentors.append(mentor)
    return mentors


def count_mentors_with_status(mentors, status):
    count = 0
    for mentor in mentors:
        if mentor.profile_status == status:
            count += 1
    return count


def count_matches_by_status():
    """A dictionary such as {"proposed": 1, "active": 2, ...}."""
    counts = {}
    for status in MATCH_STATUSES:
        counts[status] = Match.query.filter_by(status=status).count()
    return counts


@bp.get("/overview")
@role_required("admin")
def overview():
    """Numbers for the dashboard: people, matches by status, and what is waiting."""
    mentors = dashboard_mentors()
    total_mentor_accounts = MentorProfile.query.count()
    mentor_numbers = {
        "total": len(mentors),
        "verified": count_mentors_with_status(mentors, "verified"),
        "pending": count_mentors_with_status(mentors, "pending"),
        "incomplete": total_mentor_accounts - len(mentors),
    }
    return jsonify({
        "students": StudentProfile.query.count(),
        "mentors": mentor_numbers,
        "matches": count_matches_by_status(),
        "students_waiting_for_match": len(waiting_students()),
    })


@bp.get("/analytics")
@role_required("admin")
def analytics():
    """Numbers for the charts: check-in health, feedback ratings and mentor capacity."""
    return jsonify({"pulse": pulse_summary(), "feedback": feedback_summary(), "capacity": capacity_summary()})


@bp.get("/emails")
@role_required("admin")
def email_log():
    """The most recent emails the platform sent (or tried to send). ?limit=50 by default."""
    # request.args holds the values after the ? in the address
    limit = request.args.get("limit", default=50, type=int)
    if limit < 1:
        return error("limit must be 1 or more.", 400)
    rows = EmailLog.query.order_by(EmailLog.id.desc()).limit(limit).all()
    return jsonify({"emails": to_dict_list(rows)})


def student_matches_filters(student, filters):
    """True when the student passes every filter the admin typed."""
    looking = filters.get("looking")
    if looking == "true" and not student.looking_for_mentor:
        return False
    if looking == "false" and student.looking_for_mentor:
        return False

    search = filters.get("search")
    if search:
        in_name = contains(student.user.full_name, search)
        in_skills = contains(student.skills, search)
        if not in_name and not in_skills:
            return False

    topic = filters.get("topic")
    if topic and topic not in names_of(student.topics):
        return False

    level = filters.get("programme_level")
    if level and student.programme_level != level:
        return False
    return True


@bp.get("/students")
@role_required("admin")
def list_students():
    """Optional filters: ?search=name or skills, ?topic=Data Science, ?programme_level=Diploma, ?looking=true|false"""
    students = []
    for student in StudentProfile.query.all():
        if student_matches_filters(student, request.args):
            students.append(student)
    return jsonify({"students": to_dict_list(students)})


@bp.get("/students/<int:student_id>")
@role_required("admin")
def get_student(student_id):
    student = db.session.get(StudentProfile, student_id)
    if student is None:
        return error("Student not found.", 404)
    return jsonify({"profile": student.to_dict()})


def mentor_matches_filters(mentor, filters):
    """True when the mentor passes every filter the admin typed."""
    status = filters.get("status")
    if status and mentor.profile_status != status:
        return False

    topic = filters.get("topic")
    if topic and topic not in names_of(mentor.topics):
        return False

    search = filters.get("search")
    if search:
        in_name = contains(mentor.user.full_name, search)
        in_skills = contains(mentor.skills_text, search)
        if not in_name and not in_skills:
            return False
    return True


@bp.get("/mentors")
@role_required("admin")
def list_mentors():
    """Mentors with a complete profile (and verified ones). Optional filters: ?status=pending|verified, ?topic=Data Science, ?search=name or skills"""
    mentors = []
    for mentor in dashboard_mentors():
        if mentor_matches_filters(mentor, request.args):
            mentors.append(mentor)
    return jsonify({"mentors": to_dict_list(mentors)})


@bp.get("/mentors/<int:mentor_id>")
@role_required("admin")
def get_mentor(mentor_id):
    mentor = db.session.get(MentorProfile, mentor_id)
    if mentor is None:
        return error("Mentor not found.", 404)
    return jsonify({"profile": mentor.to_dict()})


@bp.put("/mentors/<int:mentor_id>")
@role_required("admin")
def update_mentor(mentor_id):
    """The admin edits a mentor's expertise, skills, experience and capacity (US-C05)."""
    mentor = db.session.get(MentorProfile, mentor_id)
    if mentor is None:
        return error("Mentor not found.", 404)
    problem = profile_service.save_mentor_profile(mentor, json_body())
    if problem:
        return error(problem, 400)
    return jsonify({"profile": mentor.to_dict()})


@bp.patch("/mentors/<int:mentor_id>/status")
@role_required("admin")
def set_mentor_status(mentor_id):
    """Verify a mentor (or put them back to pending)."""
    mentor = db.session.get(MentorProfile, mentor_id)
    if mentor is None:
        return error("Mentor not found.", 404)
    status = json_body().get("status")
    problem = validators.check_mentor_status(status)
    if problem:
        return error(problem, 400)
    if status == "verified" and not mentor.profile_complete:
        return error("This mentor has not finished their profile yet.", 409)
    mentor.profile_status = status
    db.session.commit()
    return jsonify({"profile": mentor.to_dict()})


@bp.post("/mentors/<int:mentor_id>/availability")
@role_required("admin")
def add_mentor_slot(mentor_id):
    mentor = db.session.get(MentorProfile, mentor_id)
    if mentor is None:
        return error("Mentor not found.", 404)
    slot, problem = profile_service.add_slot(mentor, json_body())
    if problem:
        return error(problem, 400)
    return jsonify({"slot": slot.to_dict()}), 201


@bp.delete("/mentors/<int:mentor_id>/availability/<int:slot_id>")
@role_required("admin")
def remove_mentor_slot(mentor_id, slot_id):
    mentor = db.session.get(MentorProfile, mentor_id)
    if mentor is None or not profile_service.remove_slot(mentor, slot_id):
        return error("Slot not found.", 404)
    return "", 204
