"""merge

Revision ID: 3d14ecc1e0e6
Revises: 3f077dbc8586
Create Date: 2025-09-03 22:57:08.434956
"""
from alembic import op
import sqlalchemy as sa

revision = "3d14ecc1e0e6"
down_revision = "3f077dbc8586"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    DO $$
    BEGIN
        -- Example: only add column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = 'items'
              AND column_name  = 'sold_price'
        ) THEN
            ALTER TABLE public.items
            ADD COLUMN sold_price NUMERIC(10,2);
        END IF;

        -- TODO: put your real logic here (updates, merges, etc.)
    END
    $$;
    """)


def downgrade():
    -- Optional: reverse the above if needed
    -- op.execute("ALTER TABLE public.items DROP COLUMN IF EXISTS sold_price;")
    pass
