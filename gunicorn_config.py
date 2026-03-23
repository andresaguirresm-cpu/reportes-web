"""Gunicorn configuration for Render free tier."""


def post_fork(server, worker):
    """Re-create SQLAlchemy connection pool after worker fork (required with --preload)."""
    from app import db
    db.engine.dispose()
