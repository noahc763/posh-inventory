"""merge

Revision ID: 3d14ecc1e0e6
Revises: 3f077dbc8586
Create Date: 2025-09-03 22:57:08.434956

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_listing_into_sold'
down_revision = '3d14ecc1e0e6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            
        ))


def downgrade():
    pass
