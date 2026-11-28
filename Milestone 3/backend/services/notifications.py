"""Notifications are rows in the database that each person sees inside the app. (Emails are in services/emailer.py.)"""
from database import db
from models import Notification, User


def notify(user_id, message, match_id=None):
    db.session.add(Notification(user_id=user_id, message=message, match_id=match_id))


def notify_admins(message, match_id=None):
    for admin in User.query.filter_by(role="admin").all():
        notify(admin.id, message, match_id)
