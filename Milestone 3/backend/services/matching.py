"""Matching rules (US-C02). Plain functions that read the database and return results.
The rules are the same as the frontend prototype: a mentor is eligible when verified, with a free place,
and the student has no open match. The score is out of 100: topics 70 + experience 30."""
from constants import (DEFAULT_CAPACITY, EXPERIENCE_CAP_YEARS, EXPERIENCE_WEIGHT, TOPIC_WEIGHT)
from models import Match, MentorProfile, StudentProfile, names_of

OPEN = ["proposed", "active"]  # a match in one of these states uses a mentor's place


def places_used(mentor_id):
    query = Match.query.filter(Match.mentor_id == mentor_id, Match.status.in_(OPEN))  # in_ means "is one of"
    return query.count()


def places_max(mentor):
    if mentor.max_students:
        return mentor.max_students
    return DEFAULT_CAPACITY


def has_open_match(student_id):
    query = Match.query.filter(Match.student_id == student_id, Match.status.in_(OPEN))
    return query.count() > 0


def eligibility_error(student, mentor):
    """Returns the reason this pair may not be proposed, or None when it may."""
    if mentor.profile_status != "verified":
        return "The mentor is not verified yet."
    if places_used(mentor.id) >= places_max(mentor):
        return "This mentor has no free places."
    if has_open_match(student.id):
        return "This student already has an open match."
    if not student.looking_for_mentor:
        return "This student is not looking for a mentor right now."
    return None


def shared_topics(student, mentor):
    """The topic names that both have, in A to Z order."""
    mentor_names = names_of(mentor.topics)
    shared = []
    for name in names_of(student.topics):
        if name in mentor_names:
            shared.append(name)
    shared.sort()
    return shared


def topic_points(student, mentor):
    """Up to 70 points: the share of the student's topics that the mentor covers."""
    wanted = len(student.topics)
    if wanted == 0:
        return 0
    shared = len(shared_topics(student, mentor))
    return round(TOPIC_WEIGHT * shared / wanted)


def experience_points(years):
    """Up to 30 points. More than 10 years does not add more."""
    counted_years = min(years, EXPERIENCE_CAP_YEARS)  # min picks the smaller number
    return round(EXPERIENCE_WEIGHT * counted_years / EXPERIENCE_CAP_YEARS)


def score_pair(student, mentor):
    """Returns {'total': 0-100, 'reasons': [...]} for one student and one mentor."""
    years = mentor.experience_years
    if years is None:
        years = 0

    total = topic_points(student, mentor) + experience_points(years)

    shared = shared_topics(student, mentor)
    if len(shared) > 0:
        topic_reason = "Shared topics: " + ", ".join(shared)
    else:
        topic_reason = "No shared topics"

    maximum = places_max(mentor)
    free = max(0, maximum - places_used(mentor.id))  # max: never show less than 0

    reasons = [topic_reason, f"{years} years of experience", f"{free} of {maximum} places free"]
    return {"total": total, "reasons": reasons}


def get_score(result):
    """Used for sorting: tells sort() which number to compare."""
    return result["score"]


def recommend(student, limit=3):
    """The best eligible mentors for one student, highest score first."""
    results = []
    for mentor in MentorProfile.query.all():
        if eligibility_error(student, mentor) is not None:
            continue  # this mentor may not be proposed
        score = score_pair(student, mentor)
        results.append({"mentor_id": mentor.id, "mentor_name": mentor.user.full_name, "score": score["total"],
                        "reasons": score["reasons"]})
    results.sort(key=get_score, reverse=True)  # reverse=True: biggest first
    return results[:limit]  # the first "limit" items


def waiting_students():
    """Students who are looking for a mentor and have no proposed or active match."""
    waiting = []
    for student in StudentProfile.query.all():
        if student.looking_for_mentor and not has_open_match(student.id):
            waiting.append(student)
    return waiting
