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

        # Inventory table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                low_stock_threshold INTEGER NOT NULL DEFAULT 10,
                location TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Stock Movements table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                type TEXT CHECK(type IN ('IN', 'OUT', 'ADJUST')) NOT NULL,
                reference_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Reservations table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT CHECK(status IN ('RESERVED', 'CONFIRMED', 'RELEASED')) NOT NULL DEFAULT 'RESERVED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
            )
        """)

        # Indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_reference_id ON stock_movements(reference_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_reservations_product_id ON reservations(product_id)")

        await db.commit()
    print("Database initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
