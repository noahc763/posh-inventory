# app.py
import os
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, make_response
from flask_login import LoginManager, login_required, current_user

from config import Config
from models import db, Item, Category, User
from auth import auth_bp
from items import items_bp
from categories import categories_bp  # <-- import the categories blueprint


def create_app():
    # Make template/static folder resolution explicit (helps avoid TemplateNotFound)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(Config)

    # Database
    db.init_app(app)
    with app.app_context():
        db.create_all()  # creates tables if they don't exist (User, Category, Item, ...)

    # Auth
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)
    app.register_blueprint(categories_bp)  # <-- register it here

    # Routes
    @app.route('/')
    @login_required
    def dashboard():
        # Optional filter by category (from ?category=<id>)
        cat_id = request.args.get('category', type=int)
        q = Item.query.filter_by(user_id=current_user.id)
        if cat_id:
            q = q.filter(Item.category_id == cat_id)
        items = q.order_by(Item.created_at.desc()).all()

        # For the filter dropdown
        cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()

        return render_template('dashboard.html', items=items, categories=cats, selected_cat=cat_id)

    @app.route('/items/<int:item_id>')
    @login_required
    def item_detail(item_id: int):
        item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
        return render_template('item_detail.html', item=item, Decimal=Decimal)

    # (optional) quick health check
    @app.route('/healthz')
    def healthz():
        return {"ok": True}

    @app.after_request
    def add_headers(resp):
        # Allow camera on same-origin pages
        resp.headers["Permissions-Policy"] = "camera=(self)"
        # Optional CSP to be safer; adjust if you use additional CDNs
        resp.headers["Content-Security-Policy"] = "default-src 'self' https: 'unsafe-inline' 'unsafe-eval' blob: data:;"
        return resp

    @app.route("/scan")
    def scan():
        resp = make_response(render_template("scan.html"))
        return resp
    return app


# WSGI entrypoint
app = create_app()
