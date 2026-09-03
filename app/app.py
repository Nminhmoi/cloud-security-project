import os
from flask import Flask, session
from config import Config
from database import get_db_connection, init_db
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.share import share_bp
from routes.admin import admin_bp
from routes.api import api_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    init_db(app)

    @app.before_request
    def reject_inactive_sessions():
        """Invalidate existing sessions after an account is disabled/deleted."""
        user_id = session.get("user_id")
        if user_id is None:
            return
        connection = get_db_connection()
        user = connection.execute(
            "SELECT is_active FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        connection.close()
        if not user or not user["is_active"]:
            session.clear()

    return app


app = create_app()


if __name__ == "__main__":
    app.logger.warning("OTP delivery mode: %s", app.config["OTP_DELIVERY_MODE"])
    app.run(host="0.0.0.0", port=5000, debug=True)
