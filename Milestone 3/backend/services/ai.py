"""The one place that talks to OpenAI. Both AI features (Smart Match and Pulse review) call ask_json().
It returns a dictionary, or None when there is no key or anything goes wrong. The callers then use their simple rules,
so the platform keeps working without the AI."""
import json
import urllib.request

from flask import current_app

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def ai_is_on():
    """True when an OpenAI key has been set."""
    key = current_app.config["OPENAI_API_KEY"]
    return key != ""


def ask_json(instructions, data):
    """Sends the instructions and the data (a dictionary) to OpenAI.
    Returns the AI's answer as a dictionary, or None if there is no key or something went wrong."""
    if not ai_is_on():
        return None

    request = build_request(instructions, data)
    try:
        # timeout=20: stop waiting after 20 seconds
        with urllib.request.urlopen(request, timeout=20) as response:
            reply_text = response.read().decode("utf-8")  # the raw bytes, turned into text
        reply = json.loads(reply_text)  # json.loads turns JSON text into Python data
        answer_text = reply["choices"][0]["message"]["content"]  # where OpenAI puts the AI's words
        answer = json.loads(answer_text)  # we asked the AI to answer in JSON
    except Exception:  # no network, wrong key, bad JSON...
        return None

    if not isinstance(answer, dict):
        return None
    return answer


def build_request(instructions, data):
    """Prepares the web request for OpenAI: what we send, where, and with which key."""
    message_to_send = {
        "model": current_app.config["OPENAI_MODEL"],
        "response_format": {"type": "json_object"},  # the answer must be JSON
        "temperature": 0.2,  # low number = steady answers, less creative
        "messages": [
            {"role": "system", "content": instructions},  # how the AI should behave
            {"role": "user", "content": json.dumps(data)},  # json.dumps turns Python data into JSON text
        ],
    }
    headers = {
        "Authorization": "Bearer " + current_app.config["OPENAI_API_KEY"],
        "Content-Type": "application/json",
    }
    body = json.dumps(message_to_send).encode("utf-8")  # web requests send bytes, not text
    return urllib.request.Request(OPENAI_URL, data=body, headers=headers, method="POST")
