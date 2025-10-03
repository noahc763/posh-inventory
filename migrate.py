# migrate.py
from flask_migrate import Migrate
from models import db
from app import create_app   # uses your existing factory
from alembic import op
import sqlalchemy as sa

app = create_app()
migrate = Migrate(app, db)

# Optional: flask shell convenience
@app.shell_context_processor
def make_shell_context():
    return {"db": db}

def upgrade():
   op.add_column('items', sa.Column('list_price', sa.Numeric(10, 2), nullable=True))

def downgrade():
    op.alter_column('items', 'listing_price', new_column_name='listing_price_price')
    op.drop_column('item', 'list_price')