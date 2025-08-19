from decimal import Decimal, ROUND_HALF_UP

# Poshmark (US) fees as of Oct 2024+: $2.95 under $15; 20% at $15+.
FLAT_FEE = Decimal("2.95")
PCT = Decimal("0.20")
THRESHOLD = Decimal("15.00")

TWO_PLACES = Decimal("0.01")

def posh_fee(sale_price: Decimal) -> Decimal:
    if sale_price < THRESHOLD:
        return FLAT_FEE
    return (sale_price * PCT).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

def payout_after_fees(sale_price: Decimal) -> Decimal:
    return (sale_price - posh_fee(sale_price)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

def break_even_listing_price(cost: Decimal) -> Decimal:
    """Minimum listing price such that payout_after_fees(price) == cost (0% profit).
    Handles the fee regime boundary at $15.
    """
    cost = Decimal(cost).quantize(TWO_PLACES)

    # Try flat-fee regime first
    flat_price = (cost + FLAT_FEE).quantize(TWO_PLACES)
    if flat_price < THRESHOLD:
        return flat_price

    # Otherwise percent regime
    pct_price = (cost / (Decimal("1.00") - PCT)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    if pct_price < THRESHOLD:
        # bump to threshold to satisfy regime
        pct_price = THRESHOLD
    return pct_price

def profit_after_fees(sale_price: Decimal, cost: Decimal) -> Decimal:
    return (payout_after_fees(Decimal(sale_price)) - Decimal(cost)).quantize(TWO_PLACES)
