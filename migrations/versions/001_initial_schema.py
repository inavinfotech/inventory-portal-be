"""Initial inventory schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-07-24 11:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Applications table
    op.create_table(
        'applications',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('api_key', sa.String(), nullable=False, unique=True),
        sa.Column('api_secret', sa.String(), nullable=False),
        sa.Column('is_active', sa.Integer(), server_default='1'),
        sa.Column('is_live_mode', sa.Integer(), server_default='0'),
        sa.Column('allowed_domains', sa.String(), server_default='*'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    # Products table
    op.create_table(
        'products',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('sku', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_price', sa.Float(), nullable=False),
        sa.Column('images', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_products_sku', 'products', ['sku'], unique=False)

    # Variant Types table
    op.create_table(
        'variant_types',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.String(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('product_id', 'name', name='uq_variant_types_product_name'),
    )
    op.create_index('idx_variant_types_product_id', 'variant_types', ['product_id'], unique=False)

    # Variant Options table
    op.create_table(
        'variant_options',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('variant_type_id', sa.String(), sa.ForeignKey('variant_types.id', ondelete='CASCADE'), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('variant_type_id', 'value', name='uq_variant_options_type_value'),
    )
    op.create_index('idx_variant_options_type_id', 'variant_options', ['variant_type_id'], unique=False)

    # Product Variants table
    op.create_table(
        'product_variants',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.String(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(), nullable=False, unique=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_product_variants_sku', 'product_variants', ['sku'], unique=False)
    op.create_index('idx_product_variants_product_id', 'product_variants', ['product_id'], unique=False)

    # Variant Option Assignments table
    op.create_table(
        'variant_option_assignments',
        sa.Column('variant_id', sa.String(), sa.ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('variant_option_id', sa.String(), sa.ForeignKey('variant_options.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('variant_id', 'variant_option_id'),
    )
    op.create_index('idx_voa_variant_id', 'variant_option_assignments', ['variant_id'], unique=False)
    op.create_index('idx_voa_option_id', 'variant_option_assignments', ['variant_option_id'], unique=False)

    # Inventory table
    op.create_table(
        'inventory',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.String(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('variant_id', sa.String(), sa.ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('quantity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('low_stock_threshold', sa.Integer(), server_default='10', nullable=False),
        sa.Column('location', sa.String(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('product_id', 'variant_id', name='uq_inventory_product_variant'),
    )
    op.create_index('idx_inventory_product_id', 'inventory', ['product_id'], unique=False)
    op.create_index('idx_inventory_variant_id', 'inventory', ['variant_id'], unique=False)

    # Stock Movements table
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.String(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('variant_id', sa.String(), sa.ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('reference_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_stock_movements_product_id', 'stock_movements', ['product_id'], unique=False)

    # Reservations table
    op.create_table(
        'reservations',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('product_id', sa.String(), sa.ForeignKey('products.id', ondelete='CASCADE'), nullable=False),
        sa.Column('variant_id', sa.String(), sa.ForeignKey('product_variants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), server_default='RESERVED', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('reservations')
    op.drop_table('stock_movements')
    op.drop_table('inventory')
    op.drop_table('variant_option_assignments')
    op.drop_table('product_variants')
    op.drop_table('variant_options')
    op.drop_table('variant_types')
    op.drop_table('products')
    op.drop_table('applications')
