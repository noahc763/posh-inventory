# migrate.py
from flask_migrate import Migrate
from models import db
from app import create_app   # uses your existing factory
from alembic import op

app = create_app()
migrate = Migrate(app, db)

# Optional: flask shell convenience
@app.shell_context_processor
def make_shell_context():
    return {"db": db}

def upgrade():
    op.alter_column('items', 'listing_price_price', new_column_name='listing_price')

def downgrade():
    op.alter_column('items', 'listing_price', new_column_name='listing_price_price')