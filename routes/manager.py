"""Manager pages."""
from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)

from models import LeaveRequest, User, db
from models.leave import STATUSES, validate_rejection_reason
from routes.auth import role_required

bp = Blueprint("manager", __name__, url_prefix="/manager")


def _redirect_after_action(leave_id):
    if request.form.get("from") == "details":
        return redirect(url_for("manager.leave_details", leave_id=leave_id))
    return redirect(url_for("manager.dashboard"))


@bp.route("/dashboard")
@role_required("manager")
def dashboard():
    status = request.args.get("status", "")
    employee_id = request.args.get("employee", type=int)

    employees = User.query.filter_by(role="employee").order_by(User.name).all()
    pending = (
        LeaveRequest.query.filter_by(status="Pending")
        .order_by(LeaveRequest.applied_at.asc())
        .all()
    )

    history_query = LeaveRequest.query
    if status in STATUSES:
        history_query = history_query.filter_by(status=status)
    else:
        status = ""
    if employee_id:
        history_query = history_query.filter_by(user_id=employee_id)
    all_requests = history_query.order_by(LeaveRequest.applied_at.desc()).all()

    stats = {
        "employees": len(employees),
        "pending": len(pending),
        "approved": LeaveRequest.query.filter_by(status="Approved").count(),
        "rejected": LeaveRequest.query.filter_by(status="Rejected").count(),
    }
    return render_template(
        "manager_dashboard.html",
        stats=stats,
        employees=employees,
        pending=pending,
        all_requests=all_requests,
        statuses=STATUSES,
        selected_status=status,
        selected_employee=employee_id,
    )


@bp.route("/leaves/<int:leave_id>")
@role_required("manager")
def leave_details(leave_id):
    leave = db.session.get(LeaveRequest, leave_id)
    if leave is None:
        abort(404)
    return render_template("leave_details.html", leave=leave, can_review=True)


@bp.route("/leaves/<int:leave_id>/approve", methods=["POST"])
@role_required("manager")
def approve_leave(leave_id):
    leave = db.session.get(LeaveRequest, leave_id)
    if leave is None:
        abort(404)
    try:
        leave.approve()
        flash(f"Leave request #{leave.id} approved.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return _redirect_after_action(leave_id)


@bp.route("/leaves/<int:leave_id>/reject", methods=["POST"])
@role_required("manager")
def reject_leave(leave_id):
    leave = db.session.get(LeaveRequest, leave_id)
    if leave is None:
        abort(404)
    reason, error = validate_rejection_reason(request.form.get("rejection_reason"))
    if error:
        flash(error, "danger")
        return redirect(url_for("manager.leave_details", leave_id=leave_id))
    try:
        leave.reject(reason)
        flash(f"Leave request #{leave.id} rejected.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return _redirect_after_action(leave_id)
