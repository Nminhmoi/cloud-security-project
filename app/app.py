import os
import secrets

import click
from flask import Flask, g, jsonify, request, session
from flask_wtf.csrf import CSRFError
from sqlalchemy.engine import make_url
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from database import init_db
from extensions import csrf, db, limiter, migrate
import models  # noqa: F401 - register model metadata before migrations run
from models import User
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.share import share_bp
from routes.admin import admin_bp
from routes.api import api_bp
from services.document_service import purge_expired_documents


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # The application is reachable only through the ALB security group, so one
    # trusted X-Forwarded-For/Proto hop is expected.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    database_url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    app.logger.warning("Using database: %s", database_url.render_as_string(hide_password=True))
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    if app.config["AUTO_CREATE_SCHEMA"]:
        init_db(app)

    @app.cli.command("purge-deleted-documents")
    @click.option(
        "--retention-days",
        type=click.IntRange(min=0),
        default=None,
        help="Override DELETED_DOCUMENT_RETENTION_DAYS for this run.",
    )
    def purge_deleted_documents_command(retention_days):
        """Permanently remove document trash after its retention window."""
        purged = purge_expired_documents(retention_days)
        click.echo(f"Purged {purged} expired document(s).")

    @app.before_request
    def reject_inactive_sessions():
        """Invalidate existing sessions after an account is disabled/deleted."""
        user_id = session.get("user_id")
        if user_id is None:
            return
        user = db.session.get(User, user_id)
        if (
            not user
            or not user.is_active
            or session.get("session_version") != user.session_version
        ):
            session.clear()

    @app.before_request
    def create_content_security_policy_nonce():
        g.csp_nonce = secrets.token_urlsafe(18)

    @app.after_request
    def add_security_headers(response):
        policy = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{g.get('csp_nonce', '')}'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = policy
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-Frame-Options"] = "DENY"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify(error={"message": error.description, "status": 400}), 400
        return error.description, 400

    @app.errorhandler(429)
    def handle_rate_limit(error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify(error={"message": "Quá nhiều yêu cầu", "status": 429}), 429
        return "Quá nhiều yêu cầu. Vui lòng thử lại sau.", 429

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error):
        if request.path.startswith("/api/") or request.is_json:
            return jsonify(error={"message": "Tệp tải lên quá lớn", "status": 413}), 413
        return "Tệp tải lên vượt quá giới hạn cho phép.", 413

    return app


app = create_app()


if __name__ == "__main__":
    app.logger.warning("OTP delivery mode: %s", app.config["OTP_DELIVERY_MODE"])
    app.run(host="0.0.0.0", port=5000, debug=True)
