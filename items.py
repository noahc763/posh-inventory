# items.py
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, Item, Category
from utils import save_upload  # saving photos

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

def _round_up_cents(value: Decimal) -> Decimal:
    """
    Round UP to 2 decimals (ceil to the next cent).
    """
    if value is None:
        return None
    # convert dollars -> cents (as Decimal), ceil to integer, then back to dollars
    cents = (value * Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
    return cents / Decimal("100")

def _breakeven(purchase_price: Decimal | None) -> Decimal | None:
    """
    Poshmark fee: $2.95 if list < $15, else 20%.
    Find the minimum list price L such that L - fee(L) - purchase >= 0.
    Mirrors the JS used on the form.
    """
    if purchase_price is None or purchase_price <= 0:
        return None

    # Case 1: flat fee regime (list < $15)
    flat_candidate = purchase_price + Decimal("2.95")
    if flat_candidate < Decimal("15.00"):
        return _round_up_cents(flat_candidate)

    # Case 2: 20% regime (list >= $15) -> 0.8L = purchase => L = purchase / 0.8
    percent_candidate = purchase_price / Decimal("0.8")
    if percent_candidate < Decimal("15.00"):
        percent_candidate = Decimal("15.00")
    return _round_up_cents(percent_candidate)

# ---------- Routes ----------

@items_bp.route("/items/add", methods=["GET", "POST"])
@items_bp.route("/items/new", methods=["GET", "POST"])
@login_required
def add_item():
    if request.method == "GET":
        prefill = {
            "barcode": request.args.get("barcode", ""),
            "category_id": request.args.get("category_id", "")
        }
        return render_template(
            "add_edit_item.html",
            item=None,
            categories=_user_categories(),
            prefill=prefill,
            read_only=False
        )

    # POST create
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        flash("Title is required.", "error")
        return render_template(
            "add_edit_item.html",
            item=None,
            categories=_user_categories(),
            prefill={"barcode": f.get("barcode","")}, read_only=False
        )

    # Optional category
    category = None
    cat_id = f.get("category_id")
    if cat_id:
        try:
            category = Category.query.filter_by(
                id=int(cat_id), user_id=current_user.id
            ).first()
        except ValueError:
            category = None

    # Optional barcode, unique per user
    barcode = (f.get("barcode") or "").strip()
    if barcode:
        existing = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first()
        if existing:
            flash("An item with that barcode already exists.", "info")
            return redirect(url_for("item_detail", item_id=existing.id))

    purchase_price = _parse_money(f.get("purchase_price")) or Decimal("0.00")
    list_price = _parse_money(f.get("list_price"))
    sold_price = _parse_money(f.get("sold_price"))

    # If no list price was entered, auto-fill with breakeven (server-side safety)
    if list_price is None:
        be = _breakeven(purchase_price)
        if be is not None:
            list_price = be

    item = Item(
        user_id=current_user.id,
        category_id=(category.id if category else None),
        title=title,
        barcode=barcode or None,
        purchase_price=purchase_price,
        list_price=list_price,
        sold_price=sold_price,  # allow sold price at create
        purchase_date=_parse_date(f.get("purchase_date")),
        sold_date=_parse_date(f.get("sold_date")),
        purchase_source=f.get("purchase_source") or None,
        notes=f.get("notes") or None,
    )

    # Photo upload
    if "photo" in request.files and request.files["photo"].filename:
        rel_path = save_upload(request.files["photo"])  # e.g. "uploads/abcd.jpg"
        if rel_path:
            item.photo_path = rel_path
        else:
            flash("Photo not saved (file type not allowed).", "error")

    db.session.add(item)
    db.session.commit()
    flash("Item added.", "success")
    return redirect(url_for("item_detail", item_id=item.id))


@items_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    item = Item.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        form = request.form

        # Basic fields
        item.title = (form.get("title") or item.title).strip()
        item.notes = form.get("notes") or None

        # Barcode (optional; unique per user when present)
        new_barcode = (form.get("barcode") or "").strip() or None
        if new_barcode and new_barcode != (item.barcode or None):
            dup = Item.query.filter(
                Item.user_id == current_user.id,
                Item.barcode == new_barcode,
                Item.id != item.id
            ).first()
            if dup:
                flash("Another item already has that barcode.", "error")
                return redirect(url_for("items.edit_item", item_id=item.id))
        item.barcode = new_barcode

        # Category change (optional)
        cat_id = form.get("category_id")
        if cat_id:
            try:
                cat = Category.query.filter_by(id=int(cat_id), user_id=current_user.id).first()
                if cat:
                    item.category_id = cat.id
            except ValueError:
                pass

        # Money / dates
        pp = _parse_money(form.get("purchase_price"))
        if pp is not None:
            item.purchase_price = pp

        lp = _parse_money(form.get("list_price"))
        if lp is None:
            # If user cleared it, set to server breakeven for safety
            be = _breakeven(item.purchase_price or Decimal("0.00"))
            item.list_price = be
        else:
            item.list_price = lp

        item.purchase_source = form.get("purchase_source") or None
        item.purchase_date   = _parse_date(form.get("purchase_date"))

        # Optional sold fields
        sold_price = _parse_money(form.get("sold_price"))
        sold_date  = _parse_date(form.get("sold_date"))
        if sold_price is not None:
            item.sold_price = sold_price
        if sold_date is not None:
            item.sold_date = sold_date

        # Photo upload
        if "photo" in request.files and request.files["photo"].filename:
            rel_path = save_upload(request.files["photo"])
            if rel_path:
                item.photo_path = rel_path
            else:
                flash("Photo not saved (file type not allowed).", "error")

        try:
            db.session.commit()
            flash("Item updated", "success")
        except Exception:
            db.session.rollback()
            flash("Could not update item (possibly barcode duplicate).", "error")

        return redirect(url_for("item_detail", item_id=item.id))

    # GET: render edit form
    return render_template("add_edit_item.html", item=item, categories=_user_categories(), read_only=False, prefill={})


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
    Item.query.filter(
        Item.user_id == current_user.id,
        Item.id.in_(id_list)
    ).delete(synchronize_session=False)
    db.session.commit()

    flash(f"Deleted {len(id_list)} item(s).", "success")
    return redirect(url_for("dashboard"))


@items_bp.route("/items/by_barcode/<barcode>")
@login_required
def by_barcode(barcode):
    # Quick redirect helper by barcode
    item = Item.query.filter_by(user_id=current_user.id, barcode=barcode).first_or_404()
    return redirect(url_for("item_detail", item_id=item.id))
