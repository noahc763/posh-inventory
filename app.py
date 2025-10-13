# app.py
import os
from decimal import Decimal
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate

from config import Config
from models import db, Item, Category, User
from auth import auth_bp
from items import items_bp
from categories import categories_bp
from utils import save_upload  # <- for photo saving


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"),
    )
    app.config.from_object(Config)

    # make sure static/uploads exists
    os.makedirs(os.path.join(app.static_folder, app.config["UPLOAD_DIR"]), exist_ok=True)


    # --- DB init ---
    db.init_app(app)
    Migrate(app, db)

    # --- Auth ---
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        # SQLAlchemy 2.x-safe get
        return db.session.get(User, int(user_id))

    # --- Blueprints ---
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(categories_bp)

    # Defer labels import to avoid circulars, then register
    from labels import labels_bp
    app.register_blueprint(labels_bp)

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
        """Accept YYYY-MM-DD or empty; return date or None."""
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
        # If your add_edit_item.html shows selects even in read-only,
        # pass categories; otherwise you can omit it.
        cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
        return render_template(
            "add_edit_item.html",
            item=item,
            categories=cats,
            read_only=True,
            prefill={}
        )


    # Scanner page
    @app.route("/scan")
    @login_required
    def scan():
        cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
        return render_template("scan.html", categories=cats)

    # Lookup API (used by scan.html to decide redirect)
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

    # Legacy link support (/items/add → /items/new)
    @app.route("/items/add")
    def legacy_items_add():
        return redirect(url_for("items_new"), code=301)

    # New-item route (with or without category in URL)
    @app.route("/categories/<int:category_id>/items/new", methods=["GET", "POST"])
    @app.route("/items/new", methods=["GET", "POST"])
    @login_required
    def items_new(category_id: int | None = None):
        # Prefill from querystring (e.g., scanner adds ?barcode=...)
        prefill = {"barcode": request.args.get("barcode", "")}

        # Categories for dropdown
        categories = (
            Category.query
            .filter_by(user_id=current_user.id)
            .order_by(Category.name.asc())
            .all()
        )

        # Selected category from URL or form
        cat_id = category_id or request.args.get("category_id", type=int) or request.form.get("category_id", type=int)
        category = (
            Category.query.filter_by(id=cat_id, user_id=current_user.id).first()
            if cat_id else None
        )

        if request.method == "POST":
            # Required title
            title = (request.form.get("title") or request.form.get("name") or "").strip()
            if not title:
                flash("Title is required.", "error")
                return render_template("item_form.html", categories=categories, category=category, prefill=prefill)

            # Require category
            if not category:
                flash("Please select a category.", "error")
                return render_template("item_form.html", categories=categories, category=None, prefill=prefill)

            # Parse inputs
            raw_barcode    = normalize_barcode(request.form.get("barcode") or "")
            purchase_price = parse_money(request.form.get("purchase_price"))
            list_price     = parse_money(request.form.get("list_price"))  # <-- LIST price (not listing_price)
            sold_price     = parse_money(request.form.get("sold_price"))
            purchase_date  = parse_date(request.form.get("purchase_date"))
            sold_date      = parse_date(request.form.get("sold_date"))
            purchase_src   = (request.form.get("purchase_source") or "").strip() or None
            notes          = (request.form.get("notes") or "").strip() or None
            size           = (request.form.get("size") or "").strip() or None
            color          = (request.form.get("color") or "").strip() or None
            condition      = (request.form.get("condition") or "").strip() or None

            # Optional photo upload
            photo_path = None
            if "photo" in request.files and request.files["photo"].filename:
                photo_path = save_upload(request.files["photo"])  # returns e.g. "uploads/uuid.jpg"

            # If barcode provided and already exists for this user, go to existing item
            if raw_barcode:
                existing = Item.query.filter_by(user_id=current_user.id, barcode=raw_barcode).first()
                if existing:
                    flash("Item with this barcode already exists; opening it.", "info")
                    return redirect(url_for("item_detail", item_id=existing.id))

            # Create the item
            item = Item(
                user_id=current_user.id,
                category_id=category.id,
                barcode=raw_barcode or None,
                title=title if hasattr(Item, "title") else None,
                size=size,
                color=color,
                condition=condition,
                notes=notes,
                purchase_source=purchase_src,
                purchase_price=purchase_price or Decimal("0.00"),
                list_price=list_price,     # may be None if you left it empty
                sold_price=sold_price,
                purchase_date=purchase_date,
                sold_date=sold_date,
                photo_path=photo_path
            )

            # Some schemas use 'name' instead of 'title'
            if not hasattr(Item, "title") and hasattr(Item, "name"):
                item.name = title
            # Handle photo upload
            if "photo" in request.files and request.files["photo"].filename:
                rel_path = save_upload(request.files["photo"])  # e.g., "uploads/abcd.jpg"
                if rel_path:
                    # Make sure your Item model has photo_path = db.Column(db.String(255))
                    item.photo_path = rel_path
                else:
                    # Optional: warn if extension invalid, etc.
                    flash("Photo not saved (file type not allowed).", "error")

            db.session.add(item)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Could not create item (possibly duplicate barcode).", "error")
                return render_template("item_form.html", categories=categories, category=category, prefill=prefill)

            flash("Item added.", "success")
            return redirect(url_for("item_detail", item_id=item.id))

        # GET → render the form (category can be None)
        return render_template("item_form.html", categories=categories, category=category, prefill=prefill)

    # Health check
    @app.route("/healthz")
    def healthz():
        return {"ok": True}

    return app


# WSGI entrypoint
app = create_app()
