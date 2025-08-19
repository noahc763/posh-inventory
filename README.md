# Posh Inventory (Flask)

### Features
- User accounts (Flask-Login)
- Items: barcode, category, cost, list/sold price, profit after fees
- Break-even listing price (0% profit) per item using current Poshmark fee rules
- Scan via USB scanner or browser camera (Quagga2)
- Local photo uploads

### Running locally
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app run --debug
```

### Notes on fees & break-even

- Fees (US): $2.95 under $15; 20% for $15+.
- Break-even price solves **payout_after_fees(price) = cost**.
  - If price < $15: price = cost + 2.95
  - Else: price = cost / 0.8
  - If the computed price crosses the $15 boundary, switch formula accordingly. See `posh.py`.

### Switch to PostgreSQL later

Set `DATABASE_URL=postgresql+psycopg://user:pass@host/db` and install `psycopg`.

### Security

This is a minimal starter. For production add HTTPS, CSRF protection, image validation, and proper auth flows.
