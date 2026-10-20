import os


database_url = os.environ.get('DATABASE_URL')
if database_url:
    scheme, separator, remainder = database_url.partition('://')
    if separator and scheme in {'postgres', 'postgresql'}:
        database_url = f'postgresql+psycopg://{remainder}'
elif os.environ.get('RENDER', '').lower() == 'true':
    raise RuntimeError(
        'DATABASE_URL must be configured on Render to use persistent database storage.'
    )


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-fallback-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'app/static/uploads'
