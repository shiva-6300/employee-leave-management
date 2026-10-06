"""JSON REST API (session based - log in with POST /api/login first)."""
from functools import wraps

from flask import Blueprint, jsonify, request, session

from models import LeaveRequest, User, db
from models.leave import STATUSES, validate_leave_data, validate_rejection_reason
from routes.auth import EMAIL_RE, get_current_user

bp = Blueprint("api", __name__, url_prefix="/api")


def error(message, status, **extra):
    return jsonify({"error": message, **extra}), status


def api_auth(role=None):
    """Require a logged-in session (and optionally a role). Returns JSON errors."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if user is None:
                return error(
                    "Authentication required. Log in with POST /api/login.", 401
                )
            if role and user.role != role:
                return error(f"This action requires the '{role}' role.", 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def json_body():
    """Return the JSON object in the request body or None if invalid."""
    if not request.is_json:
        return None
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------- auth
@bp.route("/login", methods=["POST"])
def login():
    data = json_body()
    if data is None:
        return error("Request body must be a JSON object (Content-Type: application/json).", 400)

    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not email or not isinstance(password, str) or not password:
        return error("Both 'email' and 'password' are required.", 400)
    if len(email) > 120 or not EMAIL_RE.match(email):
        return error("Please provide a valid email address.", 400)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return error("Invalid email or password.", 401)

    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["role"] = user.role
    return jsonify({"message": "Login successful.", "user": user.to_dict()}), 200


@bp.route("/logout", methods=["POST"])
@api_auth()
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."}), 200


# -------------------------------------------------------------------- leaves
@bp.route("/leaves", methods=["GET"])
@api_auth()
def list_leaves():
    user = get_current_user()
    query = LeaveRequest.query
    if user.role != "manager":
        query = query.filter_by(user_id=user.id)
    else:
        user_id = request.args.get("user_id", type=int)
        if user_id:
            query = query.filter_by(user_id=user_id)

    status = request.args.get("status")
    if status:
        if status not in STATUSES:
            return error(f"Invalid status. Use one of: {', '.join(STATUSES)}.", 400)
        query = query.filter_by(status=status)

    leaves = query.order_by(LeaveRequest.applied_at.desc()).all()
    return jsonify({"count": len(leaves), "leaves": [l.to_dict() for l in leaves]}), 200


@bp.route("/leaves", methods=["POST"])
@api_auth("employee")
def create_leave():
    data = json_body()
    if data is None:
        return error("Request body must be a JSON object (Content-Type: application/json).", 400)

    user = get_current_user()
    cleaned, errors = validate_leave_data(
        user,
        str(data.get("leave_type", "")),
        str(data.get("start_date", "")),
        str(data.get("end_date", "")),
        str(data.get("reason", "")),
    )
    if errors:
        return error("Validation failed.", 400, details=errors)

    leave = LeaveRequest(user_id=user.id, status="Pending", **cleaned)
    db.session.add(leave)
    db.session.commit()
    return jsonify({"message": "Leave request submitted.", "leave": leave.to_dict()}), 201


def _get_leave_or_404(leave_id):
    return db.session.get(LeaveRequest, leave_id)


@bp.route("/leaves/<int:leave_id>", methods=["GET"])
@api_auth()
def get_leave(leave_id):
    user = get_current_user()
    leave = _get_leave_or_404(leave_id)
    if leave is None:
        return error("Leave request not found.", 404)
    if user.role != "manager" and leave.user_id != user.id:
        return error("You can only view your own leave requests.", 403)
    return jsonify({"leave": leave.to_dict()}), 200


@bp.route("/leaves/<int:leave_id>/approve", methods=["PUT"])
@api_auth("manager")
def approve_leave(leave_id):
    leave = _get_leave_or_404(leave_id)
    if leave is None:
        return error("Leave request not found.", 404)
    try:
        leave.approve()
    except ValueError as exc:
        db.session.rollback()
        return error(str(exc), 409)
    return jsonify({"message": "Leave request approved.", "leave": leave.to_dict()}), 200


@bp.route("/leaves/<int:leave_id>/reject", methods=["PUT"])
@api_auth("manager")
def reject_leave(leave_id):
    leave = _get_leave_or_404(leave_id)
    if leave is None:
        return error("Leave request not found.", 404)

    data = json_body()
    if data is None:
        return error(
            "Request body must be JSON containing 'rejection_reason'.", 400
        )
    reason, problem = validate_rejection_reason(
        str(data.get("rejection_reason", data.get("reason", "")))
    )
    if problem:
        return error(problem, 400)

    try:
        leave.reject(reason)
    except ValueError as exc:
        db.session.rollback()
        return error(str(exc), 409)
    return jsonify({"message": "Leave request rejected.", "leave": leave.to_dict()}), 200


# ----------------------------------------------------------------- employees
@bp.route("/employees", methods=["GET"])
@api_auth("manager")
def list_employees():
    employees = User.query.filter_by(role="employee").order_by(User.name).all()
    return jsonify(
        {
            "count": len(employees),
            "employees": [e.to_dict(include_balance=True) for e in employees],
        }
    ), 200


@bp.route("/employees/<int:employee_id>", methods=["GET"])
@api_auth()
def get_employee(employee_id):
    user = get_current_user()
    if user.role != "manager" and user.id != employee_id:
        return error("You can only view your own profile.", 403)
    employee = db.session.get(User, employee_id)
    if employee is None or employee.role != "employee":
        return error("Employee not found.", 404)
    return jsonify({"employee": employee.to_dict(include_balance=True)}), 200
