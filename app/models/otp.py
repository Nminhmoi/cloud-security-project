"""Password reset OTP model."""

from extensions import db


class PasswordResetOTP(db.Model):
    __tablename__ = "password_reset_otps"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    otp_hash = db.Column(db.String(255), nullable=False)
    expires_at = db.Column(db.BigInteger, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    user = db.relationship("User", back_populates="password_reset_otp")
