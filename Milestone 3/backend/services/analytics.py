"""Numbers for the admin dashboard (US-C07). Everything is counted from the tables; nothing is stored separately."""
from models import Feedback, MentorProfile
from services.checkins import active_check_ins
from services.matching import places_max, places_used


def percent(part, whole):
    """part out of whole, as a whole number from 0 to 100. Gives 0 when whole is 0 (we cannot divide by 0)."""
    if whole == 0:
        return 0
    return round(100 * part / whole)


def pulse_summary():
    """How the weekly check-ins of active matches are going. Only check-ins that are due or older count."""
    asked = 0
    answered = 0
    # one counter for each verdict
    verdict_counts = {"on track": 0, "watch": 0, "needs attention": 0}

    for checkin in active_check_ins():
        if checkin.state() == "upcoming":
            continue  # "continue" skips to the next check-in
        asked = asked + 1
        if checkin.submitted_at is None:
            continue
        answered = answered + 1
        if checkin.review_verdict in verdict_counts:
            verdict_counts[checkin.review_verdict] += 1  # += 1 means "add one"

    return {
        "asked": asked,
        "answered": answered,
        "response_rate": percent(answered, asked),
        "on_track": verdict_counts["on track"],
        "watch": verdict_counts["watch"],
        "needs_attention": verdict_counts["needs attention"],
        "unanswered": asked - answered,
    }


def feedback_summary():
    """How many ratings there are, their average, and how many of each star."""
    rows = Feedback.query.all()

    average = None  # there is no average when nobody has rated yet
    if len(rows) > 0:
        total_of_ratings = 0
        for row in rows:
            total_of_ratings += row.rating
        average = round(total_of_ratings / len(rows), 1)  # 1 digit after the point

    counts = []
    for star in [5, 4, 3, 2, 1]:
        counts.append({"rating": star, "count": count_rating(rows, star)})

    return {"total": len(rows), "average": average, "counts": counts}


def count_rating(rows, star):
    count = 0
    for row in rows:
        if row.rating == star:
            count += 1
    return count


def capacity_summary():
    """Places in use across the verified mentors, and one row per mentor."""
    rows = []
    total_used = 0
    total_places = 0
    for mentor in MentorProfile.query.filter_by(profile_status="verified").all():
        used = places_used(mentor.id)
        maximum = places_max(mentor)
        rows.append({"mentor_id": mentor.id, "mentor_name": mentor.user.full_name, "used": used, "max": maximum})
        total_used += used
        total_places += maximum

    return {"rows": rows, "used": total_used, "places": total_places, "percent": percent(total_used, total_places)}
