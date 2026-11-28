"""Mentorship Pulse review (US-C07 health of a mentorship). Reads one check-in answer and decides whether the admin must look.
It only flags. It never changes a match. The rules always run; the AI (if switched on) can only make the verdict worse, never better."""
from constants import LOW_RATING, VERDICTS, WORRYING_WORDS
from services.ai import ask_json

AI_INSTRUCTIONS = (
    "You review one weekly check-in about a mentoring relationship between a student and a mentor. "
    "Reply with JSON only: {\"verdict\": \"on track\" | \"watch\" | \"needs attention\", \"reason\": \"one short sentence\"}. "
    "Use 'needs attention' for conflict, no contact, disrespect or a very unhappy answer; 'watch' for mild worry; "
    "otherwise 'on track'.")


def worrying_words_in(comment):
    """Which words from our list appear in the comment."""
    if comment is None:
        comment = ""
    text = comment.lower()  # lower() so that "Rude" and "rude" are the same
    found = []
    for word in WORRYING_WORDS:
        if word in text:
            found.append(word)
    return found


def rule_review(rating, comment):
    """Returns two things: the level and a list of reasons. level 0 = on track, 1 = watch, 2 = needs attention."""
    level = 0
    reasons = []

    if rating <= LOW_RATING:
        level = 2
        reasons.append(f"The rating of {rating}/5 is low")
    elif rating == 3:
        level = 1
        reasons.append("The rating of 3/5 is middling")

    words_found = worrying_words_in(comment)
    if len(words_found) > 0:
        level = max(level, 1)  # at least "watch", and never lower than it already is
        reasons.append("The comment mentions: " + ", ".join(words_found))

    return level, reasons


def ask_ai_about(checkin):
    question = {"rating": checkin.rating, "comment": checkin.comment, "week": checkin.week,
                "written_by": checkin.by_role}
    return ask_json(AI_INSTRUCTIONS, question)


def review_check_in(checkin):
    """Fills in the review fields of an answered check-in."""
    # step 1: our own rules
    level, reasons = rule_review(checkin.rating, checkin.comment)
    if len(reasons) > 0:
        reason = ". ".join(reasons) + "."
    else:
        reason = "The rating is good and the comment shows no worry."
    source = "rules"

    # step 2: the AI, if it is on. It may only raise the level, never lower it.
    answer = ask_ai_about(checkin)
    if answer is not None and answer.get("verdict") in VERDICTS:
        ai_level = VERDICTS.index(answer["verdict"])  # index() gives the position in the list: 0, 1 or 2
        if ai_level >= level:
            level = ai_level
            source = "ai"
            ai_reason = answer.get("reason")
            if ai_reason:
                reason = str(ai_reason)
            reason = reason[:300]  # keep at most 300 characters

    # step 3: save the result
    checkin.review_verdict = VERDICTS[level]
    checkin.review_reason = reason
    checkin.review_source = source
    if level > 0:
        checkin.review_status = "open"  # the admin must look at it
    else:
        checkin.review_status = "ok"
