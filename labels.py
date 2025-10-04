# labels.py
from io import BytesIO
import base64
from typing import List, Tuple

from flask import Blueprint, request, render_template, abort
from flask_login import login_required, current_user

from models import db, Item
from barcode import get as bc_get
from barcode.writer import ImageWriter

labels_bp = Blueprint("labels", __name__)

def _choose_symbology(code: str) -> Tuple[str, str]:
    """
    Choose UPC-A for 12-digit numeric, EAN13 for 13-digit numeric, else Code128.
    Returns (symbology_name_for_python-barcode, normalized_code).
    """
    s = "".join(ch for ch in (code or "").strip() if ch.isalnum())
    if s.isdigit() and len(s) == 12:
        return ("upc", s)       # UPC-A (12 digits)
    if s.isdigit() and len(s) == 13:
        return ("ean13", s)     # EAN-13
    return ("code128", s)       # fallback handles mixed length/alpha

def _barcode_png_data_url(code: str, dpi: int = 300, write_text: bool = True) -> str:
    """
    Generate a high-quality PNG barcode as a data: URL, tuned for 40×30 mm labels.
    We let python-barcode render at the requested DPI, with sensible mm-based sizes.
    """
    sym, normalized = _choose_symbology(code)
    writer = ImageWriter()

    # For 40×30 mm: bars ~18–20 mm tall leaves room for HRT (digits) and quiet zones.
    # Units for module_width/height/quiet_zone/text_distance are millimeters.
    writer_options = {
        "module_width": 0.20,      # mm per narrow module (tweak if you want denser bars)
        "module_height": 18.0,     # mm bar height (not counting human-readable text)
        "quiet_zone": 2.0,         # mm whitespace on left/right
        "font_size": 10,           # HRT text below bars
        "text_distance": 1.0,      # mm gap between bars and digits
        "write_text": bool(write_text),
        "dpi": dpi,                # <-- true device DPI (203 or 300 are common)
        "background": "white",
        "foreground": "black",
    }

    # Render into memory
    bio = BytesIO()
    bc = bc_get(sym, normalized, writer=writer)
    bc.write(bio, options=writer_options)
    png = bio.getvalue()

    b64 = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _labels_for_items(items: List[Item], dpi: int) -> List[dict]:
    """
    Build label payloads.
    We print only the barcode image (with human-readable digits inside the image).
    """
    out = []
    for it in items:
        code = it.barcode or ""
        if not code:
            # skip items with no barcode (or you can render a placeholder)
            continue
        img = _barcode_png_data_url(code, dpi=dpi, write_text=True)
        out.append({
            "barcode": code,
            "img": img,
        })
    return out

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Print labels for the selected items.
    Query params:
        ids   = comma-separated item ids   (required)
        dpi   = target printer DPI          (default 300; use 203 for many thermal printers)
        cols  = number of columns           (default 1 for roll printers)
        copies= copies per item             (default 1)
    The template is fixed to 40×30 mm label geometry.
    """
    ids_raw = (request.args.get("ids") or "").strip()
    if not ids_raw:
        abort(400, "Missing ids")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except Exception:
        abort(400, "Invalid ids")

    # Only current user's items
    items = (
        Item.query
        .filter(Item.user_id == current_user.id, Item.id.in_(ids))
        .order_by(Item.id.asc())
        .all()
    )
    if not items:
        abort(404, "No items found")

    # Params
    try:
        dpi = int(request.args.get("dpi") or 300)
    except Exception:
        dpi = 300
    try:
        cols = int(request.args.get("cols") or 1)  # roll printers: 1 column
    except Exception:
        cols = 1
    try:
        copies = max(1, int(request.args.get("copies") or 1))
    except Exception:
        copies = 1

    labels = _labels_for_items(items, dpi=dpi)
    # replicate copies
    labels = [lab for lab in labels for _ in range(copies)]

    return render_template(
        "labels_print.html",
        labels=labels,
        _cols=cols,            # CSS variable
        _label_w="40mm",
        _label_h="30mm",
        _gap="2mm",
        _margin="4mm",
        _dpi=dpi,
    )
