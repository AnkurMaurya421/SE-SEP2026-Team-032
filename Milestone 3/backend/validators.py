"""Input checks. Each function returns an error message, or None when the input is fine."""
from constants import (ANSWERS, CONCERN_STATUSES, DURATIONS, FORMATS, GOALS_LIMIT, MATCH_STATUSES, MAX_CAPACITY, MENTOR_STATUSES, STUDENT_EMAIL_DOMAIN, TEXT_LIMIT,
                       WEEKDAYS)
from models import Topic


def is_text(value):
    """True when value is text with at least one character that is not a space."""
    if not isinstance(value, str):  # isinstance asks "is this value of this type?"
        return False
    return value.strip() != ""


def is_whole_number(value):
    """True for 1, 2, 3... but not for True or False (Python also counts those as numbers)."""
    if isinstance(value, bool):
        return False
    return isinstance(value, int)


def length_of(value):
    """The number of characters. Empty or missing text counts as 0."""
    if not value:
        return 0
    return len(value)


def not_text(data, fields):
    """Returns the first of these fields that is present but is not text (for example a number or a list)."""
    for field in fields:
        if data.get(field) is not None and not isinstance(data[field], str):
            return field
    return None


def is_iitm_email(email):
    """True for name@iitm.ac.in and for any sub-domain such as name@ds.study.iitm.ac.in."""
    parts = email.split("@")
    domain = parts[-1].lower()  # [-1] is the last part: the text after the @
    if domain == STUDENT_EMAIL_DOMAIN:
        return True
    return domain.endswith("." + STUDENT_EMAIL_DOMAIN)


def looks_like_email(email):
    """A simple check: there is an @, and a dot somewhere after it."""
    if not is_text(email):
        return False
    if "@" not in email:
        return False
    domain = email.split("@")[-1]
    return "." in domain


def check_register(data):
    if not is_text(data.get("full_name")):
        return "Full name is required."
    email = data.get("email")
    if not looks_like_email(email):
        return "A valid email is required."
    password = data.get("password")
    if not isinstance(password, str) or len(password) < 6:
        return "Password must be at least 6 characters."
    if data.get("role") not in ("student", "mentor"):
        return "Role must be 'student' or 'mentor'."
    if data["role"] == "student" and not is_iitm_email(email):
        return "Students must register with an IITM email (for example name@ds.study.iitm.ac.in)."
    return None


def check_topics(names):
    """names must be a non-empty list of topic names that exist."""
    if not isinstance(names, list) or not names:
        return "Choose at least one topic."
    known_names = []
    for topic in Topic.query.all():
        known_names.append(topic.name)

    unknown_names = []
    for name in names:
        if name not in known_names:
            unknown_names.append(str(name))

    if len(unknown_names) > 0:
        return "Unknown topic: " + ", ".join(unknown_names)  # join puts ", " between the names
    return None


def check_student_profile(data):
    bad = not_text(data, ["programme_level", "career_goals", "skills", "needs_text", "mentoring_format",
                          "expected_duration", "preferences", "availability_note"])
    if bad:
        return f"{bad} must be text."
    if not is_text(data.get("programme_level")) or not is_text(data.get("career_goals")):
        return "Programme level and career goals are required."
    if len(data["career_goals"]) > GOALS_LIMIT:
        return f"Career goals must be {GOALS_LIMIT} characters or fewer."
    if length_of(data.get("needs_text")) > TEXT_LIMIT:
        return f"Needs text must be {TEXT_LIMIT} characters or fewer."
    if data.get("mentoring_format") not in FORMATS:
        return "Mentoring format must be one of: " + ", ".join(FORMATS)
    if data.get("expected_duration") not in DURATIONS:
        return "Expected duration must be one of: " + ", ".join(DURATIONS)
    if not isinstance(data.get("looking_for_mentor", True), bool):
        return "looking_for_mentor must be true or false."
    return check_topics(data.get("topics"))


def check_mentor_profile(data, places_in_use=0):
    bad = not_text(data, ["qualifications", "bio", "skills_text"])
    if bad:
        return f"{bad} must be text."
    if not is_text(data.get("qualifications")):
        return "Qualifications are required."
    years = data.get("experience_years")
    if not is_whole_number(years) or years < 0 or years > 60:
        return "Experience must be a whole number of years from 0 to 60."
    if length_of(data.get("skills_text")) > TEXT_LIMIT:
        return f"Skills text must be {TEXT_LIMIT} characters or fewer."
    capacity = data.get("max_students")
    if not is_whole_number(capacity) or capacity < 1 or capacity > MAX_CAPACITY:
        return f"Maximum students must be a whole number from 1 to {MAX_CAPACITY}."
    if capacity < places_in_use:
        return f"This mentor already has {places_in_use} open matches, so the maximum cannot be lower."
    return check_topics(data.get("topics"))


def check_slot(data):
    if data.get("day_of_week") not in WEEKDAYS:
        return "Day must be one of: " + ", ".join(WEEKDAYS)
    start = data.get("start_time")
    end = data.get("end_time")
    if not is_text(start) or not is_text(end):
        return "Start and end time must look like 18:00."
    if len(start) != 5 or len(end) != 5:
        return "Start and end time must look like 18:00."
    if end <= start:  # times written as "HH:MM" can be compared as text
        return "End time must be after start time."
    return None


def check_mentor_status(value):
    if value not in MENTOR_STATUSES:
        return "Status must be one of: " + ", ".join(MENTOR_STATUSES)
    return None


def check_answer(value):
    if value not in ANSWERS:
        return "Answer must be one of: " + ", ".join(ANSWERS)
    return None


def check_match_status(value):
    if value not in MATCH_STATUSES:
        return "Status must be one of: " + ", ".join(MATCH_STATUSES)
    return None


def check_feedback(data):
    rating = data.get("rating")
    if not is_whole_number(rating) or rating < 1 or rating > 5:
        return "Rating must be a whole number from 1 to 5."
    comments = data.get("comments")
    if comments is not None and not isinstance(comments, str):
        return "comments must be text."
    if length_of(comments) > TEXT_LIMIT:
        return f"Comments must be {TEXT_LIMIT} characters or fewer."
    return None


def check_concern(data):
    if not is_text(data.get("text")):
        return "Describe your concern first."
    if len(data["text"]) > TEXT_LIMIT:
        return f"The concern must be {TEXT_LIMIT} characters or fewer."
    return None


def check_concern_status(value):
    if value not in CONCERN_STATUSES:
        return "Status must be one of: " + ", ".join(CONCERN_STATUSES)
    return None
