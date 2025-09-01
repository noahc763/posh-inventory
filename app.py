# app.py
import os
from decimal import Decimal
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_required, current_user

from config import Config
from models import db, Item, Category, User
from auth import auth_bp
from items import items_bp
from categories import categories_bp


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    )
    app.config.from_object(Config)

    # --- DB init ---
    db.init_app(app)
    with app.app_context():
        if os.environ.get("RUN_DB_CREATE_ALL") == "1":
            db.create_all()

    # --- Auth ---
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(categories_bp)

    # --- Helpers ---
    def normalize_barcode(raw: str) -> str:
        if not raw:
            return ""
        return "".join(ch for ch in raw.strip() if ch.isalnum())

    def parse_money(v):
        try:
            return Decimal(v)
        except Exception:
            return None

    def parse_date(v):
        try:
            return datetime.strptime(v, "%Y-%m-%d").date() if v else None
        except Exception:
            return None

    # --- Routes ---

    @app.route("/")
    @login_required
    def dashboard():
        cat_id = request.args.get("category", type=int)
        q = Item.query.filter_by(user_id=current_user.id)
        if cat_id:
            q = q.filter(Item.category_id == cat_id)
        items = q.order_by(Item.created_at.desc()).all()
        cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
        return render_template(
            "dashboard.html",
            items=items,
            categories=cats,
            selected_cat=cat_id,
            Decimal=Decimal,
        )

    @app.route("/items/<int:item_id>")
    @login_required
    def item_detail(item_id: int):
        item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
        return render_template("item_detail.html", item=item, Decimal=Decimal)

    # Scanner page
    @app.route("/scan")
    @login_required
    def scan():
        cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
        return render_template("scan.html", categories=cats)

    # Lookup API
    @app.get("/api/items/lookup")
    @login_required
    def api_items_lookup():
        barcode = normalize_barcode(request.args.get("barcode", ""))
        if not barcode:
            return jsonify({"found": False}), 200
        item = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first()
        if item:
            return jsonify({"found": True, "id": item.id}), 200
        return jsonify({"found": False}), 200

    # === Manual Add / New Item ===

    # Legacy link support
    @app.route("/items/add")
    def legacy_items_add():
        return redirect(url_for("items_new"), code=301)

    # Single canonical form; category can be chosen in-form.
    @app.route("/items/new", methods=["GET", "POST"])
    @app.route("/categories/<int:category_id>/items/new", methods=["GET", "POST"])
    @login_required
    def items_new(category_id=None):
        prefill = {"barcode": request.args.get("barcode", "")}

        categories = (Category.query
                      .filter_by(user_id=current_user.id)
                      .order_by(Category.name.asc())
                      .all())

        cat_id = (category_id
                  or request.args.get("category_id", type=int)
                  or request.form.get("category_id", type=int))
        category = (Category.query
                    .filter_by(id=cat_id, user_id=current_user.id)
                    .first()) if cat_id else None

        if request.method == "POST":
            title = (request.form.get("title") or request.form.get("name") or "").strip()
            if not title:
                flash("Title is required.", "error")
                return render_template("item_form.html", categories=categories, category=category, prefill=prefill)

            if not category:
                flash("Please select a category.", "error")
                return render_template("item_form.html", categories=categories, category=None, prefill=prefill)

            def as_decimal(field):
                raw = (request.form.get(field) or "").strip()
                try:
                    return Decimal(raw) if raw else None
                except Exception:
                    return None

            def as_datetime(field):
                raw = (request.form.get(field) or "").strip()
                try:
                    return datetime.fromisoformat(raw) if raw else None
                except Exception:
                    return None

            item = Item(
                user_id=current_user.id,
                category_id=category.id,
                title=title,                              # change to name=title if your model uses `name`
                barcode=(request.form.get("barcode") or None),
                size=(request.form.get("size") or None),
                color=(request.form.get("color") or None),
                purchase_price=as_decimal("purchase_price"),
                listed_price=as_decimal("listing_price"),
                sold_price=as_decimal("sold_price"),
                sold_date=as_datetime("sold_date"),
                condition=(request.form.get("condition") or None),
                notes=(request.form.get("notes") or None),
            )
            db.session.add(item)
            db.session.commit()
            flash("Item added.", "success")
            return redirect(url_for("item_detail", item_id=item.id))

        return render_template("item_form.html", categories=categories, category=category, prefill=prefill)

    # Health check
    @app.route("/healthz")
    def healthz():
        return {"ok": True}

    return app


# WSGI entrypoint
app = create_app()
