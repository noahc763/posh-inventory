from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

from posh import profit_after_fees, break_even_listing_price, payout_after_fees

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

    title = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(120))
    size = db.Column(db.String(60))
    color = db.Column(db.String(60))
    condition = db.Column(db.String(120))
    notes = db.Column(db.Text)

    barcode = db.Column(db.String(64), index=True)  # UPC/EAN etc.

    purchase_source = db.Column(db.String(120))
    purchase_price = db.Column(db.Numeric(10,2), nullable=False, default=0)
    purchase_date = db.Column(db.Date)

    list_price = db.Column(db.Numeric(10,2))
    photo_path = db.Column(db.String(255))

    sold_price = db.Column(db.Numeric(10,2))
    sold_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def payout(self):
        if self.sold_price is None:
            return None
        return payout_after_fees(Decimal(self.sold_price))

    def profit(self):
        if self.sold_price is None:
            return None
        return profit_after_fees(Decimal(self.sold_price), Decimal(self.purchase_price or 0))

    def break_even_price(self):
        return break_even_listing_price(Decimal(self.purchase_price or 0))
