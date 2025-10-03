# labels.py
from flask import Blueprint, request, render_template, abort, url_for
from flask_login import login_required, current_user
from io import BytesIO
import base64

from models import Item

# NEW: QR
import qrcode
from qrcode.constants import ERROR_CORRECT_M  # decent error correction

labels_bp = Blueprint("labels", __name__, template_folder="templates")

def _png_data_uri(binary: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(binary).decode("ascii")

def _render_qr_png(value: str, box_size: int = 8, border: int = 2) -> bytes:
    """
    Render a QR code (PNG).
    - box_size: pixels per square module (8–10 looks nice for 1–2 inch labels)
    - border: quiet zone modules (2–4 recommended)
    """
    qr = qrcode.QRCode(
        version=None,  # fit to data
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Printable sheet of QR code labels.

    Query params:
      - ids: comma-separated item IDs, e.g. ?ids=1,2,5 (required)
      - copies: number of copies per item (default 1)
      - cols: number of columns on the sheet (default 3)
      - size: preset (optional) one of: 'avery5160', 'avery5167', '2x1', '1.5x1'
      - content: 'item' (default) to encode the barcode/raw id, or 'url' to encode the item detail URL
      - show_text: '1' to show tiny human text under the QR (default 1)
    """
    ids_param = (request.args.get("ids") or "").strip()
    if not ids_param:
        abort(400, "Missing ?ids=...")

    try:
        item_ids = [int(x) for x in ids_param.split(",") if x.strip()]
    except Exception:
        abort(400, "Bad ids")

    copies    = max(1, min(100, int(request.args.get("copies", 1))))
    cols      = max(1, min(6,   int(request.args.get("cols", 3))))
    size      = (request.args.get("size") or "").lower()
    content   = (request.args.get("content") or "item").lower()
    show_text = request.args.get("show_text", "1") == "1"

    # Current user’s items only
    items = (
        Item.query
            .filter(Item.user_id == current_user.id, Item.id.in_(item_ids))
            .all()
    )

    labels = []
    for it in items:
        # What do we encode in the QR?
        if content == "url":
            # Absolute URL to item detail
            value = url_for("item_detail", item_id=it.id, _external=True)
            text_line = value
        else:
            # Raw identifier for inventory scanners
            value = (it.barcode or str(it.id)).strip()
            text_line = value

        png = _render_qr_png(value, box_size=8, border=2)
        data_uri = _png_data_uri(png)

        labels.extend([{
            "title":   it.title or "Untitled",
            "text":    text_line if show_text else "",
            "img":     data_uri,
        }] * copies)

    presets = {
        "avery5160": {"label_w": "2.625in", "label_h": "1.0in", "gap": "0.125in", "margin": "0.5in"},
        "avery5167": {"label_w": "1.75in",  "label_h": "0.5in", "gap": "0.125in", "margin": "0.5in"},
        "2x1":       {"label_w": "2.0in",   "label_h": "1.0in", "gap": "0.125in", "margin": "0.5in"},
        "1.5x1":     {"label_w": "1.5in",   "label_h": "1.0in", "gap": "0.125in", "margin": "0.5in"},
    }
    preset = presets.get(size) if size else None

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,
        preset=preset,
        is_qr=True  # if you want to branch in template later
    )