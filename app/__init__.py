import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
logger = logging.getLogger(__name__)


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
        os.makedirs(app.instance_path, exist_ok=True)
        _init_db(app)

    return app


def _init_db(app):
    """Initialize DB tables. If the primary DB is unreachable, fall back to SQLite."""
    sqlite_uri = 'sqlite:///' + os.path.join(app.instance_path, 'reportes.db')

    try:
        db.create_all()
        logger.info("DB init OK — %s", app.config.get('SQLALCHEMY_DATABASE_URI', '')[:60])
    except Exception as primary_err:
        logger.error("Primary DB unreachable (%s). Switching to SQLite.", primary_err)
        app.config['SQLALCHEMY_DATABASE_URI'] = sqlite_uri
        db.init_app(app)   # re-init SQLAlchemy with SQLite URI
        db.create_all()
        logger.warning("Running on SQLite fallback — data will not persist across restarts")

    try:
        _run_migrations()
    except Exception as e:
        logger.warning("Migration warning (non-fatal): %s", e)


def _run_migrations():
    """Add new columns to existing tables without losing data."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)

    # Only run if the table already exists
    if 'report_rows' not in inspector.get_table_names():
        return

    existing = [col['name'] for col in inspector.get_columns('report_rows')]
    pending = []

    if 'establecimiento' not in existing:
        pending.append("ALTER TABLE report_rows ADD COLUMN establecimiento VARCHAR(200) DEFAULT ''")

    if 'registros' not in existing:
        pending.append("ALTER TABLE report_rows ADD COLUMN registros INTEGER DEFAULT 0")

    if 'ciudad' not in existing:
        pending.append("ALTER TABLE report_rows ADD COLUMN ciudad VARCHAR(200) DEFAULT ''")

    if pending:
        with db.engine.connect() as conn:
            for sql in pending:
                conn.execute(text(sql))
            conn.commit()
