"""Browser authentication routes."""

import re

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
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from extensions import db, limiter
from models import User
from services.auth_service import (
    authenticate_user,
    complete_password_reset,
    establish_session,
    password_policy_error,
)
from services.email_service import EmailDeliveryError, send_otp_email
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
@limiter.limit("5 per hour", methods=["POST"])
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
    password_error = password_policy_error(password)
    if password_error:
        return password_error, 400

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
@limiter.limit("30 per minute")
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
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    identifier = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    result = authenticate_user(identifier, password)
    if result.status == "locked":
        return _login_failure("Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau!", 429)
    if result.status == "invalid":
        return _login_failure("Sai tài khoản hoặc mật khẩu!", 401)
    if result.status == "inactive":
        return _login_failure("Tài khoản đã bị vô hiệu hóa!", 403)

    user = result.user
    establish_session(user, permanent=request.form.get("remember_me") == "on")
    if _wants_json_response():
        endpoint = "admin.dashboard" if user.role_name == "admin" else "documents.index"
        return jsonify(data={"redirect_url": url_for(endpoint)})
    return _login_destination(user.role_name)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per 15 minutes", methods=["POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form["email"].strip().lower()
    user = db.session.scalar(
        db.select(User).where(func.lower(User.email) == email.casefold())
    )
    reset_user_id = user.id if user else -1
    if user:
        otp = create_otp(user.id)
        try:
            send_otp_email(email, otp)
        except EmailDeliveryError:
            current_app.logger.exception("Gửi OTP thất bại")
            delete_otp(user.id)
            reset_user_id = -1

    session.pop("reset_verified_user_id", None)
    session["reset_user_id"] = reset_user_id
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"])
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
@limiter.limit("5 per hour", methods=["POST"])
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
    password_error = password_policy_error(password)
    if password_error:
        return password_error, 400

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    complete_password_reset(user, password)
    delete_otp(user_id)

    session.clear()
    return redirect(url_for("auth.login"))
