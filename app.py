# app.py
import os
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, login_required, current_user
from config import Config
from models import db, Item, Category, User
from auth import auth_bp
from items import items_bp
from categories import categories_bp
from datetime import datetime


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
        db.create_all()  # create tables if missing

    # --- Auth ---
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Blueprints ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(categories_bp)

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
        return render_template("dashboard.html", items=items, categories=cats, selected_cat=cat_id, Decimal=Decimal)

    @app.route("/items/<int:item_id>")
    @login_required
    def item_detail(item_id: int):
        item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
        return render_template("item_detail.html", item=item, Decimal=Decimal)

    @app.route("/scan")
    @login_required
    def scan():
        return render_template("scan.html")

    # --- Helpers ---
    def normalize_barcode(raw: str) -> str:
        if not raw:
            return ""
        return "".join(ch for ch in raw.strip() if ch.isalnum())

    # API used by scan.html to decide where to redirect
    @app.get("/api/items/lookup")
    @login_required
    def api_items_lookup():
        barcode = normalize_barcode(request.args.get("barcode", ""))
        if not barcode:
            return jsonify({"found": False}), 200

        item = (
            Item.query.filter_by(user_id=current_user.id, barcode=barcode)
            .first()
        )
        if item:
            return jsonify({"found": True, "id": item.id}), 200
        return jsonify({"found": False}), 200

    @app.get("/items/new")
    @login_required
    def items_new():
        barcode = request.args.get("barcode", "")
        return render_template("item_form.html", prefill={"barcode": barcode})

    @app.post("/items")
    @login_required
    def items_create():
        name = (request.form.get("name") or "").strip()
        barcode = normalize_barcode(request.form.get("barcode") or "")
        purchase_price = request.form.get("purchase_price")
        sold_price = request.form.get("sold_price")
        purchase_date = request.form.get("purchase_date")
        purchase_source = (request.form.get("purchase_source") or "").strip()
        list_price = request.form.get("list_price")
        notes = request.form.get("notes")

        if not barcode:
            return ("Barcode required", 400)

        # helpers
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

        existing = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first()
        if existing:
            return redirect(url_for("item_detail", item_id=existing.id))

        item = Item(
            user_id=current_user.id,
            title=name or "Untitled",
            barcode=barcode,
            purchase_source=purchase_source or None,
            purchase_price=parse_money(purchase_price) or Decimal("0.00"),
            list_price=parse_money(list_price),
            sold_price=parse_money(sold_price),
            purchase_date=parse_date(purchase_date),
            notes=notes or None,
        )

        db.session.add(item)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return ("Barcode already exists", 409)

        return redirect(url_for("item_detail", item_id=item.id))


    # (optional) quick health check
    @app.route("/healthz")
    def healthz():
        return {"ok": True}

    return app


# WSGI entrypoint
app = create_app()
