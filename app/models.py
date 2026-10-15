from datetime import datetime
from app import db

class Procurement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    abc = db.Column(db.String(100))
    pre_bid_date = db.Column(db.String(100))
    place_of_bidding = db.Column(db.String(255))
    municipality = db.Column(db.String(100))
    agency = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(20), default='Ongoing')  # 'Ongoing', 'Awarded', 'Archived'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('Item', backref='procurement', lazy=True, cascade="all, delete-orphan")

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    procurement_id = db.Column(db.Integer, db.ForeignKey('procurement.id'), nullable=False)
    code = db.Column(db.String(50))
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    price = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(50))
    target_qty = db.Column(db.Integer, default=1)
    current_qty = db.Column(db.Integer, default=0)
    expiration_date = db.Column(db.Date, nullable=True)

class AvailableStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    unit = db.Column(db.String(50))
    expiration_date = db.Column(db.Date, nullable=True)

from werkzeug.security import generate_password_hash, check_password_hash

# ... existing Procurement and Item models ...

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
