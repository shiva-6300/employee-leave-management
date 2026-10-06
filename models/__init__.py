"""Database object and model imports."""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    """Current UTC time as a naive datetime (works with MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Imported after `db` is defined to avoid circular-import problems.
from models.user import User  # noqa: E402,F401
from models.leave_balance import LeaveBalance  # noqa: E402,F401
from models.leave import LeaveRequest  # noqa: E402,F401
