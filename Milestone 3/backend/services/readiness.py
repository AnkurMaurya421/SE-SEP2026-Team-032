"""Readiness (US-S07 to US-S11): how ready a student's profile is for the admin to propose a mentor."""

CHECKS = [
    ("programme_level", "Programme level"),
    ("career_goals", "Career goals"),
    ("topics", "At least one topic"),
    ("skills", "Skills"),
    ("needs_text", "What you need from a mentor"),
    ("availability_note", "When you are available"),
]


def is_filled(student, field):
    """True when the student has written or chosen something for this field."""
    if field == "topics":
        return len(student.topics) > 0
    value = getattr(student, field)  # getattr(student, "skills") is the same as student.skills
    if value:
        return True
    return False


def readiness(student):
    """Returns {'items': [...], 'percent': 0-100, 'ready': bool}. 'ready' needs goals, level and a topic."""
    items = []
    done_count = 0
    for field, label in CHECKS:
        done = is_filled(student, field)
        items.append({"field": field, "label": label, "done": done})
        if done:
            done_count += 1

    percent = round(100 * done_count / len(items))
    ready = (is_filled(student, "programme_level")
             and is_filled(student, "career_goals")
             and is_filled(student, "topics"))

    return {"items": items, "percent": percent, "ready": ready, "looking_for_mentor": student.looking_for_mentor}
