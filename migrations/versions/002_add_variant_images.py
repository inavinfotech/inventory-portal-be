"""Add variant images column

Revision ID: 002_add_variant_images
Revises: 001_initial_schema
Create Date: 2026-07-24 12:13:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '002_add_variant_images'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('product_variants')]
    
    if 'images' not in columns:
        op.add_column('product_variants', sa.Column('images', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('product_variants', 'images')
