"""The matches of one student or mentor, as that person is allowed to see them (US-S07, US-M03)."""
from models import Match, MentorProfile, StudentProfile


def my_matches(user):
    """The matches of this student or mentor, newest first."""
    if user.role == "student":
        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        query = Match.query.filter_by(student_id=profile.id)
    else:
        profile = MentorProfile.query.filter_by(user_id=user.id).first()
        query = Match.query.filter_by(mentor_id=profile.id)
    return query.order_by(Match.id.desc()).all()  # desc: biggest id first


def with_other_person(match, user):
    """The match, plus the profile of the other person. Their email is shown only once the match is active."""
    if user.role == "student":
        other_profile = match.mentor
    else:
        other_profile = match.student

    other_person = other_profile.to_dict()
    if match.status not in ["active", "completed"]:
        del other_person["email"]  # del removes one item from a dictionary

    result = match.to_dict()
    result["other"] = other_person
    return result
