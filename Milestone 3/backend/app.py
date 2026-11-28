"""Starts the backend:  python app.py   (it then listens on http://localhost:5001)

Read this file first. It shows how the whole backend is put together."""
from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from database import db
from routes import admin, auth, checkins, feedback, jobs, matches, notifications, profiles, quiz
from seed import seed_basics, seed_demo


# A "blueprint" is a group of routes. Each file in the routes folder has one, named bp.
ROUTE_FILES = [auth, profiles, admin, matches, feedback, checkins, jobs, notifications, quiz]


def create_app(config=Config):
    """Builds the Flask app. The tests call this with TestConfig instead of Config."""
    app = Flask(__name__)
    app.config.from_object(config)  # copies the settings from the config class into app.config
    allow_frontend_to_call_us(app)
    db.init_app(app)  # connects the database object to this app

    for route_file in ROUTE_FILES:
        app.register_blueprint(route_file.bp)

    add_health_route(app)
    add_error_answers(app)
    prepare_database(app)
    return app


def allow_frontend_to_call_us(app):
    """Browsers block calls from another website unless the server allows it (this is called CORS).
    CORS_ORIGINS is text such as "https://a.com, https://b.com"; we turn it into a list."""
    allowed_websites = []
    for website in app.config["CORS_ORIGINS"].split(","):
        allowed_websites.append(website.strip())  # strip() removes the spaces around the text
    CORS(app, origins=allowed_websites)


def add_health_route(app):
    """A very small route that only says the server is running."""

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})


def add_error_answers(app):
    """Makes Flask's own errors look like all our other errors: {"error": "message"}."""

    @app.errorhandler(404)
    def not_found(problem):
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(405)
    def wrong_method(problem):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(500)
    def server_error(problem):
        db.session.rollback()  # throw away half-done database changes, so the next request starts clean
        return jsonify({"error": "Something went wrong on the server."}), 500


def prepare_database(app):
    """Creates any missing tables and the starting rows."""
    with app.app_context():  # database work outside a request needs the "app context"
        db.create_all()
        seed_basics()
        if app.config["LOAD_DEMO_DATA"]:
            seed_demo()


# This part runs only when you type "python app.py", not when another file imports this one.
if __name__ == "__main__":
    application = create_app()
    application.run(port=5001, debug=True)
