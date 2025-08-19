from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os

from models import db, Item, Category
from posh import profit_after_fees
from utils import allowed_file, save_upload

items_bp = Blueprint('items', __name__)

@items_bp.route('/items/add', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        form = request.form
        title = form.get('title')
        if not title:
            flash('Title is required', 'error')
            return render_template('add_edit_item.html', item=None, categories=_user_categories())

        photo_path = None
        if 'photo' in request.files and request.files['photo'].filename:
            photo_path = save_upload(request.files['photo'])

        item = Item(
            user_id=current_user.id,
            title=title,
            brand=form.get('brand') or None,
            size=form.get('size') or None,
            color=form.get('color') or None,
            condition=form.get('condition') or None,
            notes=form.get('notes') or None,
            barcode=form.get('barcode') or None,
            category_id=int(form.get('category_id') or 0) or None,
            purchase_source=form.get('purchase_source') or None,
            purchase_price=Decimal(form.get('purchase_price') or 0),
            purchase_date=(form.get('purchase_date') or None),
            list_price=Decimal(form.get('list_price') or 0) or None,
            photo_path=photo_path
        )
        db.session.add(item)
        db.session.commit()
        flash('Item added', 'success')
        return redirect(url_for('item_detail', item_id=item.id))

    return render_template('add_edit_item.html', item=None, categories=_user_categories())

@items_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    if request.method == 'POST':
        form = request.form
        item.title = form.get('title') or item.title
        item.brand = form.get('brand') or None
        item.size = form.get('size') or None
        item.color = form.get('color') or None
        item.condition = form.get('condition') or None
        item.notes = form.get('notes') or None
        item.barcode = form.get('barcode') or None
        item.category_id = int(form.get('category_id') or 0) or None
        item.purchase_source = form.get('purchase_source') or None
        item.purchase_price = Decimal(form.get('purchase_price') or 0)
        item.purchase_date = (form.get('purchase_date') or None)
        item.list_price = Decimal(form.get('list_price') or 0) or None

        if 'photo' in request.files and request.files['photo'].filename:
            item.photo_path = save_upload(request.files['photo'])

        # Optional: mark sold
        sold_price = form.get('sold_price')
        sold_date = form.get('sold_date')
        if sold_price:
            item.sold_price = Decimal(sold_price)
        if sold_date:
            item.sold_date = sold_date

        db.session.commit()
        flash('Item updated', 'success')
        return redirect(url_for('item_detail', item_id=item.id))

    return render_template('add_edit_item.html', item=item, categories=_user_categories())

@items_bp.route('/scan', methods=['GET', 'POST'])
@login_required
def scan():
    # POST when barcode was typed/scanned manually
    if request.method == 'POST':
        code = request.form.get('barcode', '').strip()
        if not code:
            flash('Scan or type a barcode', 'error')
            return render_template('scan.html')
        item = Item.query.filter_by(user_id=current_user.id, barcode=code).first()
        if item:
            return redirect(url_for('item_detail', item_id=item.id))
        flash('No item with that barcode yet — fill the form to create one.', 'info')
        return redirect(url_for('items.add_item') + f"?barcode={code}")
    return render_template('scan.html')

@items_bp.route('/items/by_barcode/<barcode>')
@login_required
def by_barcode(barcode):
    item = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first_or_404()
    return redirect(url_for('item_detail', item_id=item.id))

# helpers

def _user_categories():
    return Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
