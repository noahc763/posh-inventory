# labels.py
import io
import string
from flask import Blueprint, send_file, request, render_template, abort, url_for
from flask_login import login_required, current_user
from models import db, Item
import barcode
from barcode.writer import ImageWriter

labels_bp = Blueprint("labels", __name__, template_folder="templates")

# Short internal code like "PI3F9" (base36 of item id)
def _base36(n: int) -> str:
    if n <= 0: return "0"
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append(chars[r])
    return "".join(reversed(out))

def _item_code_text(item: Item) -> str:
    # Prefer stored product barcode if present, else internal short code
    if item.barcode:
        return item.barcode.strip()
    return f"PI{_base36(item.id)}"

@labels_bp.get("/items/<int:item_id>/barcode.png")
@login_required
def item_barcode_png(item_id: int):
    item = Item.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        abort(404)
    code_text = _item_code_text(item)

    # Generate Code128 PNG
    buf = io.BytesIO()
    code = barcode.get("code128", code_text, writer=ImageWriter())
    # Tune these for your printer/label size
    opts = {
        "module_width": 0.25,     # bar width in mm-ish; bigger = wider
        "module_height": 18.0,    # bar height (mm-ish)
        "font_size": 10,
        "text_distance": 1.0,
        "quiet_zone": 2.0,        # left/right padding
        "write_text": True,       # show human-readable text under bars
    }
    code.write(buf, opts)
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     as_attachment=False,
                     download_name=f"item-{item_id}-barcode.png")

@labels_bp.get("/labels/print")
@login_required
def labels_print():
    # Usage: /labels/print?ids=1,2,3  (order matters)
    raw = (request.args.get("ids") or "").strip()
    if not raw:
        abort(400, description="Provide ?ids=comma-separated item ids")
    ids = []
    for part in raw.split(","):
        try:
            ids.append(int(part))
        except ValueError:
            continue

    items = (Item.query
             .filter(Item.user_id == current_user.id, Item.id.in_(ids))
             .order_by(Item.id.in_(ids).desc()) # simple keep-order hint
             .all())

    # Options (optional query params)
    include_title = request.args.get("title", "1") != "0"   # default on
    include_price = request.args.get("price", "0") == "1"   # default off

    return render_template("labels_print.html",
                           items=items,
                           include_title=include_title,
                           include_price=include_price)
