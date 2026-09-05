"""Browser authentication routes."""

import re
import smtplib

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from services.email_service import send_otp_email
from services.otp_service import create_otp, delete_otp
from services.otp_service import verify_otp as verify_otp_code

auth_bp = Blueprint("auth", __name__)


def _login_destination(role_name):
    """Return the correct landing page for an authenticated role."""
    endpoint = "admin.dashboard" if role_name == "admin" else "documents.index"
    return redirect(url_for(endpoint))


def _wants_json_response():
    """Detect the explicit JSON response requested by the async login form."""
    accepts = request.accept_mimetypes
    return accepts["application/json"] > accepts["text/html"]


def _login_failure(message, status):
    """Keep browser login failures on the login screen."""
    if _wants_json_response():
        return jsonify(error={"message": message, "status": status}), status
    return render_template("login.html", login_error=message), status


def _valid_username(username):
    return bool(
        6 <= len(username) <= 24
        and re.fullmatch(r"[\x21-\x7E]+", username)
        and re.search(r"[A-Za-z]", username)
        and re.search(r"[0-9]", username)
        and re.search(r"[^A-Za-z0-9]", username)
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form["username"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    if not _valid_username(username):
        return "Tên đăng nhập phải dài 6-24 ký tự, có chữ, số và ký tự đặc biệt!", 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return "Địa chỉ email không hợp lệ!", 400
    if len(password) < 6:
        return "Mật khẩu phải có ít nhất 6 ký tự!", 400

    try:
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return "Tên đăng nhập hoặc email đã tồn tại!", 409

    return redirect(url_for("auth.login"))


@auth_bp.route("/check-username")
def check_username():
    username = request.args.get("username", "").strip()
    if not _valid_username(username):
        return jsonify(
            available=False,
            message="Cần 6-24 ký tự gồm chữ, số và ký tự đặc biệt.",
        )

    exists = db.session.scalar(
        db.select(User.id).where(func.lower(User.username) == username.casefold())
    )
    message = (
        "Tên đăng nhập đã được sử dụng."
        if exists
        else "Tên đăng nhập có thể sử dụng."
    )
    return jsonify(available=not bool(exists), message=message)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    identifier = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    normalized_identifier = identifier.casefold()
    user = db.session.scalar(
        db.select(User).where(
            or_(
                func.lower(User.username) == normalized_identifier,
                func.lower(User.email) == normalized_identifier,
            )
        )
    )

    try:
        password_is_valid = bool(
            user and user.password and check_password_hash(user.password, password)
        )
    except (TypeError, ValueError):
        current_app.logger.exception(
            "Invalid password hash stored for user id %s", user.id if user else None
        )
        password_is_valid = False

    if not password_is_valid:
        return _login_failure("Sai tài khoản hoặc mật khẩu!", 401)
    if not user.is_active:
        return _login_failure("Tài khoản đã bị vô hiệu hóa!", 403)

    session.clear()
    session.permanent = request.form.get("remember_me") == "on"
    session["user_id"] = user.id
    session["username"] = user.username
    if _wants_json_response():
        endpoint = "admin.dashboard" if user.role_name == "admin" else "documents.index"
        return jsonify(data={"redirect_url": url_for(endpoint)})
    return _login_destination(user.role_name)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form["email"].strip().lower()
    user = db.session.scalar(
        db.select(User).where(func.lower(User.email) == email.casefold())
    )
    if not user:
        return "Không tìm thấy tài khoản đăng ký bằng email này!", 404

    otp = create_otp(user.id)
    try:
        send_otp_email(email, otp)
    except (OSError, smtplib.SMTPException, ValueError):
        current_app.logger.exception("Gửi OTP thất bại")
        delete_otp(user.id)
        return "Không thể gửi OTP. Vui lòng kiểm tra cấu hình email!", 500

    session.pop("reset_verified_user_id", None)
    session["reset_user_id"] = user.id
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    user_id = session.get("reset_user_id")
    if not user_id:
        return redirect(url_for("auth.forgot_password"))
    if request.method == "GET":
        return render_template("verify_otp.html")

    result = verify_otp_code(user_id, request.form["otp"].strip())
    if result == "expired":
        session.pop("reset_user_id", None)
        return "Mã OTP đã hết hạn!", 400
    if result == "locked":
        session.pop("reset_user_id", None)
        return "Bạn đã nhập sai 3 lần. Vui lòng yêu cầu mã mới!", 429
    if result == "invalid":
        return "Mã OTP không chính xác!", 400

    session["reset_verified_user_id"] = user_id
    session.pop("reset_user_id", None)
    return redirect(url_for("auth.reset_password"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_verified_user_id")
    if not user_id:
        return redirect(url_for("auth.forgot_password"))
    if request.method == "GET":
        return render_template("reset_password.html")

    password = request.form["new_password"]
    confirmation = request.form["confirm_password"]
    if password != confirmation:
        return "Mật khẩu xác nhận không khớp!", 400
    if len(password) < 6:
        return "Mật khẩu mới phải có ít nhất 6 ký tự!", 400

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    user.password = generate_password_hash(password)
    db.session.commit()
    delete_otp(user_id)

    session.clear()
    session["user_id"] = user_id
    session["username"] = user.username
    return _login_destination(user.role_name)
