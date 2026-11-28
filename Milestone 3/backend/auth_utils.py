"""Passwords, login tokens and the role checks that protect every route (US-C06).
The check happens here on the server, so hiding a link in the frontend is never the only protection.

Words used in this file:
  hash       a scrambled form of a password. We store the hash, never the password itself.
  token      a signed text the user gets after login and sends with every later request.
  decorator  a line such as @login_required above a function. It runs a check before the function."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from database import db
from models import User
from responses import error


def hash_password(password):
    method = current_app.config["PASSWORD_HASH_METHOD"]
    return generate_password_hash(password, method=method)


def password_matches(user, password):
    """True when the typed password gives the same hash as the stored one."""
    return check_password_hash(user.password_hash, password)


def make_token(user):
    """Creates the login token. It stops working after TOKEN_HOURS hours."""
    hours = current_app.config["TOKEN_HOURS"]
    expires = datetime.utcnow() + timedelta(hours=hours)
    token_content = {"user_id": user.id, "role": user.role, "exp": expires}
    return jwt.encode(token_content, current_app.config["SECRET_KEY"], algorithm="HS256")


def user_from_request():
    """Reads the header 'Authorization: Bearer <token>' and returns the User.
    Returns None if the token is missing, wrong or too old."""
    header = request.headers.get("Authorization", "")
    start = "Bearer "
    if not header.startswith(start):
        return None
    token = header[len(start):]  # the text after "Bearer "

    try:
        token_content = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:  # the token was changed, is nonsense, or has expired
        return None

    user = db.session.get(User, token_content["user_id"])
    if user is None or not user.is_active:
        return None
    return user


def login_required(route_function):
    """Decorator: the caller must be logged in, otherwise the answer is 401.

    Python gives this function the route function. We return a new function that first checks the login
    and then calls the route function. The logged-in user is saved in g.user for the route to use."""

    @wraps(route_function)  # keeps the original function name, which Flask needs
    def check_then_run(*args, **kwargs):  # *args and **kwargs mean "whatever values the route receives"
        user = user_from_request()
        if user is None:
            return error("Please log in first.", 401)
        g.user = user
        return route_function(*args, **kwargs)

    return check_then_run


def role_required(*allowed_roles):
    """Decorator with a setting, for example @role_required("admin") or @role_required("student", "mentor").
    401 if not logged in, 403 if logged in with a role that is not allowed.

    It has one more layer than login_required: the outer function receives the roles,
    the middle function receives the route function, the inner function does the check."""

    def decorator(route_function):

        @wraps(route_function)
        def check_then_run(*args, **kwargs):
            user = user_from_request()
            if user is None:
                return error("Please log in first.", 401)
            if user.role not in allowed_roles:
                return error("You are not allowed to do this.", 403)
            g.user = user
            return route_function(*args, **kwargs)

        return check_then_run

    return decorator
