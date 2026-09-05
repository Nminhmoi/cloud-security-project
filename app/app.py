import os
from flask import Flask, session
from sqlalchemy.engine import make_url

from config import Config
from database import init_db
from extensions import db, migrate
import models  # noqa: F401 - register model metadata before migrations run
from models import User
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.share import share_bp
from routes.admin import admin_bp
from routes.api import api_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
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

    @app.before_request
    def reject_inactive_sessions():
        """Invalidate existing sessions after an account is disabled/deleted."""
        user_id = session.get("user_id")
        if user_id is None:
            return
        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            session.clear()

    return app


app = create_app()


if __name__ == "__main__":
    app.logger.warning("OTP delivery mode: %s", app.config["OTP_DELIVERY_MODE"])
    app.run(host="0.0.0.0", port=5000, debug=True)
