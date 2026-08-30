import re
import smtplib
import sqlite3

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
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection
from services.email_service import send_otp_email
from services.otp_service import create_otp, delete_otp
from services.otp_service import verify_otp as verify_otp_code

auth_bp = Blueprint("auth", __name__)


def _valid_username(username):
    return (
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
        return (
            "Tên đăng nhập phải dài 6-24 ký tự, có chữ, số và ký tự đặc biệt!",
            400,
        )

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return "Địa chỉ email không hợp lệ!", 400

    connection = get_db_connection()
    try:
        connection.execute(
            """
            INSERT INTO users (username, email, password)
            VALUES (?, ?, ?)
            """,
            (username, email, generate_password_hash(password)),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        return "Tên đăng nhập hoặc email đã tồn tại!", 409
    finally:
        connection.close()

    return redirect(url_for("auth.login"))


@auth_bp.route("/check-username")
def check_username():
    username = request.args.get("username", "").strip()

    if not _valid_username(username):
        return jsonify(
            available=False,
            message="Cần 6-24 ký tự gồm chữ, số và ký tự đặc biệt.",
        )

    connection = get_db_connection()
    exists = connection.execute(
        "SELECT 1 FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    connection.close()

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

    connection = get_db_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE username = ?",
        (request.form["username"],),
    ).fetchone()
    connection.close()

    password_is_valid = user and check_password_hash(
        user["password"],
        request.form["password"],
    )
    if not password_is_valid:
        return "Sai tài khoản hoặc mật khẩu!", 401

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return redirect(url_for("documents.index"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form["email"].strip().lower()
    connection = get_db_connection()
    user = connection.execute(
        "SELECT id FROM users WHERE email = ? COLLATE NOCASE",
        (email,),
    ).fetchone()
    connection.close()

    if not user:
        return "Không tìm thấy tài khoản đăng ký bằng email này!", 404

    otp = create_otp(user["id"])
    try:
        send_otp_email(email, otp)
    except (OSError, smtplib.SMTPException, ValueError):
        current_app.logger.exception("Gửi OTP thất bại")
        delete_otp(user["id"])
        return "Không thể gửi OTP. Vui lòng kiểm tra cấu hình email!", 500

    session.pop("reset_verified_user_id", None)
    session["reset_user_id"] = user["id"]
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

    connection = get_db_connection()
    user = connection.execute(
        "SELECT username FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        connection.close()
        session.clear()
        return redirect(url_for("auth.login"))

    connection.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (generate_password_hash(password), user_id),
    )
    connection.commit()
    connection.close()
    delete_otp(user_id)

    session.clear()
    session["user_id"] = user_id
    session["username"] = user["username"]
    return redirect(url_for("documents.index"))
