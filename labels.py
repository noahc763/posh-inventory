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

def _normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").strip() if ch.isalnum())

def _choose_symbology(code: str) -> Tuple[str, str]:
    """
    Prefer UPC-A for 12-digit numeric, EAN-13 for 13-digit numeric, else Code128.
    Return (symbology, normalized_code).
    """
    s = _normalize_code(code)
    if s.isdigit() and len(s) == 12:
        # UPC-A: many printers/data sets use 12 with check already present.
        # python-barcode accepts 11 or 12; if it rejects, we'll fallback.
        return ("upc", s)
    if s.isdigit() and len(s) == 13:
        return ("ean13", s)
    return ("code128", s)

def _barcode_png_data_url(code: str, dpi: int = 300, write_text: bool = True) -> str:
    """
    Generate a crisp PNG barcode as a data URL. Tuned for 40×30 mm labels.
    """
    sym, normalized = _choose_symbology(code)
    writer = ImageWriter()
    options = {
        # ~0.20 mm per module gives good density for 203–300 DPI label printers
        "module_width": 0.20,
        "module_height": 18.0,   # bar height (mm), leaves room for HRT inside the image
        "quiet_zone": 2.0,       # mm
        "font_size": 10,         # human-readable text
        "text_distance": 1.0,    # mm gap between bars and digits
        "write_text": bool(write_text),
        "dpi": dpi,
        "background": "white",
        "foreground": "black",
    }

    # Render into memory, with safe fallback to Code128 on validation errors
    bio = BytesIO()
    try:
        bc = bc_get(sym, normalized, writer=writer)
        bc.write(bio, options=options)
    except Exception:
        # Fallback if, e.g., UPC/EAN length/check digit validation fails
        bio = BytesIO()
        bc = bc_get("code128", normalized, writer=writer)
        bc.write(bio, options=options)

    png = bio.getvalue()
    b64 = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _labels_for_items(items: List[Item], dpi: int) -> List[dict]:
    """
    Build label payloads; one dict per label.
    We embed only the PNG (with digits rendered by python-barcode).
    """
    out: List[dict] = []
    for it in items:
        code = (it.barcode or "").strip()
        if not code:
            continue
        img = _barcode_png_data_url(code, dpi=dpi, write_text=True)
        out.append({"barcode": code, "img": img})
    return out

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Printable labels (40×30 mm by default).
    Query params:
      ids    = comma-separated item IDs (required)
      dpi    = printer DPI (203 or 300 typical; default 300)
      cols   = columns (1 for roll printers; default 1)
      copies = copies per item (default 1)
    """
    ids_raw = (request.args.get("ids") or "").strip()
    if not ids_raw:
        abort(400, "Missing ids")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except Exception:
        abort(400, "Invalid ids")

    # Only items owned by current user
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
        cols = int(request.args.get("cols") or 1)
    except Exception:
        cols = 1
    try:
        copies = max(1, int(request.args.get("copies") or 1))
    except Exception:
        copies = 1

    labels = _labels_for_items(items, dpi=dpi)
    labels = [lab for lab in labels for _ in range(copies)]  # replicate copies

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,             # <-- match template variable names
        label_w="40mm",
        label_h="30mm",
        gap="2mm",
        margin="4mm",
        dpi=dpi,
    )
