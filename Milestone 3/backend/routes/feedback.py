"""Feedback and concerns about a match (US-S09, US-S10). Students and mentors write them; the admin reads them
and marks concerns resolved. Only the two people in a match can write about it."""
from flask import Blueprint, g, jsonify, request

import validators
from auth_utils import role_required
from database import db
from models import Concern, Feedback, Match, now
from responses import error, json_body, to_dict_list
from services.match_flow import pair_names
from services.my_matches import my_matches
from services.notifications import notify, notify_admins

bp = Blueprint("feedback", __name__, url_prefix="/api")


def own_match(match_id):
    """The match, if the logged-in student or mentor is part of it; otherwise None."""
    match = db.session.get(Match, match_id)
    if match is None:
        return None
    if match not in my_matches(g.user):
        return None
    return match


@bp.post("/matches/<int:match_id>/feedback")
@role_required("student", "mentor")
def give_feedback(match_id):
    """Body: {"rating": 1 to 5, "comments": "..."}. One per person per match, once the match is active or completed."""
    match = own_match(match_id)
    if match is None:
        return error("Match not found.", 404)
    data = json_body()
    problem = validators.check_feedback(data)
    if problem:
        return error(problem, 400)
    if match.status not in ("active", "completed"):
        return error("Feedback can be given once the match is active.", 409)
    earlier = Feedback.query.filter_by(match_id=match.id, author_id=g.user.id).first()
    if earlier is not None:
        return error("You have already given feedback on this match.", 409)
    comments = data.get("comments")
    if comments is None:
        comments = ""
    row = Feedback(match_id=match.id, author_id=g.user.id, rating=data["rating"], comments=comments.strip())
    db.session.add(row)
    db.session.commit()
    return jsonify({"feedback": row.to_dict()}), 201


@bp.get("/feedback/me")
@role_required("student", "mentor")
def my_feedback():
    rows = Feedback.query.filter_by(author_id=g.user.id).order_by(Feedback.id.desc()).all()
    return jsonify({"feedback": to_dict_list(rows)})


@bp.get("/admin/feedback")
@role_required("admin")
def all_feedback():
    """All feedback, newest first. Optional filter: ?match_id=1"""
    query = Feedback.query.order_by(Feedback.id.desc())
    match_id = request.args.get("match_id", type=int)
    if match_id:
        query = query.filter_by(match_id=match_id)
    return jsonify({"feedback": to_dict_list(query.all())})


@bp.post("/matches/<int:match_id>/concerns")
@role_required("student", "mentor")
def raise_concern(match_id):
    """Body: {"text": "..."}. The admins are told."""
    match = own_match(match_id)
    if match is None:
        return error("Match not found.", 404)
    data = json_body()
    problem = validators.check_concern(data)
    if problem:
        return error(problem, 400)
    row = Concern(match_id=match.id, raised_by=g.user.id, text=data["text"].strip())
    db.session.add(row)
    message = f"{g.user.full_name} ({g.user.role}) raised a concern about the match {pair_names(match)}."
    notify_admins(message, match.id)
    db.session.commit()
    return jsonify({"concern": row.to_dict()}), 201


@bp.get("/concerns/me")
@role_required("student", "mentor")
def my_concerns():
    rows = Concern.query.filter_by(raised_by=g.user.id).order_by(Concern.id.desc()).all()
    return jsonify({"concerns": to_dict_list(rows)})


@bp.get("/admin/concerns")
@role_required("admin")
def all_concerns():
    """All concerns, newest first. Optional filter: ?status=open|resolved"""
    status = request.args.get("status")
    if status:
        problem = validators.check_concern_status(status)
        if problem:
            return error(problem, 400)
    query = Concern.query.order_by(Concern.id.desc())
    if status:
        query = query.filter_by(status=status)
    return jsonify({"concerns": to_dict_list(query.all())})


@bp.patch("/admin/concerns/<int:concern_id>")
@role_required("admin")
def update_concern(concern_id):
    """Body: {"status": "resolved"}. The person who raised it is told."""
    row = db.session.get(Concern, concern_id)
    if row is None:
        return error("Concern not found.", 404)
    status = json_body().get("status")
    problem = validators.check_concern_status(status)
    if problem:
        return error(problem, 400)
    if status != row.status:  # nothing to do when the status stays the same
        change_concern_status(row, status)
    db.session.commit()
    return jsonify({"concern": row.to_dict()})


def change_concern_status(concern, new_status):
    concern.status = new_status
    if new_status == "resolved":
        concern.resolved_at = now()
        notify(concern.raised_by, "The admin marked your concern as resolved.", concern.match_id)
    else:
        concern.resolved_at = None  # opened again
