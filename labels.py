# labels.py
from io import BytesIO
import base64
from typing import List, Tuple

from flask import Blueprint, request, render_template, abort
from flask_login import login_required, current_user

from models import Item
from barcode import get as bc_get
from barcode.writer import ImageWriter

from PIL import Image  # Pillow is already in your deps

labels_bp = Blueprint("labels", __name__)

# ----------------- helpers -----------------

def _mm_to_px(mm: float, dpi: int) -> int:
    # 1 inch = 25.4 mm
    return int(round(mm * dpi / 25.4))

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

def _render_barcode_png(sym: str, code: str, options: dict) -> bytes:
    """Render a python-barcode PNG to bytes with given writer options."""
    writer = ImageWriter()
    bio = BytesIO()
    bc = bc_get(sym, code, writer=writer)
    bc.write(bio, options=options)
    return bio.getvalue()

def _barcode_png_data_url(code: str,
                          label_w_mm: float,
                          label_h_mm: float,
                          dpi: int = 300,
                          reserve_top_mm: float = 0.0,
                          write_text: bool = True) -> str:
    """
    Render a barcode that grows to fill the available label area.

    - label_w_mm / label_h_mm: total label dimensions
    - reserve_top_mm: space kept for price text above the image
    - write_text: keep digits inside image (True) or not
    """
    sym, normalized = _choose_symbology(code)

    # Target box for the image (leave a little bottom breathing room too)
    target_w_px = _mm_to_px(label_w_mm, dpi)
    target_h_px = _mm_to_px(max(0.0, label_h_mm - reserve_top_mm), dpi)

    # If something odd, fall back
    target_w_px = max(target_w_px, 40)
    target_h_px = max(target_h_px, 40)

    # We’ll binary-search module_width (in mm). Height & font scale with it.
    # Reasonable bounds for label printers (203–300dpi) on 40×30mm:
    lo, hi = 0.12, 0.40  # mm per module (narrowest bar)
    best_png = None
    best_area = -1

    # Some constants (in mm) that we’ll scale a bit
    base_quiet = 1.6     # quiet zone each side
    base_text_gap = 0.8  # gap between bars and HRT
    base_height = 17.0   # bar height mm at mid module width
    base_font_px_at_300dpi = 11  # readable HRT at 300 dpi

    # We’ll do ~18 iterations to converge
    for _ in range(18):
        mw = (lo + hi) / 2.0  # module_width mm
        scale = mw / 0.26     # relative to a comfortable mid density

        # Dynamically scale bar height + text details
        module_height = max(12.0, min(22.0, base_height * (0.85 + 0.3 * scale)))
        quiet_zone = max(1.0, min(3.0, base_quiet * (0.9 + 0.4 * scale)))
        text_distance = max(0.6, min(1.6, base_text_gap * (0.9 + 0.4 * scale)))

        # Font size in *pixels* (python-barcode expects px for PIL font)
        font_px = int(round(base_font_px_at_300dpi * (dpi / 300.0) * (0.95 + 0.25 * scale)))
        font_px = max(9, min(16, font_px))

        options = {
            "module_width": mw,
            "module_height": module_height,
            "quiet_zone": quiet_zone,
            "font_size": font_px,
            "text_distance": text_distance,
            "write_text": bool(write_text),
            "dpi": dpi,
            "background": "white",
            "foreground": "black",
        }

        try:
            png = _render_barcode_png(sym, normalized, options)
        except Exception:
            # Fallback to code128 if strict UPC/EAN reject
            try:
                sym = "code128"
                png = _render_barcode_png(sym, normalized, options)
            except Exception:
                # If all fails, break
                break

        # Measure rendered image
        try:
            im = Image.open(BytesIO(png))
            w, h = im.size
        except Exception:
            break

        fits = (w <= target_w_px) and (h <= target_h_px)
        area = w * h

        if fits:
            # Keep the largest that fits
            if area > best_area:
                best_area = area
                best_png = png
            # Try to grow more
            lo = mw
        else:
            # Too big, shrink
            hi = mw

    # If search failed, render a safe default
    if best_png is None:
        options = {
            "module_width": 0.26,
            "module_height": 18.0,
            "quiet_zone": 2.0,
            "font_size": int(round(11 * (dpi / 300.0))),
            "text_distance": 1.0,
            "write_text": bool(write_text),
            "dpi": dpi,
            "background": "white",
            "foreground": "black",
        }
        try:
            best_png = _render_barcode_png(sym, normalized, options)
        except Exception:
            best_png = _render_barcode_png("code128", normalized, options)

    b64 = base64.b64encode(best_png).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _labels_for_items(items: List[Item],
                      dpi: int,
                      label_w_mm: float,
                      label_h_mm: float,
                      show_price: bool) -> List[dict]:
    """
    Build the label payloads with dynamic-sized barcodes.
    """
    out: List[dict] = []
    # Reserve ~3.5 mm for price line if we show price
    reserve_top_mm = 3.5 if show_price else 0.0

    for it in items:
        code = (it.barcode or "").strip()
        if not code:
            continue

        img = _barcode_png_data_url(
            code,
            label_w_mm=label_w_mm,
            label_h_mm=label_h_mm,
            dpi=dpi,
            reserve_top_mm=reserve_top_mm,
            write_text=True,   # keep digits inside the image
        )

        price_str = None
        if show_price and it.list_price is not None:
            price_str = f"${float(it.list_price):.2f}"

        out.append({
            "barcode": code,
            "img": img,
            "price": price_str,
        })

    return out

# ----------------- route -----------------

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Printable labels (defaults: 40×30 mm, 1 column, DPI=300).
    Query params:
      ids      = comma-separated item IDs (required)
      dpi      = printer DPI (203 or 300 typical; default 300)
      cols     = number of columns (1 for rolls; default 1)
      copies   = copies per item (default 1)
      label_w  = label width, e.g. "40mm" or "1.57in" (default 40mm)
      label_h  = label height, e.g. "30mm" or "1.18in" (default 30mm)
      price    = "1" to show price above the barcode (default off)
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
    def _parse_length(s: str, default_mm: float) -> float:
        if not s:
            return default_mm
        s = s.strip().lower()
        try:
            if s.endswith("mm"):
                return float(s[:-2])
            if s.endswith("in") or s.endswith('"'):
                val = float(s.rstrip('"').rstrip("in"))
                return val * 25.4
            # bare number -> assume mm
            return float(s)
        except Exception:
            return default_mm

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

    label_w_mm = _parse_length(request.args.get("label_w"), 40.0)
    label_h_mm = _parse_length(request.args.get("label_h"), 30.0)
    show_price = (request.args.get("price") == "1")

    labels = _labels_for_items(items, dpi=dpi, label_w_mm=label_w_mm, label_h_mm=label_h_mm, show_price=show_price)
    # replicate copies
    labels = [lab for lab in labels for _ in range(copies)]

    # Pass strings back to template for CSS variables
    label_w_str = f"{label_w_mm:.2f}mm"
    label_h_str = f"{label_h_mm:.2f}mm"

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,
        label_w=label_w_str,
        label_h=label_h_str,
        gap="0mm",
        margin="0mm",
        dpi=dpi,
    )
