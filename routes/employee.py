"""Employee pages."""
from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)

from models import LeaveRequest, db
from models.leave import LEAVE_TYPES, STATUSES, validate_leave_data
from models.leave_balance import BALANCE_COLUMNS
from routes.auth import get_current_user, role_required

bp = Blueprint("employee", __name__, url_prefix="/employee")


def _balance_cards(user):
    balance = user.get_or_create_balance()
    cards = []
    for leave_type in LEAVE_TYPES:
        cards.append(
            {
                "type": leave_type,
                "balance": balance.get(leave_type),
                "pending": LeaveRequest.pending_days(user.id, leave_type),
            }
        )
    return cards


@bp.route("/dashboard")
@role_required("employee")
def dashboard():
    user = get_current_user()
    requests_ = user.leave_requests
    stats = {
        status: sum(1 for r in requests_ if r.status == status) for status in STATUSES
    }
    return render_template(
        "employee_dashboard.html",
        cards=_balance_cards(user),
        stats=stats,
        recent=requests_[:5],
    )


@bp.route("/apply", methods=["GET", "POST"])
@role_required("employee")
def apply_leave():
    user = get_current_user()
    form = {"leave_type": "", "start_date": "", "end_date": "", "reason": ""}

    if request.method == "POST":
        form = {
            "leave_type": request.form.get("leave_type", ""),
            "start_date": request.form.get("start_date", ""),
            "end_date": request.form.get("end_date", ""),
            "reason": request.form.get("reason", ""),
        }
        data, errors = validate_leave_data(
            user,
            form["leave_type"],
            form["start_date"],
            form["end_date"],
            form["reason"],
        )
        if errors:
            for message in errors:
                flash(message, "danger")
            return (
                render_template(
                    "apply_leave.html",
                    form=form,
                    cards=_balance_cards(user),
                    leave_types=LEAVE_TYPES,
                ),
                400,
            )

        leave = LeaveRequest(user_id=user.id, status="Pending", **data)
        db.session.add(leave)
        db.session.commit()
        flash(
            f"Leave request submitted for {leave.days} working day(s). "
            "It is now pending approval.",
            "success",
        )
        return redirect(url_for("employee.leave_history"))

    return render_template(
        "apply_leave.html",
        form=form,
        cards=_balance_cards(user),
        leave_types=LEAVE_TYPES,
    )


@bp.route("/history")
@role_required("employee")
def leave_history():
    user = get_current_user()
    status = request.args.get("status", "")
    query = LeaveRequest.query.filter_by(user_id=user.id)
    if status in STATUSES:
        query = query.filter_by(status=status)
    else:
        status = ""
    leaves = query.order_by(LeaveRequest.applied_at.desc()).all()
    return render_template(
        "leave_history.html", leaves=leaves, statuses=STATUSES, selected_status=status
    )


@bp.route("/leaves/<int:leave_id>")
@role_required("employee")
def leave_details(leave_id):
    user = get_current_user()
    leave = db.session.get(LeaveRequest, leave_id)
    if leave is None or leave.user_id != user.id:
        abort(404)
    return render_template("leave_details.html", leave=leave, can_review=False)
