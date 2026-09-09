"""Password reset OTP persistence."""

import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import PasswordResetOTP

OTP_TTL_SECONDS = 120
MAX_ATTEMPTS = 3


def create_otp(user_id):
    otp = f"{secrets.randbelow(1_000_000):06d}"
    record = db.session.get(PasswordResetOTP, user_id)
    if record is None:
        record = PasswordResetOTP(user_id=user_id)
        db.session.add(record)

    record.otp_hash = generate_password_hash(otp)
    record.expires_at = int(time.time()) + OTP_TTL_SECONDS
    record.attempts = 0
    db.session.commit()
    return otp


def verify_otp(user_id, otp):
    record = db.session.get(PasswordResetOTP, user_id)
    if record is None:
        return "invalid"
    if record.expires_at < int(time.time()):
        db.session.delete(record)
        db.session.commit()
        return "expired"

    if record.attempts >= MAX_ATTEMPTS:
        return "locked"
    if check_password_hash(record.otp_hash, otp):
        return "valid"

    record.attempts += 1
    locked = record.attempts >= MAX_ATTEMPTS
    if locked:
        db.session.delete(record)
    db.session.commit()
    return "locked" if locked else "invalid"


def delete_otp(user_id):
    record = db.session.get(PasswordResetOTP, user_id)
    if record is not None:
        db.session.delete(record)
        db.session.commit()
