import os
from flask import Flask, redirect, url_for, session, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash
from config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.philgeps import philgeps_bp
    from app.routes.inventory import inventory_bp
    from app.routes.bid_upload import bid_upload_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(philgeps_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(bid_upload_bp)

    @app.route('/')
    def index_redirect():
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return redirect(url_for('inventory.index'))

    # Serve manifest.json with proper MIME type
    @app.route('/manifest.json')
    def manifest():
        return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

    # Serve sw.js with root scope header for PWA offline caching
    @app.route('/sw.js')
    def service_worker():
        response = make_response(send_from_directory('static', 'sw.js', mimetype='application/javascript'))
        response.headers['Service-Worker-Allowed'] = '/'
        return response

    with app.app_context():
        from app.models import Procurement, Item, AvailableStock, User
        db.create_all()

        item_columns = {column['name'] for column in inspect(db.engine).get_columns('item')}
        if 'expiration_date' not in item_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE item ADD COLUMN expiration_date DATE'))

        # Create default admin if none exists
        if not User.query.filter_by(username='admin').first():
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if admin_password:
                password_hash = generate_password_hash(admin_password)
            else:
                import secrets
                password_hash = generate_password_hash(secrets.token_urlsafe(16))
                app.logger.warning(
                    "ADMIN_PASSWORD not set in environment. "
                    "A random admin password was generated; set ADMIN_PASSWORD to control it."
                )

            admin = User(username='admin', password_hash=password_hash)
            db.session.add(admin)
            db.session.commit()

    return app
