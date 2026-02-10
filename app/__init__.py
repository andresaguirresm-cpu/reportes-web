import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
        if config_name == 'production':
            config_name = 'production'
        else:
            config_name = 'development'

    app = Flask(__name__)

    from app.config import config
    app.config.from_object(config.get(config_name, config['default']))
    config.get(config_name, config['default']).init_app(app)

    db.init_app(app)

    from app.routes.main import main_bp
    from app.routes.upload import upload_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.download import download_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        from app import models  # noqa: F401
        db.create_all()

    return app
