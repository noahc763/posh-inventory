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
        return ("upc", s)
    if s.isdigit() and len(s) == 13:
        return ("ean13", s)
    return ("code128", s)

def _render_barcode(sym: str, payload: str, *, dpi: int, write_text: bool, module_width: float = 0.26) -> bytes:
    """
    Render a barcode PNG (bytes) using python-barcode ImageWriter.
    Sizes tuned for 40×30 mm labels. module_width is in millimeters.
    """
    writer = ImageWriter()
    options = {
        "module_width": module_width,  # mm per narrow bar; tweak to fill width at your DPI
        "module_height": 18.0,         # mm bar height (area above digits)
        "quiet_zone": 2.0,             # mm left/right padding
        "font_size": 10,               # human-readable text size
        "text_distance": 1.2,          # mm gap between bars and digits (helps avoid overlap)
        "write_text": bool(write_text),
        "dpi": int(dpi),
        "background": "white",
        "foreground": "black",
    }
    bio = BytesIO()
    bc = bc_get(sym, payload, writer=writer)
    bc.write(bio, options=options)
    return bio.getvalue()

def _barcode_png_data_url(code: str, dpi: int = 300, write_text: bool = True) -> str:
    """
    Generate a crisp PNG barcode as a data URL. Tuned for 40×30 mm labels.
    Handles UPC 12 vs 11 rules gracefully before falling back to Code128.
    """
    sym, normalized = _choose_symbology(code)

    png_bytes: bytes | None = None

    if sym == "upc":
        # Try with 12 first (some versions accept), then try first 11 (lib computes checksum)
        try:
            png_bytes = _render_barcode("upc", normalized, dpi=dpi, write_text=write_text)
        except Exception:
            if len(normalized) == 12 and normalized.isdigit():
                try:
                    png_bytes = _render_barcode("upc", normalized[:11], dpi=dpi, write_text=write_text)
                except Exception:
                    png_bytes = None
    elif sym == "ean13":
        try:
            png_bytes = _render_barcode("ean13", normalized, dpi=dpi, write_text=write_text)
        except Exception:
            # Try without last digit to let library compute checksum
            if len(normalized) == 13 and normalized.isdigit():
                try:
                    png_bytes = _render_barcode("ean13", normalized[:12], dpi=dpi, write_text=write_text)
                except Exception:
                    png_bytes = None

    # Fallback to Code128 if needed or for arbitrary payloads
    if png_bytes is None:
        png_bytes = _render_barcode("code128", normalized, dpi=dpi, write_text=write_text)

    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _labels_for_items(items: List[Item], dpi: int) -> List[dict]:
    """
    Build label payloads; one dict per label. We embed only the PNG (with digits rendered).
    """
    out: List[dict] = []
    for it in items:
        code = (it.barcode or "").strip()
        if not code:
            continue
        img = _barcode_png_data_url(code, dpi=dpi, write_text=False)
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
        cols = int(request.args.get("cols") or 1)
    except Exception:
        cols = 1
    try:
        copies = max(1, int(request.args.get("copies") or 1))
    except Exception:
        copies = 1

    labels = _labels_for_items(items, dpi=dpi)
    labels = [lab for lab in labels for _ in range(copies)]  # duplicate for copies

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,
        label_w="40mm",
        label_h="30mm",
        gap="2mm",
        margin="4mm",
        dpi=dpi,
    )
