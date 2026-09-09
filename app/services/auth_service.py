"""Authentication state, lockout, and session helpers."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from flask import current_app, session
from sqlalchemy import func, or_
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import ActivityLog, User


_DUMMY_PASSWORD_HASH = generate_password_hash("cloudbox-timing-defense-only")


@dataclass
class AuthenticationResult:
    status: str
    user: User | None = None


def _utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def find_user(identifier):
    normalized = identifier.strip().casefold()
    return db.session.scalar(
        db.select(User).where(
            or_(
                func.lower(User.username) == normalized,
                func.lower(User.email) == normalized,
            )
        )
    )


def authenticate_user(identifier, password):
    """Authenticate and persist shared failed-login/lockout telemetry."""

    user = find_user(identifier)
    now = _utc_now_naive()
    if user and user.locked_until and user.locked_until > now:
        return AuthenticationResult("locked", user)

    if user and user.locked_until and user.locked_until <= now:
        user.locked_until = None
        user.failed_login_attempts = 0

    password_hash = user.password if user and user.password else _DUMMY_PASSWORD_HASH
    try:
        password_valid = isinstance(password, str) and check_password_hash(
            password_hash, password
        )
    except (TypeError, ValueError):
        current_app.logger.exception(
            "Invalid password hash stored for user id %s", user.id if user else None
        )
        password_valid = False

    if not user or not password_valid:
        if user:
            user.failed_login_attempts += 1
            maximum = current_app.config["MAX_FAILED_LOGIN_ATTEMPTS"]
            if user.failed_login_attempts >= maximum:
                user.locked_until = now + timedelta(
                    minutes=current_app.config["ACCOUNT_LOCK_MINUTES"]
                )
            db.session.add(
                ActivityLog(
                    actor_user_id=user.id,
                    action="login_failed",
                    target_type="user",
                    target_id=user.id,
                    details=(
                        f"Failed login attempt {user.failed_login_attempts} of "
                        f"{maximum}"
                    ),
                )
            )
            db.session.commit()
        return AuthenticationResult("invalid", user)

    if not user.is_active:
        return AuthenticationResult("inactive", user)

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
    return AuthenticationResult("success", user)


def establish_session(user, permanent=False):
    session.clear()
    session.permanent = permanent
    session["user_id"] = user.id
    session["username"] = user.username
    session["session_version"] = user.session_version


def password_policy_error(password):
    if not isinstance(password, str):
        return "Mật khẩu không hợp lệ"
    minimum = current_app.config["MIN_PASSWORD_LENGTH"]
    if len(password) < minimum:
        return f"Mật khẩu phải có ít nhất {minimum} ký tự"
    if len(password) > 128:
        return "Mật khẩu không được vượt quá 128 ký tự"
    return None


def complete_password_reset(user, password):
    user.password = generate_password_hash(password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.session_version += 1
    db.session.add(
        ActivityLog(
            actor_user_id=user.id,
            action="password_reset",
            target_type="user",
            target_id=user.id,
            details="Password reset completed; existing sessions invalidated",
        )
    )
    db.session.commit()
