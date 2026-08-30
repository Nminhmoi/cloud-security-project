import os
from flask import Flask
from config import Config
from database import init_db
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.share import share_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(share_bp)
    init_db(app)
    return app


app = create_app()


if __name__ == "__main__":
    app.logger.warning("OTP delivery mode: %s", app.config["OTP_DELIVERY_MODE"])
    app.run(host="0.0.0.0", port=5000, debug=True)
