from typing import List, Optional, Tuple
from app.db.database import db_helper
from app.models.product import ProductCreate, ProductUpdate
import aiosqlite

class ProductService:
    @staticmethod
    async def get_products(limit: int = 10, offset: int = 0) -> Tuple[List[dict], int]:
        async with db_helper.get_db_connection() as db:
            # Get total count
            async with db.execute("SELECT COUNT(*) FROM products") as cursor:
                total = (await cursor.fetchone())[0]

            # Get paginated items
            async with db.execute(
                "SELECT * FROM products ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                items = [dict(row) for row in rows]
                
            return items, total

    @staticmethod
    async def get_product_by_id(product_id: int) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def get_product_by_sku(sku: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT * FROM products WHERE sku = ?", (sku,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def create_product(product: ProductCreate) -> dict:
        # SKU Idempotency check
        existing = await ProductService.get_product_by_sku(product.sku)
        if existing:
            return existing

        async with db_helper.get_db_connection() as db:
            cursor = await db.execute(
                "INSERT INTO products (name, sku, description, price) VALUES (?, ?, ?, ?)",
                (product.name, product.sku, product.description, product.price)
            )
            await db.commit()
            product_id = cursor.lastrowid
            return await ProductService.get_product_by_id(product_id)

product_service = ProductService()
