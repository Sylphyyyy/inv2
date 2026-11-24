import os


def env(key, default=None):
    return os.environ.get(key, default)


database_url = env('DATABASE_URL')
if database_url:
    scheme, separator, remainder = database_url.partition('://')
    if separator and scheme in {'postgres', 'postgresql'}:
        database_url = f'postgresql+psycopg://{remainder}'


class Config:
    SECRET_KEY = env('SECRET_KEY') or 'dev-fallback-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = env('UPLOAD_FOLDER') or '/tmp/uploads'
    ADMIN_EMAIL = (env('ADMIN_EMAIL') or '').strip().lower()
    MAIL_SERVER = env('MAIL_SERVER')
    MAIL_PORT = int(env('MAIL_PORT', '587') or '587')
    MAIL_USERNAME = env('MAIL_USERNAME')
    MAIL_PASSWORD = env('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = env('MAIL_DEFAULT_SENDER')
    PUBLIC_BASE_URL = (env('PUBLIC_BASE_URL') or '').rstrip('/')
    PROCUREMENT_PIPELINE_URL = (env('PROCUREMENT_PIPELINE_URL') or '').rstrip('/')
    PROCUREMENT_PIPELINE_TOKEN = (env('PROCUREMENT_PIPELINE_TOKEN') or '').strip()
