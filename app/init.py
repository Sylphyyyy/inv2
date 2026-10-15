from flask import Flask, redirect, url_for
from config import Config
from app.models import db, Category

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from app.routes.inventory import inventory_bp
    from app.routes.philgeps import philgeps_bp

    app.register_blueprint(inventory_bp)
    app.register_blueprint(philgeps_bp)

    @app.route('/')
    def index():
        return redirect(url_for('inventory.index'))

    with app.app_context():
        db.create_all()
        if not Category.query.first():
            cats = [
                Category(name="Drugs and Medicines", description="Pharmaceuticals"),
                Category(name="Medical Supplies", description="Gloves, Syringes"),
                Category(name="Office Supplies", description="Paper, Inks"),
                Category(name="Cleaning / Janitorial", description="Disinfectants")
            ]
            db.session.add_all(cats)
            db.session.commit()

    return app