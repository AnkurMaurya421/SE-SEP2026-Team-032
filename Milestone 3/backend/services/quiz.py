"""Level quiz: turns a student's answers for one topic into beginner, intermediate or advanced, and saves it."""
from constants import QUIZ_LEVELS, QUIZ_QUESTIONS
from database import db
from models import QuizResult, now
from validators import is_whole_number


def level_for(score):
    """QUIZ_LEVELS is a list of pairs (highest score, level name), from low to high."""
    for highest_score, level_name in QUIZ_LEVELS:
        if score <= highest_score:
            return level_name
    return "advanced"


def check_answers(answers):
    """answers must be one whole number (0, 1 or 2) for every question. Returns an error message or None."""
    if not isinstance(answers, list) or len(answers) != len(QUIZ_QUESTIONS):
        return f"answers must be a list of {len(QUIZ_QUESTIONS)} numbers."
    for position in range(len(answers)):  # position is 0, 1, 2...
        answer = answers[position]
        number_of_options = len(QUIZ_QUESTIONS[position]["options"])
        if not is_whole_number(answer) or answer < 0 or answer >= number_of_options:
            return "Each answer must be 0, 1 or 2."
    return None


def save_result(student, topic, answers):
    """One result per student and topic: taking the quiz again replaces the old one."""
    result = QuizResult.query.filter_by(student_id=student.id, topic=topic).first()
    if result is None:
        result = QuizResult(student=student, topic=topic)
        db.session.add(result)
    result.score = sum(answers)  # sum() adds all the numbers in a list
    result.level = level_for(result.score)
    result.taken_at = now()
    return result
