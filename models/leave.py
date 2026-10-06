from datetime import date, datetime, timedelta

from sqlalchemy import func

from models import db, utcnow

LEAVE_TYPES = ("Casual", "Sick", "Earned")
STATUSES = ("Pending", "Approved", "Rejected")
MAX_LEAVE_SPAN_DAYS = 90
MIN_REASON_LENGTH = 5
MAX_REASON_LENGTH = 500
MAX_REJECTION_LENGTH = 300


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type = db.Column(db.Enum(*LEAVE_TYPES, name="leave_type"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(*STATUSES, name="leave_status"), nullable=False, default="Pending"
    )
    rejection_reason = db.Column(db.Text, nullable=True)
    applied_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    user = db.relationship("User", back_populates="leave_requests")

    @staticmethod
    def calculate_days(start, end):
        """Number of working days (Mon-Fri) between start and end, inclusive."""
        total = 0
        current = start
        while current <= end:
            if current.weekday() < 5:
                total += 1
            current += timedelta(days=1)
        return total

    @staticmethod
    def find_overlap(user_id, start, end):
        """Return an existing Pending/Approved request overlapping the range."""
        return LeaveRequest.query.filter(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status.in_(["Pending", "Approved"]),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        ).first()

    @staticmethod
    def pending_days(user_id, leave_type):
        """Days of the given type already reserved by pending requests."""
        total = (
            db.session.query(func.coalesce(func.sum(LeaveRequest.days), 0))
            .filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.leave_type == leave_type,
                LeaveRequest.status == "Pending",
            )
            .scalar()
        )
        return int(total or 0)

    # ---------------------------------------------------------------- workflow
    def approve(self):
        if self.status != "Pending":
            raise ValueError(f"This request is already {self.status.lower()}.")
        balance = self.user.get_or_create_balance()
        available = balance.get(self.leave_type)
        if self.days > available:
            raise ValueError(
                f"Cannot approve: employee only has {available} day(s) of "
                f"{self.leave_type} leave left."
            )
        balance.deduct(self.leave_type, self.days)
        self.status = "Approved"
        self.rejection_reason = None
        db.session.commit()

    def reject(self, reason):
        if self.status != "Pending":
            raise ValueError(f"This request is already {self.status.lower()}.")
        self.status = "Rejected"
        self.rejection_reason = reason
        db.session.commit()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "employee": {
                "id": self.user.id,
                "name": self.user.name,
                "email": self.user.email,
            },
            "leave_type": self.leave_type,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "days": self.days,
            "reason": self.reason,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<LeaveRequest {self.id} {self.leave_type} {self.status}>"


# ---------------------------------------------------------------- validation
def _parse_date(value):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_leave_data(user, leave_type, start_str, end_str, reason):
    """Validate a leave application.

    Returns (cleaned_data, errors). `cleaned_data` is only usable when
    `errors` is empty.
    """
    errors = []
    leave_type = (leave_type or "").strip()
    reason = (reason or "").strip()

    if leave_type not in LEAVE_TYPES:
        errors.append("Please select a valid leave type (Casual, Sick or Earned).")

    start = _parse_date(start_str)
    end = _parse_date(end_str)
    if start is None:
        errors.append("Start date is required and must be a valid date (YYYY-MM-DD).")
    if end is None:
        errors.append("End date is required and must be a valid date (YYYY-MM-DD).")

    if not reason:
        errors.append("Reason is required.")
    elif len(reason) < MIN_REASON_LENGTH:
        errors.append(f"Reason must be at least {MIN_REASON_LENGTH} characters long.")
    elif len(reason) > MAX_REASON_LENGTH:
        errors.append(f"Reason must not exceed {MAX_REASON_LENGTH} characters.")

    days = 0
    if start and end:
        if start < date.today():
            errors.append("Start date cannot be in the past.")
        if end < start:
            errors.append("End date cannot be before the start date.")
        elif (end - start).days + 1 > MAX_LEAVE_SPAN_DAYS:
            errors.append(
                f"A single request cannot span more than {MAX_LEAVE_SPAN_DAYS} days."
            )

    # Checks that depend on everything above being valid.
    if not errors:
        days = LeaveRequest.calculate_days(start, end)
        if days == 0:
            errors.append(
                "The selected dates only contain weekends - no leave days to apply for."
            )
        else:
            overlap = LeaveRequest.find_overlap(user.id, start, end)
            if overlap:
                errors.append(
                    "You already have a "
                    f"{overlap.status.lower()} leave request from "
                    f"{overlap.start_date:%d %b %Y} to {overlap.end_date:%d %b %Y} "
                    "that overlaps with these dates."
                )
            balance = user.get_or_create_balance()
            reserved = LeaveRequest.pending_days(user.id, leave_type)
            available = balance.get(leave_type) - reserved
            if days > available:
                errors.append(
                    f"Insufficient {leave_type} leave balance. You are requesting "
                    f"{days} day(s) but only {max(available, 0)} day(s) are available"
                    + (f" ({reserved} reserved by pending requests)." if reserved else ".")
                )

    cleaned = {
        "leave_type": leave_type,
        "start_date": start,
        "end_date": end,
        "days": days,
        "reason": reason,
    }
    return cleaned, errors


def validate_rejection_reason(reason):
    """Return (clean_reason, error_message_or_None)."""
    reason = (reason or "").strip()
    if not reason:
        return reason, "A rejection reason is required."
    if len(reason) < MIN_REASON_LENGTH:
        return reason, f"Rejection reason must be at least {MIN_REASON_LENGTH} characters long."
    if len(reason) > MAX_REJECTION_LENGTH:
        return reason, f"Rejection reason must not exceed {MAX_REJECTION_LENGTH} characters."
    return reason, None
