import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection

OTP_TTL_SECONDS = 120
MAX_ATTEMPTS = 3


def create_otp(user_id):
    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = int(time.time()) + OTP_TTL_SECONDS

    connection = get_db_connection()
    connection.execute(
        """
        INSERT INTO password_reset_otps (
            user_id,
            otp_hash,
            expires_at,
            attempts
        )
        VALUES (?, ?, ?, 0)
        ON CONFLICT(user_id) DO UPDATE SET
            otp_hash = excluded.otp_hash,
            expires_at = excluded.expires_at,
            attempts = 0
        """,
        (user_id, generate_password_hash(otp), expires_at),
    )
    connection.commit()
    connection.close()
    return otp


def verify_otp(user_id, otp):
    connection = get_db_connection()
    record = connection.execute(
        "SELECT * FROM password_reset_otps WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if record is None or record["expires_at"] < int(time.time()):
        connection.execute(
            "DELETE FROM password_reset_otps WHERE user_id = ?",
            (user_id,),
        )
        connection.commit()
        connection.close()
        return "expired"

    if record["attempts"] >= MAX_ATTEMPTS:
        connection.close()
        return "locked"

    if check_password_hash(record["otp_hash"], otp):
        connection.close()
        return "valid"

    attempts = record["attempts"] + 1
    if attempts >= MAX_ATTEMPTS:
        connection.execute(
            "DELETE FROM password_reset_otps WHERE user_id = ?",
            (user_id,),
        )
    else:
        connection.execute(
            """
            UPDATE password_reset_otps
            SET attempts = ?
            WHERE user_id = ?
            """,
            (attempts, user_id),
        )

    connection.commit()
    connection.close()
    return "locked" if attempts >= MAX_ATTEMPTS else "invalid"


def delete_otp(user_id):
    connection = get_db_connection()
    connection.execute(
        "DELETE FROM password_reset_otps WHERE user_id = ?",
        (user_id,),
    )
    connection.commit()
    connection.close()

