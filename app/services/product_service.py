from typing import List, Optional, Tuple
from app.db.database import db_helper
from app.models.product import ProductCreate, ProductUpdate
import aiosqlite
import json

class ProductService:
    @staticmethod
    def _process_product_row(row: dict) -> dict:
        data = dict(row)
        if data.get("images"):
            try:
                data["images"] = json.loads(data["images"])
            except:
                data["images"] = []
        else:
            data["images"] = []
        return data

    @staticmethod
    async def _get_variants_for_product(db: aiosqlite.Connection, product_id: int) -> List[dict]:
        async with db.execute("""
            SELECT v.*, 
                   COALESCE(i.quantity, 0) as stock,
                   COALESCE((SELECT SUM(r.quantity) FROM reservations r WHERE r.variant_id = v.id AND r.status = 'RESERVED'), 0) as reserved
            FROM product_variants v
            LEFT JOIN inventory i ON v.id = i.variant_id
            WHERE v.product_id = ?
        """, (product_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    async def get_products(limit: int = 10, offset: int = 0) -> Tuple[List[dict], int]:
        async with db_helper.get_db_connection() as db:
            # Get total count
            async with db.execute("SELECT COUNT(*) FROM products") as cursor:
                total = (await cursor.fetchone())[0]

            # Get paginated items with total stock and total reserved
            async with db.execute("""
                SELECT p.*, 
                       (SELECT SUM(quantity) FROM inventory WHERE product_id = p.id) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p
                ORDER BY p.created_at DESC LIMIT ? OFFSET ?
            """, (limit, offset)) as cursor:
                rows = await cursor.fetchall()
                items = []
                for row in rows:
                    product = ProductService._process_product_row(row)
                    product["stock"] = row["stock"] if row["stock"] is not None else 0
                    product["reserved"] = row["reserved"] if row["reserved"] is not None else 0
                    product["variants"] = await ProductService._get_variants_for_product(db, product["id"])
                    items.append(product)
                
            return items, total

    @staticmethod
    async def get_product_by_id(product_id: int) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("""
                SELECT p.*, 
                       (SELECT SUM(quantity) FROM inventory WHERE product_id = p.id) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p WHERE p.id = ?
            """, (product_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                product = ProductService._process_product_row(row)
                product["stock"] = row["stock"] if row["stock"] is not None else 0
                product["reserved"] = row["reserved"] if row["reserved"] is not None else 0
                product["variants"] = await ProductService._get_variants_for_product(db, product_id)
                return product

    @staticmethod
    async def get_product_by_sku(sku: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("""
                SELECT p.*, 
                       (SELECT SUM(quantity) FROM inventory WHERE product_id = p.id) as stock,
                       COALESCE((SELECT SUM(quantity) FROM reservations WHERE product_id = p.id AND status = 'RESERVED'), 0) as reserved
                FROM products p WHERE p.sku = ?
            """, (sku,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                product = ProductService._process_product_row(row)
                product["stock"] = row["stock"] if row["stock"] is not None else 0
                product["reserved"] = row["reserved"] if row["reserved"] is not None else 0
                product["variants"] = await ProductService._get_variants_for_product(db, product["id"])
                return product

    @staticmethod
    async def create_product(product: ProductCreate) -> dict:
        # SKU Idempotency check
        existing = await ProductService.get_product_by_sku(product.sku)
        if existing:
            return existing

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                images_json = json.dumps(product.images) if product.images else None
                cursor = await db.execute(
                    "INSERT INTO products (name, sku, description, price, images) VALUES (?, ?, ?, ?, ?)",
                    (product.name, product.sku, product.description, product.price, images_json)
                )
                product_id = cursor.lastrowid

                # Create Variants if any
                if product.variants:
                    for variant in product.variants:
                        await db.execute(
                            "INSERT INTO product_variants (product_id, sku, weight, price) VALUES (?, ?, ?, ?)",
                            (product_id, variant.sku, variant.weight, variant.price)
                        )
                
                await db.commit()
                return await ProductService.get_product_by_id(product_id)
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def update_product(product_id: int, product_update: ProductUpdate) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # Build dynamic update query for products table
                update_data = product_update.model_dump(exclude_unset=True)
                variants_to_update = update_data.pop("variants", None)

                if update_data:
                    if "images" in update_data:
                        update_data["images"] = json.dumps(update_data["images"])

                    fields = ", ".join([f"{k} = ?" for k in update_data.keys()])
                    values = list(update_data.values())
                    values.append(product_id)

                    query = f"UPDATE products SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                    await db.execute(query, values)

                # Update variants (Upsert logic)
                if variants_to_update is not None:
                    # Get current variant IDs for this product
                    async with db.execute("SELECT id FROM product_variants WHERE product_id = ?", (product_id,)) as cursor:
                        current_variant_ids = {row[0] for row in await cursor.fetchall()}
                    
                    new_variant_ids = {v["id"] for v in variants_to_update if v.get("id")}
                    
                    # 1. Delete variants that are no longer present
                    ids_to_delete = current_variant_ids - new_variant_ids
                    if ids_to_delete:
                        placeholders = ", ".join(["?"] * len(ids_to_delete))
                        await db.execute(f"DELETE FROM product_variants WHERE id IN ({placeholders})", list(ids_to_delete))
                    
                    # 2. Update existing or Insert new variants
                    for variant in variants_to_update:
                        if variant.get("id"):
                            # Update existing
                            await db.execute(
                                "UPDATE product_variants SET sku = ?, weight = ?, price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (variant["sku"], variant["weight"], variant["price"], variant["id"])
                            )
                        else:
                            # Insert new
                            await db.execute(
                                "INSERT INTO product_variants (product_id, sku, weight, price) VALUES (?, ?, ?, ?)",
                                (product_id, variant["sku"], variant["weight"], variant["price"])
                            )

                await db.commit()
                return await ProductService.get_product_by_id(product_id)
            except Exception as e:
                await db.rollback()
                raise e


product_service = ProductService()
