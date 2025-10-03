from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import delete

from models import db, Item, Category

items_bp = Blueprint("items", __name__)

# ---------- Helpers ----------

def _parse_money(v):
    try:
        return Decimal(v)
    except Exception:
        return None

def _parse_date(v):
    try:
        return datetime.strptime(v, "%Y-%m-%d").date() if v else None
    except Exception:
        return None

def _user_categories():
    return (
        Category.query.filter_by(user_id=current_user.id)
        .order_by(Category.name.asc())
        .all()
    )

# ---------- Routes (keep only what’s needed) ----------

@items_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        form = request.form

        # Names here should match your templates (you removed size/color/condition from the form)
        item.title = form.get("title") or item.title
        item.notes = form.get("notes") or None

        # Barcode (optional in your schema, but unique per user when present)
        item.barcode = (form.get("barcode") or None)

        # Category change (optional)
        cat_id = form.get("category_id")
        if cat_id:
            cat = Category.query.filter_by(id=int(cat_id), user_id=current_user.id).first()
            if cat:
                item.category_id = cat.id

        # Money / dates
        item.purchase_source = form.get("purchase_source") or None
        item.purchase_price  = _parse_money(form.get("purchase_price")) or item.purchase_price
        item.list_price      = _parse_money(form.get("list_price"))
        item.purchase_date   = _parse_date(form.get("purchase_date"))

        # Optional sold fields
        sold_price = _parse_money(form.get("sold_price"))
        sold_date  = _parse_date(form.get("sold_date"))
        if sold_price is not None:
            item.sold_price = sold_price
        if sold_date is not None:
            item.sold_date = sold_date

        try:
            db.session.commit()
            flash("Item updated", "success")
        except Exception as e:
            db.session.rollback()
            flash("Could not update item (possibly barcode duplicate).", "error")

        return redirect(url_for("item_detail", item_id=item.id))

    # GET: render edit form (if you use it)
    return render_template("add_edit_item.html", item=item, categories=_user_categories())

@items_bp.post("/items/<int:item_id>/delete")
@login_required
def delete_item(item_id: int):
    item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()

    # JSON/AJAX support
    wants_json = request.accept_mimetypes.best == "application/json" or request.is_json
    if wants_json:
        return jsonify({"ok": True}), 200

    flash("Item deleted.", "success")
    return redirect(url_for("dashboard"))


@items_bp.post("/items/bulk_delete")
@login_required
def bulk_delete_items():
    ids_raw = (request.form.get("ids") or "").strip()
    if not ids_raw:
        return redirect(url_for("dashboard"))

    try:
        id_list = [int(x) for x in ids_raw.split(",") if x.strip()]
    except Exception:
        flash("Invalid selection.", "error")
        return redirect(url_for("dashboard"))

    if not id_list:
        return redirect(url_for("dashboard"))

    # Only delete the current user's items
    Item.query.filter(Item.user_id == current_user.id, Item.id.in_(id_list)).delete(synchronize_session=False)
    db.session.commit()

    flash(f"Deleted {len(id_list)} item(s).", "success")
    return redirect(url_for("dashboard"))

@items_bp.route("/items/by_barcode/<barcode>")
@login_required
def by_barcode(barcode):
    # Quick redirect helper by barcode
    item = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first_or_404()
    return redirect(url_for("item_detail", item_id=item.id))
