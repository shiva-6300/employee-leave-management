"""Employee Leave Management System - application entry point.

Run with:  python app.py
"""
import secrets
import sys

from flask import Flask, jsonify, render_template, request, session
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from models import LeaveBalance, User, db
from routes import api, auth, employee, manager

ERROR_MESSAGES = {
    400: "Bad request. The form may have expired - please go back and try again.",
    403: "You do not have permission to access this resource.",
    404: "The page you are looking for could not be found.",
    405: "That method is not allowed for this URL.",
    500: "Something went wrong on our side. Please try again later.",
}


def seed_default_data():
    """Create demo users on an empty database (same data as database.sql)."""
    if User.query.first() is not None:
        return

    people = [
        ("Priya Sharma", "manager@company.com", "Manager@123", "manager", None),
        ("John Doe", "employee@company.com", "Employee@123", "employee", (10, 10, 15)),
        ("Anita Rao", "anita@company.com", "Employee@123", "employee", (12, 8, 15)),
        ("Rahul Verma", "rahul@company.com", "Employee@123", "employee", (12, 10, 15)),
    ]
    for name, email, password, role, balances in people:
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        if balances:
            user.balance = LeaveBalance(
                casual_leave=balances[0],
                sick_leave=balances[1],
                earned_leave=balances[2],
            )
        db.session.add(user)
    db.session.commit()
    print("Seeded demo users (see README for credentials).")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(employee.bp)
    app.register_blueprint(manager.bp)
    app.register_blueprint(api.bp)

    # ---------------------------------------------------------- CSRF (forms)
    @app.before_request
    def csrf_protect():
        """Check the CSRF token on every HTML form POST (the JSON API is exempt)."""
        if request.method == "POST" and not request.path.startswith("/api/"):
            expected = session.get("_csrf_token")
            sent = request.form.get("csrf_token")
            if not expected or not sent or not secrets.compare_digest(expected, sent):
                return handle_error(400)

    @app.context_processor
    def inject_globals():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(16)
        return {
            "csrf_token": session["_csrf_token"],
            "current_user": auth.get_current_user(),
        }

    # -------------------------------------------------------------- filters
    @app.template_filter("fmt_date")
    def fmt_date(value):
        return value.strftime("%d %b %Y") if value else "-"

    @app.template_filter("fmt_datetime")
    def fmt_datetime(value):
        return value.strftime("%d %b %Y, %H:%M") if value else "-"

    # ------------------------------------------------------ error handling
    def handle_error(error_or_code):
        code = error_or_code if isinstance(error_or_code, int) else getattr(
            error_or_code, "code", 500
        )
        if code not in ERROR_MESSAGES:
            code = 500
        if code == 500:
            db.session.rollback()
        message = ERROR_MESSAGES[code]
        if request.path.startswith("/api/"):
            return jsonify({"error": message}), code
        return render_template("error.html", code=code, message=message), code

    for code in ERROR_MESSAGES:
        app.register_error_handler(code, handle_error)

    # ------------------------------------------------------------ database
    with app.app_context():
        try:
            db.create_all()
            seed_default_data()
        except SQLAlchemyError as exc:
            print("\nCould not connect to the database.")
            print("Check your .env settings and make sure MySQL is running.")
            print(f"Details: {exc.__class__.__name__}: {str(exc).splitlines()[0]}\n")
            sys.exit(1)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=app.config["PORT"], debug=app.config["DEBUG"])
