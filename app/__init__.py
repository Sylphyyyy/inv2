from flask import Flask, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    app.config['SECRET_KEY'] = 'your-secret-key-here'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    with app.app_context():
        from app.models import Procurement, Item, AvailableStock, User
        db.create_all()
        item_columns = {column['name'] for column in inspect(db.engine).get_columns('item')}
        if 'expiration_date' not in item_columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE item ADD COLUMN expiration_date DATE'))
        
        # Create default admin if none exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password_hash=generate_password_hash('admin123'))
            db.session.add(admin)
            db.session.commit()

    return app
