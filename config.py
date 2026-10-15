import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-admin-secret-key-9988'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///inventory_procurement.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False