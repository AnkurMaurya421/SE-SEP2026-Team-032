"""Every error from the API has the same shape: {"error": "message"} with the right status code."""
from flask import jsonify, request


def error(message, status=400):
    """Returns two things: the JSON answer and the HTTP status code (400 means "bad input")."""
    return jsonify({"error": message}), status


def json_body():
    """Returns the JSON object the client sent, as a Python dictionary.
    If the client sent nothing, or a list, or a number, we return an empty dictionary.
    Then the field checks answer with a clear 400 instead of the server crashing."""
    data = request.get_json(silent=True)  # silent=True: give None instead of failing on bad JSON
    if isinstance(data, dict):
        return data
    return {}


def to_dict_list(rows):
    """Turns a list of database rows into a list of dictionaries, ready to send as JSON."""
    result = []
    for row in rows:
        result.append(row.to_dict())
    return result
