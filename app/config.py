import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///reportes.db')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '')

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # Render uses postgres:// but SQLAlchemy needs postgresql://
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        if uri.startswith('postgres://'):
            app.config['SQLALCHEMY_DATABASE_URI'] = uri.replace('postgres://', 'postgresql://', 1)


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
