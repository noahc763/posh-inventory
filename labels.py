# labels.py
from flask import Blueprint, request, render_template, abort
from flask_login import login_required, current_user
from io import BytesIO
import base64

from models import Item

# python-barcode
from barcode import Code128, EAN13, EAN8, UPCA
from barcode.writer import ImageWriter  # -> PNG via Pillow

labels_bp = Blueprint("labels", __name__, template_folder="templates")

def _png_data_uri(binary: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(binary).decode("ascii")

def _render_barcode_png(value: str, scale: float = 2.0, text: bool = True) -> bytes:
    """
    Render a barcode to PNG bytes. Chooses a symbology that fits the value.
    """
    value = (value or "").strip()

    # Pick a reasonable symbology based on length/content
    writer = ImageWriter()
    writer_options = {
        "module_width": 0.2,     # bar width in mm (smaller = more compact)
        "module_height": 15.0,   # bar height in mm
        "font_size": 10,
        "text_distance": 1.0,
        "write_text": bool(text),
        "quiet_zone": 2.0,
        "dpi": int(300 * scale), # crisp on print
    }

    # Try numeric-specific types first; fall back to Code128 (handles alphanum)
    BarcodeClass = Code128
    if value.isdigit():
        if len(value) == 8:
            BarcodeClass = EAN8
        elif len(value) == 12:
            BarcodeClass = UPCA
        elif len(value) == 13:
            BarcodeClass = EAN13

    code = BarcodeClass(value, writer=writer)
    buf = BytesIO()
    code.write(buf, options=writer_options)
    return buf.getvalue()

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Render a printable sheet of barcode labels.

    Query params:
      - ids: comma-separated item IDs, e.g. ?ids=1,2,5
      - copies: number of copies per item (default 1)
      - cols: number of columns on the sheet (default 3, good for Avery 5160)
      - show_text: '1' to show human text under barcode (default 1)
      - size: preset (optional) one of: 'avery5160', 'avery5167', '2x1', '1.5x1'
    """
    ids_param = (request.args.get("ids") or "").strip()
    if not ids_param:
        abort(400, "Missing ?ids=...")

    try:
        item_ids = [int(x) for x in ids_param.split(",") if x.strip()]
    except Exception:
        abort(400, "Bad ids")

    copies = max(1, min(100, int(request.args.get("copies", 1))))
    cols = max(1, min(6, int(request.args.get("cols", 3))))
    show_text = request.args.get("show_text", "1") == "1"
    size = (request.args.get("size") or "").lower()

    # Fetch only the current user’s items
    items = (
        Item.query
            .filter(Item.user_id == current_user.id, Item.id.in_(item_ids))
            .all()
    )
    # Build label data (repeat per copies)
    labels = []
    for it in items:
        value = it.barcode or str(it.id)
        png = _render_barcode_png(value, scale=2.0, text=show_text)
        data_uri = _png_data_uri(png)
        labels.extend([{
            "title": it.title or "Untitled",
            "barcode": value,
            "img": data_uri,
        }] * copies)

    # Presets for common sheets (CSS variables in template)
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
    )
