from models import db

# Maps the leave type shown to users to the column that stores its balance.
BALANCE_COLUMNS = {
    "Casual": "casual_leave",
    "Sick": "sick_leave",
    "Earned": "earned_leave",
}


class LeaveBalance(db.Model):
    __tablename__ = "leave_balances"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    casual_leave = db.Column(db.Integer, nullable=False, default=12)
    sick_leave = db.Column(db.Integer, nullable=False, default=10)
    earned_leave = db.Column(db.Integer, nullable=False, default=15)

    user = db.relationship("User", back_populates="balance")

    def get(self, leave_type):
        return getattr(self, BALANCE_COLUMNS[leave_type])

    def deduct(self, leave_type, days):
        column = BALANCE_COLUMNS[leave_type]
        setattr(self, column, getattr(self, column) - days)

    def to_dict(self):
        return {
            "casual_leave": self.casual_leave,
            "sick_leave": self.sick_leave,
            "earned_leave": self.earned_leave,
        }

    def __repr__(self):
        return f"<LeaveBalance user={self.user_id}>"
