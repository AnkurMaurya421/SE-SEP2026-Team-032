"""Shared pytest fixtures. Every test gets a fresh in-memory database."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # lets the tests import the backend modules

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from seed import ADMIN_EMAIL, ADMIN_PASSWORD  # noqa: E402
from tests import helpers  # noqa: E402


@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        yield app.test_client()


@pytest.fixture
def admin_token(client):
    response = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return response.get_json()["token"]


def table_row(number, case):
    """One line of the table. The | character separates columns, so it is replaced inside the text."""
    cells = [case["api"], case["case"], case["inputs"], case["expected"], case["actual"], case["result"]]
    safe_cells = []
    for cell in cells:
        safe_cells.append(cell.replace("|", "/"))
    return f"| {number} | " + " | ".join(safe_cells) + " |"


def pytest_sessionfinish(session, exitstatus):
    """pytest calls this once, after all tests. It writes the test-case table
    (API, inputs, expected output, actual output, result) into tests/test_cases.md."""
    if len(helpers.CASES) == 0:
        return

    rows = ["| # | API being tested | Test case | Inputs | Expected output | Actual output | Result |",
            "|---|---|---|---|---|---|---|"]
    passed = 0
    number = 0
    for case in helpers.CASES:
        number += 1
        rows.append(table_row(number, case))
        if case["result"] == "Success":
            passed += 1

    path = os.path.join(os.path.dirname(__file__), "test_cases.md")
    with open(path, "w") as output_file:
        output_file.write(f"# Test cases\n\n{passed} of {len(helpers.CASES)} test cases passed.\n\n" + "\n".join(rows) + "\n")
