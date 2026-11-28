"""Smart Match. Ranks the eligible mentors for one student by reading what the student and the mentors wrote.
Total score (0 to 100) = 60% text fit + 40% rule score (topics and experience, from services/matching.py).
The text fit comes from OpenAI when it is switched on; otherwise from shared keywords (the fallback)."""
import re

from constants import SMART_MAX_KEYWORDS, SMART_RULE_WEIGHT, SMART_TEXT_WEIGHT
from models import MentorProfile, names_of
from services.ai import ask_json
from services.matching import eligibility_error, get_score, score_pair

# Very common words. They say nothing about what a person needs, so we ignore them.
# split() cuts the long text at every space and gives a list of words.
STOP_WORDS = (
    "i a an and are as at be been but by can do for from get has have help how in into is it its me my need needs of on or our "
    "so that the their them then there these this to want wants was we what when which who will with would you your am about "
    "also very much more most like any all some such than too").split()

AI_INSTRUCTIONS = (
    "You help an admin match a student with mentors. For every mentor, judge how well the mentor's text fits what the student "
    "needs. Reply with JSON only: {\"results\": [{\"mentor_id\": 1, \"fit\": 0-100, \"reason\": \"one short sentence\"}]}. "
    "Give one result for every mentor you were sent.")


# ---------------- Part 1: our own simple text comparison (used when the AI is off) ----------------

def stem(word):
    """Cuts common endings, so that "coding" and "codes" can count as the same word.
    re.sub(pattern, "", word) removes the pattern; the $ means "only at the end of the word"."""
    if len(word) > 5:
        return re.sub(r"(ing|ed|es|s)$", "", word)
    return re.sub(r"s$", "", word)


def keywords(text):
    """The meaningful words of a text, as a dictionary: {short form: word as written}."""
    if text is None:
        text = ""
    all_words = re.findall(r"[a-z]+", text.lower())  # every run of letters is one word
    found = {}
    for word in all_words:
        if len(word) < 3 or word in STOP_WORDS:
            continue
        short_form = stem(word)
        if short_form not in found:  # keep the first spelling we saw
            found[short_form] = word
    return found


def student_text(student):
    return f"{student.needs_text or ''} {student.career_goals or ''}"


def mentor_text(mentor):
    return f"{mentor.skills_text or ''} {mentor.bio or ''} {mentor.qualifications or ''}"


def keyword_fit(student, mentor):
    """Returns two things: a fit from 0 to 100, and a reason in words."""
    student_words = keywords(student_text(student))
    mentor_words = keywords(mentor_text(mentor))

    shared = []
    for short_form in student_words:
        if short_form in mentor_words:
            shared.append(student_words[short_form])

    # 5 shared words already count as a full fit (fewer if the student wrote fewer words)
    words_needed = min(len(student_words), SMART_MAX_KEYWORDS)
    if words_needed == 0:
        fit = 0
    else:
        fit = min(1, len(shared) / words_needed) * 100

    if len(shared) > 0:
        reason = "Both describe: " + ", ".join(shared[:6])  # show at most 6 words
    else:
        reason = "The free-text answers share no wording"
    return round(fit), reason


# ---------------- Part 2: asking the AI ----------------

def student_for_ai(student):
    """Only what the AI needs to know. No name or email is sent."""
    return {"needs": student.needs_text, "goals": student.career_goals, "topics": names_of(student.topics),
            "levels": student.quiz_levels()}


def mentor_for_ai(mentor):
    return {"mentor_id": mentor.id, "bio": mentor.bio, "skills": mentor.skills_text,
            "qualifications": mentor.qualifications, "topics": names_of(mentor.topics)}


def read_ai_result(item):
    """Checks one result from the AI. Returns (mentor_id, fit, reason), or None if it is not usable."""
    if not isinstance(item, dict):
        return None
    mentor_id = item.get("mentor_id")
    fit = item.get("fit")
    if not isinstance(mentor_id, int):
        return None
    if isinstance(fit, bool) or not isinstance(fit, (int, float)):  # int or float means "a number"
        return None
    fit = round(fit)
    fit = max(0, min(100, fit))  # force the number to stay between 0 and 100
    reason = str(item.get("reason") or "")[:300]
    return mentor_id, fit, reason


def ai_fits(student, mentors):
    """Asks the AI once for all mentors.
    Returns {mentor_id: {"fit": ..., "reason": ...}}. The dictionary is empty when the AI is off or failed."""
    mentor_list = []
    for mentor in mentors:
        mentor_list.append(mentor_for_ai(mentor))
    answer = ask_json(AI_INSTRUCTIONS, {"student": student_for_ai(student), "mentors": mentor_list})

    fits = {}
    if answer is None or not isinstance(answer.get("results"), list):
        return fits
    for item in answer["results"]:
        result = read_ai_result(item)
        if result is not None:
            mentor_id, fit, reason = result
            fits[mentor_id] = {"fit": fit, "reason": reason}
    return fits


# ---------------- Part 3: putting it together ----------------

def level_reasons(student):
    """A list with one line about the student's quiz levels, or an empty list."""
    lines = []
    for topic, level in student.quiz_levels().items():  # items() gives each key with its value
        lines.append(f"{topic}: {level}")
    if len(lines) == 0:
        return []
    return ["Student level (quiz): " + ", ".join(lines)]


def eligible_mentors(student):
    mentors = []
    for mentor in MentorProfile.query.all():
        if eligibility_error(student, mentor) is None:
            mentors.append(mentor)
    return mentors


def score_one_mentor(student, mentor, fits):
    """Builds the result for one mentor. Uses the AI's fit if we have it, else our own."""
    rule = score_pair(student, mentor)

    if mentor.id in fits:
        fit = fits[mentor.id]["fit"]
        reason = fits[mentor.id]["reason"]
        source = "ai"
    else:
        fit, reason = keyword_fit(student, mentor)
        source = "rules"

    # 60 parts text fit and 40 parts rule score, out of 100
    total = round((SMART_TEXT_WEIGHT * fit + SMART_RULE_WEIGHT * rule["total"]) / 100)

    reasons = [reason] + rule["reasons"] + level_reasons(student)  # + joins lists
    return {"mentor_id": mentor.id, "mentor_name": mentor.user.full_name, "score": total, "text_fit": fit,
            "rule_score": rule["total"], "source": source, "reasons": reasons}


def smart_recommend(student, limit=3):
    """Returns two things: the best mentors, and 'ai' or 'rules' to say what scored them."""
    mentors = eligible_mentors(student)

    fits = {}
    if len(mentors) > 0:  # no need to ask the AI about nobody
        fits = ai_fits(student, mentors)

    results = []
    for mentor in mentors:
        results.append(score_one_mentor(student, mentor, fits))

    overall_source = "rules"
    for result in results:
        if result["source"] == "ai":
            overall_source = "ai"

    results.sort(key=get_score, reverse=True)
    return results[:limit], overall_source
