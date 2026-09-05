"""User model."""

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(24), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255), nullable=False)
    role_id = db.Column(
        db.Integer,
        db.ForeignKey("roles.id"),
        nullable=False,
        default=2,
        server_default="2",
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default=db.true(),
    )

    role = db.relationship("Role", back_populates="users", lazy="joined")
    documents = db.relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan", lazy="select"
    )
    received_shares = db.relationship(
        "DocumentShare",
        back_populates="recipient",
        cascade="all, delete-orphan",
        lazy="select",
    )
    password_reset_otp = db.relationship(
        "PasswordResetOTP",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def role_name(self):
        return self.role.name if self.role else None

    def to_dict(self, include_role=False):
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_active": bool(self.is_active),
            "role_id": self.role_id,
        }
        if include_role:
            data["role"] = self.role_name
            data["role_name"] = self.role_name
        return data
