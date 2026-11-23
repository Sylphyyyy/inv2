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
        if 'delivery_checked' not in item_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE item ADD COLUMN delivery_checked BOOLEAN NOT NULL DEFAULT FALSE'))

        user_columns = {column['name'] for column in inspect(db.engine).get_columns('user')}
        with db.engine.begin() as connection:
            if 'email' not in user_columns:
                connection.execute(text('ALTER TABLE "user" ADD COLUMN email VARCHAR(320)'))
            if 'reset_token_hash' not in user_columns:
                connection.execute(text('ALTER TABLE "user" ADD COLUMN reset_token_hash VARCHAR(64)'))
            if 'reset_token_expires_at' not in user_columns:
                connection.execute(text('ALTER TABLE "user" ADD COLUMN reset_token_expires_at BIGINT'))

        proc_columns = {column['name'] for column in inspect(db.engine).get_columns('procurement')}
        with db.engine.begin() as connection:
            if 'abc' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN abc VARCHAR(100)'))
            if 'pre_bid_date' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN pre_bid_date VARCHAR(100)'))
            if 'place_of_bidding' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN place_of_bidding VARCHAR(255)'))
            if 'municipality' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN municipality VARCHAR(100)'))
            if 'agency' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN agency VARCHAR(150)'))
            if 'status' not in proc_columns:
                connection.execute(text("ALTER TABLE procurement ADD COLUMN status VARCHAR(20) DEFAULT 'Ongoing'"))
            if 'created_at' not in proc_columns:
                connection.execute(text('ALTER TABLE procurement ADD COLUMN created_at DATETIME'))

        # Create default admin if none exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
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

        if app.config['ADMIN_EMAIL'] and not admin.email:
            admin.email = app.config['ADMIN_EMAIL']
        elif app.config['ADMIN_EMAIL'] and admin.email != app.config['ADMIN_EMAIL']:
            app.logger.warning(
                'ADMIN_EMAIL differs from the existing admin recovery address; leaving it unchanged.'
            )
        db.session.commit()

    return app
