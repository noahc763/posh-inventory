from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Index

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "users"  # avoid reserved word 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    notes = db.Column(db.Text)

    barcode = db.Column(db.String(64), nullable=True)

    purchase_source = db.Column(db.String(120))
    purchase_price = db.Column(db.Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    purchase_date = db.Column(db.Date)

    list_price = db.Column(db.Numeric(10, 2))
    sold_price = db.Column(db.Numeric(10, 2))
    sold_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "barcode", name="uq_user_barcode"),
        Index("ix_items_user_barcode", "user_id", "barcode"),
    )

    @property
    def payout(self):
        # Poshmark keeps 20%
        return (self.sold_price or Decimal("0.00")) * Decimal("0.80")

    @property
    def profit(self):
        return self.payout - (self.purchase_price or Decimal("0.00"))
