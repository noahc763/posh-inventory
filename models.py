from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Index, Numeric
from sqlalchemy.orm import synonym

from posh import profit_after_fees, break_even_listing_price, payout_after_fees

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "users"  # avoid reserved word 'user' in Postgres
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # optional: convenience relationships
    items = db.relationship("Item", backref="user", lazy=True, cascade="all, delete-orphan")
    categories = db.relationship("Category", backref="user", lazy=True, cascade="all, delete-orphan")

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False, index=True)

    items = db.relationship("Item", backref="category", lazy=True)

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))

    title = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(120))
    size = db.Column(db.String(60))
    color = db.Column(db.String(60))
    condition = db.Column(db.String(120))
    notes = db.Column(db.Text)

    # Keep nullable so users can add items without a barcode
    # but enforce uniqueness per user when present.
    barcode = db.Column(db.String(64), nullable=True)

    purchase_source = db.Column(db.String(120))
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    purchase_date = db.Column(db.Date)
    photo_path = db.Column(db.String(255))

    sold_price = db.Column(db.Numeric(10, 2), nullable=True)
    sold_date = db.Column(db.Date)
    list_price = synonym('sold_price')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "barcode", name="uq_user_barcode"),
        # Composite index to match your common lookup pattern
        Index("ix_items_user_barcode", "user_id", "barcode"),
    )

    def payout(self):
        if self.sold_price is None:
            return None
        # sold_price is already Decimal from Numeric; Decimal(...) is still fine
        return payout_after_fees(Decimal(self.sold_price))

    def profit(self):
        if self.sold_price is None:
            return None
        return profit_after_fees(Decimal(self.sold_price), Decimal(self.purchase_price or 0))

    def break_even_price(self):
        return break_even_listing_price(Decimal(self.purchase_price or 0))
