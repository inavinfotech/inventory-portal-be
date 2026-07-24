import asyncio
import aiosqlite
import os
from app.core.config import settings

async def init_db():
    raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    # Resolve relative paths to absolute, anchored at the backend directory
    if not os.path.isabs(raw_path):
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(backend_dir, raw_path.lstrip("./"))
    else:
        db_path = raw_path
    print(f"Using DB path: {db_path}")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        # ------------------------------------------------------------------ #
        #  Applications table (API Auth)                                       #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                api_secret TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                is_live_mode INTEGER DEFAULT 0,
                allowed_domains TEXT DEFAULT '*',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted_at TIMESTAMP
            )
        """)

        # ------------------------------------------------------------------ #
        #  Products table                                                       #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                description TEXT,
                base_price REAL NOT NULL,
                images TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ------------------------------------------------------------------ #
        #  Variant Types table                                                  #
        #  One row per variant dimension per product (e.g. "Color", "Size")   #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS variant_types (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                name TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                UNIQUE(product_id, name)
            )
        """)

        # ------------------------------------------------------------------ #
        #  Variant Options table                                                #
        #  Specific values for each type (e.g. Color → "Red", "Blue")        #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS variant_options (
                id TEXT PRIMARY KEY,
                variant_type_id TEXT NOT NULL,
                value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (variant_type_id) REFERENCES variant_types (id) ON DELETE CASCADE,
                UNIQUE(variant_type_id, value)
            )
        """)

        # ------------------------------------------------------------------ #
        #  Product Variants table                                               #
        #  Each row = one concrete SKU (no hardcoded size/color/weight)       #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS product_variants (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # ------------------------------------------------------------------ #
        #  Variant Option Assignments table                                     #
        #  M2M: each variant → its selected option values                     #
        #  e.g. variant X has Color="Red" AND Size="M"                        #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS variant_option_assignments (
                variant_id TEXT NOT NULL,
                variant_option_id TEXT NOT NULL,
                PRIMARY KEY (variant_id, variant_option_id),
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_option_id) REFERENCES variant_options (id) ON DELETE CASCADE
            )
        """)

        # ------------------------------------------------------------------ #
        #  Inventory table                                                      #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                variant_id TEXT,
                quantity INTEGER NOT NULL DEFAULT 0,
                low_stock_threshold INTEGER NOT NULL DEFAULT 10,
                location TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE,
                UNIQUE(product_id, variant_id)
            )
        """)

        # ------------------------------------------------------------------ #
        #  Stock Movements table                                                #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                variant_id TEXT,
                quantity INTEGER NOT NULL,
                type TEXT CHECK(type IN ('IN', 'OUT', 'ADJUST')) NOT NULL,
                reference_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
            )
        """)

        # ------------------------------------------------------------------ #
        #  Reservations table                                                   #
        # ------------------------------------------------------------------ #
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                variant_id TEXT,
                quantity INTEGER NOT NULL,
                status TEXT CHECK(status IN ('RESERVED', 'CONFIRMED', 'RELEASED')) NOT NULL DEFAULT 'RESERVED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
            )
        """)

        # ------------------------------------------------------------------ #
        #  Indexes                                                              #
        # ------------------------------------------------------------------ #
        await db.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_sku ON product_variants(sku)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_variant_types_product_id ON variant_types(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_variant_options_type_id ON variant_options(variant_type_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_voa_variant_id ON variant_option_assignments(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_voa_option_id ON variant_option_assignments(variant_option_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_variant_id ON inventory(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_variant_id ON stock_movements(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_reference_id ON stock_movements(reference_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_product_id ON reservations(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_variant_id ON reservations(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_status ON reservations(status)")

        await db.commit()

    print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
