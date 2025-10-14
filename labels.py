from io import BytesIO
import base64
from typing import List, Tuple

from flask import Blueprint, request, render_template, abort
from flask_login import login_required, current_user

from models import Item
from barcode import get as bc_get
from barcode.writer import ImageWriter
from PIL import Image
from decimal import Decimal

labels_bp = Blueprint("labels", __name__)

def _mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / 25.4))

def _normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").strip() if ch.isalnum())

def _choose_symbology(code: str) -> Tuple[str, str]:
    s = _normalize_code(code)
    if s.isdigit() and len(s) == 12:
        return ("upc", s)
    if s.isdigit() and len(s) == 13:
        return ("ean13", s)
    return ("code128", s)

def _render_barcode_png(sym: str, code: str, options: dict) -> bytes:
    bio = BytesIO()
    bc = bc_get(sym, code, writer=ImageWriter())
    bc.write(bio, options=options)
    return bio.getvalue()

def _barcode_png_data_url(
    code: str,
    label_w_mm: float,
    label_h_mm: float,
    dpi: int = 300,
    reserve_top_mm: float = 0.0,
    reserve_bottom_mm: float = 3.5,
) -> str:
    """
    Render a barcode to fill label space.
    No digits baked in (write_text=False).
    Digits shown separately in HTML.
    """
    sym, normalized = _choose_symbology(code)

    target_w_px = _mm_to_px(label_w_mm, dpi)
    avail_h_mm = max(0.0, label_h_mm - reserve_top_mm - reserve_bottom_mm)
    target_h_px = _mm_to_px(avail_h_mm, dpi)

    best_png, best_area = None, -1
    lo, hi = 0.12, 0.40

    for _ in range(18):
        mw = (lo + hi) / 2.0
        options = {
            "module_width": mw,
            "module_height": 18.0,
            "quiet_zone": 2.0,
            "write_text": False,  # no text inside image
            "dpi": dpi,
            "background": "white",
            "foreground": "black",
        }

        try:
            png = _render_barcode_png(sym, normalized, options)
        except Exception:
            try:
                png = _render_barcode_png("code128", normalized, options)
                sym = "code128"
            except Exception:
                break

        try:
            w, h = Image.open(BytesIO(png)).size
        except Exception:
            break

        fits = (w <= target_w_px) and (h <= target_h_px)
        area = w * h
        if fits and area > best_area:
            best_area, best_png = area, png
            lo = mw
        else:
            hi = mw

    if best_png is None:
        options = {
            "module_width": 0.26,
            "module_height": 18.0,
            "quiet_zone": 2.0,
            "write_text": False,
            "dpi": dpi,
            "background": "white",
            "foreground": "black",
        }
        best_png = _render_barcode_png(sym, normalized, options)

    b64 = base64.b64encode(best_png).decode("ascii")
    return f"data:image/png;base64,{b64}"

def _labels_for_items(items: List[Item], dpi: int, label_w_mm: float, label_h_mm: float, show_price: bool) -> List[dict]:
    out = []
    reserve_top_mm = 3.5 if show_price else 0.0
    reserve_bottom_mm = 3.5

    for it in items:
        code = (it.barcode or "").strip()
        if not code:
            continue

        img = _barcode_png_data_url(
            code,
            label_w_mm,
            label_h_mm,
            dpi,
            reserve_top_mm,
            reserve_bottom_mm,
        )

        price_str = None
        if show_price and it.list_price is not None:
            price_str = f"${float(it.list_price):.2f}"

        out.append({
            "barcode": code,
            "human": code,
            "img": img,
            "price": price_str,
        })
    return out

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    ids_raw = (request.args.get("ids") or "").strip()
    if not ids_raw:
        abort(400, "Missing ids")
    try:
        ids = [int(x) for x in ids_raw.split(",") if x.strip()]
    except Exception:
        abort(400, "Invalid ids")

    items = (
        Item.query
        .filter(Item.user_id == current_user.id, Item.id.in_(ids))
        .order_by(Item.id.asc())
        .all()
    )
    if not items:
        abort(404, "No items found")

    def _len_mm(s: str | None, default_mm: float) -> float:
        if not s:
            return default_mm
        s = s.strip().lower()
        try:
            if s.endswith("mm"): return float(s[:-2])
            if s.endswith("in") or s.endswith('"'): return float(s.rstrip('"').rstrip("in")) * 25.4
            return float(s)
        except Exception:
            return default_mm

    # sizes & params (unchanged helpers above)
    dpi = int(request.args.get("dpi") or 300)
    cols = int(request.args.get("cols") or 1)
    copies = max(1, int(request.args.get("copies") or 1))
    label_w_mm = _len_mm(request.args.get("label_w"), 40.0)
    label_h_mm = _len_mm(request.args.get("label_h"), 30.0)

    # ✅ Show price by default; pass ?price=0 to hide
    show_price = (request.args.get("price", "1") != "0")

    labels = _labels_for_items(items, dpi, label_w_mm, label_h_mm, show_price)
    labels = [lab for lab in labels for _ in range(copies)]

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,
        label_w=f"{label_w_mm:.2f}mm",
        label_h=f"{label_h_mm:.2f}mm",
        gap="0mm",
        margin="0mm",
        dpi=dpi,
    )
