# labels.py
from typing import List
from flask import Blueprint, request, render_template, abort
from flask_login import login_required, current_user
from decimal import Decimal, ROUND_CEILING

from models import Item

labels_bp = Blueprint("labels", __name__)

# ---------------- helpers ----------------

def _len_mm(s: str | None, default_mm: float) -> float:
    """
    Parse a CSS length like '40mm' or '30mm' -> float millimeters.
    Falls back to default_mm if missing/invalid.
    """
    if not s:
        return default_mm
    s = s.strip().lower()
    if s.endswith("mm"):
        try:
            return float(s[:-2])
        except Exception:
            return default_mm
    try:
        # allow passing raw number meaning mm
        return float(s)
    except Exception:
        return default_mm


def _round_up_cents(value: Decimal) -> Decimal:
    """Round UP to 2 decimals."""
    cents = (value * Decimal("100")).to_integral_value(rounding=ROUND_CEILING)
    return cents / Decimal("100")


def _breakeven(purchase_price: Decimal | None) -> Decimal | None:
    """
    Poshmark fee:
      - $2.95 if list < $15
      - 20% if list >= $15
    Find minimum list L so that L - fee(L) - purchase >= 0.
    """
    if purchase_price is None or purchase_price <= 0:
        return None

    flat = purchase_price + Decimal("2.95")
    if flat < Decimal("15.00"):
        return _round_up_cents(flat)

    # 20% regime
    percent = purchase_price / Decimal("0.8")
    if percent < Decimal("15.00"):
        percent = Decimal("15.00")
    return _round_up_cents(percent)


def _labels_for_items_text(items: List[Item]) -> List[dict]:
    """
    Build a list of dicts for text-only labels:
      - num: the prominent number to print (barcode if present, else item id)
      - price: break-even price like '$12.34' (or '' if not computable)
    """
    out: List[dict] = []
    for it in items:
        # Choose the number to show: prefer barcode, fallback to item id.
        num = (it.barcode or "").strip() or str(it.id)

        be = _breakeven(it.purchase_price) if it.purchase_price is not None else None
        price = f"${be:.2f}" if be is not None else ""

        out.append({"num": num, "price": price})
    return out

# ---------------- route ----------------

@labels_bp.route("/labels/print")
@login_required
def labels_print():
    """
    Text-only labels for 40×30 mm (customizable).
    Query params:
      ids       = comma-separated item IDs (required)
      cols      = columns across (default 1)
      copies    = copies per item (default 1)
      label_w   = label width, e.g., '40mm' (default 40mm)
      label_h   = label height, e.g., '30mm' (default 30mm)
      margin    = page margin around sheet/grid (default 0mm)
      gap       = gap between labels (default 0mm)
    """
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

    # layout params
    try:
        cols = int(request.args.get("cols") or 1)
    except Exception:
        cols = 1
    try:
        copies = max(1, int(request.args.get("copies") or 1))
    except Exception:
        copies = 1

    label_w_mm = _len_mm(request.args.get("label_w"), 40.0)
    label_h_mm = _len_mm(request.args.get("label_h"), 30.0)
    margin = request.args.get("margin") or "0mm"
    gap = request.args.get("gap") or "0mm"

    labels = _labels_for_items_text(items)
    labels = [lab for lab in labels for _ in range(copies)]  # replicate copies

    return render_template(
        "labels_print.html",
        labels=labels,
        cols=cols,
        label_w=f"{label_w_mm:.2f}mm",
        label_h=f"{label_h_mm:.2f}mm",
        gap=gap,
        margin=margin,
    )
