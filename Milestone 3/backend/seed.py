"""Creates the fixed topics and the admin account the first time the app starts.
The admin is the client (IIC team): it is not created through registration."""
from flask import current_app

from auth_utils import hash_password
from constants import TOPICS
from database import db
from models import AvailabilitySlot, Match, MatchStatusLog, MentorProfile, StudentProfile, Topic, User
from services.matching import score_pair
from services.notifications import notify

ADMIN_EMAIL = "admin@client.test"
ADMIN_PASSWORD = "demo123"


def seed_basics():
    add_missing_topics()
    add_admin_account()
    db.session.commit()  # commit saves the changes in the database


def add_missing_topics():
    for name in TOPICS:
        existing = Topic.query.filter_by(name=name).first()
        if existing is None:
            db.session.add(Topic(name=name))


def add_admin_account():
    """Creates the admin account only if it does not exist yet."""
    existing = User.query.filter_by(email=ADMIN_EMAIL).first()
    if existing is not None:
        return
    password = current_app.config["ADMIN_PASSWORD"]
    if not password:
        password = ADMIN_PASSWORD  # nothing was set, so use the default
    admin = User(email=ADMIN_EMAIL, password_hash=hash_password(password), full_name="Admin", role="admin")
    db.session.add(admin)


# ---- Sample people for a demo (only when LOAD_DEMO_DATA=1 and the database has no students yet) ----
DEMO_PASSWORD = "demo123"
DEMO_STUDENTS = [
    ("Asha Verma", "asha@ds.study.iitm.ac.in", dict(
        programme_level="Diploma", career_goals="Move into data analytics", skills="Python, SQL",
        needs_text="I want to move from my current job into data analytics. I need help building a portfolio with SQL and Python projects and preparing for analyst interviews.",
        mentoring_format="Video call", expected_duration="3 months", preferences="Weekend calls",
        availability_note="Weekend evenings"), ["Data Science", "Career Switching"]),
    ("Rohan Das", "rohan@ds.study.iitm.ac.in", dict(
        programme_level="Foundation", career_goals="Prepare for software interviews", skills="HTML, JavaScript",
        needs_text="I am preparing for software developer interviews. I need practice with JavaScript questions, mock interviews and a plan for building web projects.",
        mentoring_format="Messaging", expected_duration="1 month", availability_note="Sunday afternoons"),
     ["Interview Preparation", "Web Development"]),
    ("Neha Joshi", "neha@ds.study.iitm.ac.in", dict(
        programme_level="Degree", career_goals="Plan a product management career", skills="Excel, communication",
        needs_text="I want to become a product manager. I need guidance on writing product requirements, preparing for product interviews and changing careers from operations.",
        mentoring_format="Phone call", expected_duration="6 months", preferences="Short weekly calls",
        availability_note="Sunday and Wednesday evenings"), ["Product Management", "Career Switching"]),
]
DEMO_MENTORS = [
    ("Dr. Meera Iyer", "meera@mentor.test", dict(
        qualifications="PhD, Data Science", experience_years=12, max_students=3, profile_status="verified",
        bio="Leads an analytics team and mentors early-career students.",
        skills_text="I coach students on data analytics careers, SQL and Python portfolio projects, and help people switch into data roles."),
     ["Data Science", "Career Switching"], [("Saturday", "18:00", "20:00")]),
    ("Karan Shah", "karan@mentor.test", dict(
        qualifications="B.Tech", experience_years=5, max_students=2, profile_status="pending", bio="Builds web apps with React and mentors students on their first projects.",
        skills_text="Web development with JavaScript and React, and guidance on small projects."),
     ["Web Development"], [("Tuesday", "19:00", "20:30")]),
    ("Priya Nair", "priya@mentor.test", dict(
        qualifications="MBA, Product Manager", experience_years=8, max_students=2, profile_status="verified",
        bio="Product manager who coaches students on product careers and interviews.",
        skills_text="I mentor on product management: writing product requirements, roadmaps, mock interviews for product roles and changing careers."),
     ["Product Management", "Interview Preparation", "Career Switching"], [("Sunday", "17:00", "19:00"), ("Wednesday", "18:00", "19:30")]),
]


def topics_named(names):
    return Topic.query.filter(Topic.name.in_(names)).all()


def add_demo_user(name, email, role):
    user = User(email=email, password_hash=hash_password(DEMO_PASSWORD), full_name=name, role=role)
    db.session.add(user)
    db.session.flush()
    return user


def seed_demo():
    """Three students, three mentors and one proposed match, so a new database is not empty."""
    if StudentProfile.query.count() > 0:
        return  # there are students already, so do nothing
    students = add_demo_students()
    mentors = add_demo_mentors()
    first_student = students[0]
    first_mentor = mentors[0]
    add_demo_match(first_student, first_mentor)
    db.session.commit()


def add_demo_students():
    students = []
    for name, email, fields, topics in DEMO_STUDENTS:
        user = add_demo_user(name, email, "student")
        # **fields passes every item of the dictionary as a named value, e.g. skills="Python, SQL"
        profile = StudentProfile(user_id=user.id, topics=topics_named(topics), **fields)
        db.session.add(profile)
        students.append(profile)
    return students


def add_demo_mentors():
    mentors = []
    for name, email, fields, topics, slots in DEMO_MENTORS:
        user = add_demo_user(name, email, "mentor")
        profile = MentorProfile(user_id=user.id, topics=topics_named(topics), **fields)
        db.session.add(profile)
        db.session.flush()  # flush sends the row to the database now, so profile.id gets a number
        for day, start, end in slots:
            slot = AvailabilitySlot(mentor_id=profile.id, day_of_week=day, start_time=start, end_time=end)
            db.session.add(slot)
        mentors.append(profile)
    return mentors


def add_demo_match(student, mentor):
    db.session.flush()
    admin = User.query.filter_by(email=ADMIN_EMAIL).first()
    score = score_pair(student, mentor)
    match = Match(student_id=student.id, mentor_id=mentor.id, proposed_by=admin.id, status="proposed",
                  match_score=score["total"], score_reasons="; ".join(score["reasons"]), notes="Goal fit: analytics")
    db.session.add(match)
    db.session.flush()
    first_log = MatchStatusLog(match_id=match.id, old_status=None, new_status="proposed", changed_by=admin.id)
    db.session.add(first_log)
    notify(mentor.user_id, "A new student match is waiting for your response.", match.id)
    notify(student.user_id, "A mentor has been proposed for you. Please accept or decline.", match.id)
