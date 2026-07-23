import asyncio
import aiosqlite
from app.core.config import settings

async def init_db():
    db_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        
        # Applications table (for API Auth)
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

        # Products table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                images TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Product Variants table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                weight TEXT,
                size TEXT,
                color TEXT,
                attributes TEXT,
                price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Inventory table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                quantity INTEGER NOT NULL DEFAULT 0,
                low_stock_threshold INTEGER NOT NULL DEFAULT 10,
                location TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
            )
        """)

        # Stock Movements table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                quantity INTEGER NOT NULL,
                type TEXT CHECK(type IN ('IN', 'OUT', 'ADJUST')) NOT NULL,
                reference_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
            )
        """)

        # Reservations table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                variant_id INTEGER,
                quantity INTEGER NOT NULL,
                status TEXT CHECK(status IN ('RESERVED', 'CONFIRMED', 'RELEASED')) NOT NULL DEFAULT 'RESERVED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id) REFERENCES product_variants (id) ON DELETE CASCADE
            )
        """)

        # Migration: Add variant_id column if missing from existing tables
        for table in ["inventory", "stock_movements", "reservations"]:
            cursor = await db.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in await cursor.fetchall()]
            if "variant_id" not in columns:
                print(f"Adding variant_id to {table}...")
                await db.execute(f"ALTER TABLE {table} ADD COLUMN variant_id INTEGER")

        # Migration: Add size, color, attributes columns to product_variants if missing
        cursor = await db.execute("PRAGMA table_info(product_variants)")
        variant_columns = [row[1] for row in await cursor.fetchall()]
        for new_col in ["size", "color", "attributes"]:
            if new_col not in variant_columns:
                print(f"Adding {new_col} column to product_variants...")
                await db.execute(f"ALTER TABLE product_variants ADD COLUMN {new_col} TEXT")

        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_sku ON product_variants(sku)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON product_variants(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_variant_id ON inventory(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_variant_id ON stock_movements(variant_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_reference_id ON stock_movements(reference_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_product_id ON reservations(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_variant_id ON reservations(variant_id)")

        await db.commit()
        
        # Seed Website Application (Disabled as per user request to move to dashboard setup)
        # website_api_key = "app_117136c25b8273b68a1eaa79"
        # website_api_secret = "Fj3vUNAPnNSOEioBGRGUx74kcomRFZA4gi7b7d5W"
        
        # from passlib.hash import sha256_crypt
        # hashed_secret = sha256_crypt.hash(website_api_secret)
        
        # cursor = await db.execute("SELECT id FROM applications WHERE api_key = ?", (website_api_key,))
        # if not await cursor.fetchone():
        #     print("Seeding website application to inventory portal...")
        #     await db.execute(
        #         """INSERT INTO applications 
        #            (id, name, api_key, api_secret, is_active, is_live_mode, allowed_domains) 
        #            VALUES (?, ?, ?, ?, ?, ?, ?)""",
        #         ("website-app-id", "TianaLuxora Website", website_api_key, hashed_secret, 1, 0, "*")
        #     )
        #     await db.commit()
        #     print("Website application seeding complete for inventory portal.")

    print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
