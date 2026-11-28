"""Helpers for the tests.

check() makes one API call, compares it with what we expect and records a row for the test-case table
(API being tested, inputs, expected output, actual output, result). conftest.py writes the table at the end of the run."""
import json

CASES = []  # one dict per check() call


def auth(token):
    """The header that tells the API who is calling. Empty when there is no token."""
    if not token:
        return {}
    return {"Authorization": "Bearer " + token}


def short(value, limit=160):
    """The value as text, cut off after "limit" characters so the table stays readable."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def hide_password(data):
    """A copy of the data with the password replaced by stars."""
    if isinstance(data, dict) and "password" in data:
        copy = dict(data)
        copy["password"] = "******"
        return copy
    return data


def check(client, method, url, status, case, json_body=None, token=None, role="", contains=None):
    """Calls the API and asserts that the status code is `status` and, if given, that `contains` is in the body.
    `case` is a short description of the test case; `role` says who is calling (for the table only)."""
    response = client.open(url, method=method, json=json_body, headers=auth(token))
    body = response.get_json(silent=True)
    actual_text = ""
    if body is not None:
        actual_text = json.dumps(body, ensure_ascii=False)

    passed = response.status_code == status
    if contains is not None and contains not in actual_text:
        passed = False

    record_case(method, url, status, case, json_body, role, contains, response.status_code, body, passed)
    # assert stops the test with this message when "passed" is False
    assert passed, f"{case}: expected status {status} and '{contains}', got {response.status_code} {actual_text}"
    return body


def record_case(method, url, status, case, json_body, role, contains, actual_status, body, passed):
    """Adds one row to the test-case table."""
    inputs = "no body"
    if json_body is not None:
        inputs = short(hide_password(json_body))
    if role:
        inputs = f"[{role}] " + inputs

    expected = f"{status}"
    if contains:
        expected = expected + f", body contains '{contains}'"

    shown_body = "(empty)"
    if body is not None:
        shown_body = short(body)

    result = "Fail"
    if passed:
        result = "Success"

    CASES.append({
        "api": f"{method} {url}", "case": case, "inputs": inputs, "expected": expected,
        "actual": f"{actual_status} {shown_body}", "result": result,
    })


# ---- small setup helpers (not recorded as test cases) ----

def register(client, email, role, name="Test User", password="secret1"):
    client.post("/api/auth/register", json={"full_name": name, "email": email, "password": password, "role": role})
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.get_json()["token"]


STUDENT_PROFILE = {
    "programme_level": "Diploma", "career_goals": "Move into data analytics", "skills": "Python, SQL",
    "needs_text": "I need help building a portfolio.", "mentoring_format": "Video call",
    "expected_duration": "3 months", "topics": ["Data Science", "Career Switching"],
}
MENTOR_PROFILE = {
    "qualifications": "PhD, Data Science", "experience_years": 12, "bio": "Leads an analytics team.",
    "skills_text": "I coach students on analytics careers.", "max_students": 3, "topics": ["Data Science", "Career Switching"],
}


def make_student(client, email="asha@ds.study.iitm.ac.in", name="Asha Verma", profile=None):
    """Registers a student, fills the profile and returns (token, student_id)."""
    token = register(client, email, "student", name)
    body = client.put("/api/students/me", json=profile or STUDENT_PROFILE, headers=auth(token)).get_json()
    return token, body["profile"]["student_id"]


def make_mentor(client, admin_token, email="meera@mentor.test", name="Dr. Meera Iyer", profile=None, verified=True):
    """Registers a mentor, fills the profile, optionally verifies them, and returns (token, mentor_id)."""
    token = register(client, email, "mentor", name)
    body = client.put("/api/mentors/me", json=profile or MENTOR_PROFILE, headers=auth(token)).get_json()
    mentor_id = body["profile"]["mentor_id"]
    client.post("/api/mentors/me/availability", json={"day_of_week": "Saturday", "start_time": "18:00", "end_time": "20:00"}, headers=auth(token))
    if verified:
        client.patch(f"/api/admin/mentors/{mentor_id}/status", json={"status": "verified"}, headers=auth(admin_token))
    return token, mentor_id
