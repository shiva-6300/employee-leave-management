from werkzeug.security import check_password_hash, generate_password_hash

from models import db, utcnow


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)  # hashed, never plain text
    role = db.Column(
        db.Enum("employee", "manager", name="user_role"),
        nullable=False,
        default="employee",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    leave_requests = db.relationship(
        "LeaveRequest",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="LeaveRequest.applied_at.desc()",
    )
    balance = db.relationship(
        "LeaveBalance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    @property
    def is_manager(self):
        return self.role == "manager"

    def get_or_create_balance(self):
        """Return this user's leave balance, creating the default row if missing."""
        from models.leave_balance import LeaveBalance

        if self.balance is None:
            self.balance = LeaveBalance()
            db.session.add(self.balance)
            db.session.commit()
        return self.balance

    def to_dict(self, include_balance=False):
        data = {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_balance:
            data["leave_balance"] = (
                self.balance.to_dict() if self.balance else None
            )
        return data

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
