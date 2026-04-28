from typing import Optional, List
from app.db.database import db_helper
import aiosqlite
from datetime import datetime

class StockService:
    @staticmethod
    async def get_stock(product_id: int, variant_id: Optional[int] = None) -> int:
        async with db_helper.get_db_connection() as db:
            if variant_id:
                async with db.execute("SELECT quantity FROM inventory WHERE variant_id = ?", (variant_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
            else:
                async with db.execute("SELECT SUM(quantity) FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row and row[0] is not None else 0

    @staticmethod
    async def _ensure_product_exists(db: aiosqlite.Connection, product_id: int, variant_id: Optional[int] = None):
        async with db.execute("SELECT id FROM products WHERE id = ?", (product_id,)) as cursor:
            if not await cursor.fetchone():
                raise ValueError(f"Product with id {product_id} does not exist")
        
        if variant_id:
            async with db.execute("SELECT id FROM product_variants WHERE id = ? AND product_id = ?", (variant_id, product_id)) as cursor:
                if not await cursor.fetchone():
                    raise ValueError(f"Variant with id {variant_id} does not exist for product {product_id}")

    @staticmethod
    async def _init_inventory_if_missing(db: aiosqlite.Connection, product_id: int, variant_id: Optional[int] = None):
        if variant_id:
            async with db.execute("SELECT id FROM inventory WHERE variant_id = ?", (variant_id,)) as cursor:
                if not await cursor.fetchone():
                    await db.execute("INSERT INTO inventory (product_id, variant_id, quantity) VALUES (?, ?, 0)", (product_id, variant_id))
        else:
            async with db.execute("SELECT id FROM inventory WHERE product_id = ? AND variant_id IS NULL", (product_id,)) as cursor:
                if not await cursor.fetchone():
                    await db.execute("INSERT INTO inventory (product_id, variant_id, quantity) VALUES (?, NULL, 0)", (product_id,))

    @staticmethod
    async def _check_idempotency(db: aiosqlite.Connection, product_id: int, variant_id: Optional[int], reference_id: Optional[str]) -> Optional[int]:
        if not reference_id:
            return None
        
        query = "SELECT id FROM stock_movements WHERE product_id = ? AND reference_id = ?"
        params = [product_id, reference_id]
        if variant_id:
            query += " AND variant_id = ?"
            params.append(variant_id)
        else:
            query += " AND variant_id IS NULL"

        async with db.execute(query, params) as cursor:
            if await cursor.fetchone():
                return await StockService.get_stock(product_id, variant_id)
        return None

    @staticmethod
    async def add_stock(product_id: int, qty: int, reference_id: Optional[str] = None, variant_id: Optional[int] = None) -> int:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
            
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id, variant_id)
                await StockService._init_inventory_if_missing(db, product_id, variant_id)
                
                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, variant_id, reference_id)
                if existing_qty is not None:
                    await db.rollback()
                    return existing_qty

                # Update inventory
                query = "UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                params = [qty, product_id]
                if variant_id:
                    query += " AND variant_id = ?"
                    params.append(variant_id)
                else:
                    query += " AND variant_id IS NULL"
                
                await db.execute(query, params)
                
                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, 'IN', ?)",
                    (product_id, variant_id, qty, reference_id)
                )
                
                await db.commit()
                return await StockService.get_stock(product_id, variant_id)
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def remove_stock(product_id: int, qty: int, reference_id: Optional[str] = None, variant_id: Optional[int] = None) -> int:
        if qty <= 0:
            raise ValueError("Quantity must be positive")

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id, variant_id)
                await StockService._init_inventory_if_missing(db, product_id, variant_id)

                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, variant_id, reference_id)
                if existing_qty is not None:
                    await db.rollback()
                    return existing_qty

                # Check current stock
                current_qty = await StockService.get_stock(product_id, variant_id)
                if current_qty < qty:
                    raise ValueError(f"Insufficient stock. Available: {current_qty}, Requested: {qty}")

                # Update inventory
                query = "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                params = [qty, product_id]
                if variant_id:
                    query += " AND variant_id = ?"
                    params.append(variant_id)
                else:
                    query += " AND variant_id IS NULL"
                
                await db.execute(query, params)

                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, 'OUT', ?)",
                    (product_id, variant_id, -qty, reference_id)
                )

                await db.commit()
                return await StockService.get_stock(product_id, variant_id)
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def adjust_stock(product_id: int, new_qty: int, reference_id: Optional[str] = None, variant_id: Optional[int] = None) -> int:
        if new_qty < 0:
            raise ValueError("Stock quantity cannot be negative")

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id, variant_id)
                await StockService._init_inventory_if_missing(db, product_id, variant_id)

                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, variant_id, reference_id)
                if existing_qty is not None:
                    await db.rollback()
                    return existing_qty

                # Update inventory
                query = "UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                params = [new_qty, product_id]
                if variant_id:
                    query += " AND variant_id = ?"
                    params.append(variant_id)
                else:
                    query += " AND variant_id IS NULL"
                    
                await db.execute(query, params)

                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, 'ADJUST', ?)",
                    (product_id, variant_id, new_qty, reference_id)
                )

                await db.commit()
                return new_qty
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def bulk_add_stock(updates: List[dict], global_reference_id: Optional[str] = None) -> List[dict]:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                results = []
                for update in updates:
                    product_id = update["product_id"]
                    variant_id = update.get("variant_id")
                    qty = update["quantity"]
                    reference_id = update.get("reference_id") or global_reference_id
                    
                    if qty <= 0:
                        raise ValueError(f"Quantity for product {product_id} must be positive")
                        
                    await StockService._ensure_product_exists(db, product_id, variant_id)
                    await StockService._init_inventory_if_missing(db, product_id, variant_id)
                    
                    # Idempotency check
                    existing_qty = await StockService._check_idempotency(db, product_id, variant_id, reference_id)
                    if existing_qty is not None:
                        results.append({"product_id": product_id, "variant_id": variant_id, "quantity": existing_qty, "status": "already_processed"})
                        continue

                    # Update inventory
                    query = "UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                    params = [qty, product_id]
                    if variant_id:
                        query += " AND variant_id = ?"
                        params.append(variant_id)
                    else:
                        query += " AND variant_id IS NULL"
                    await db.execute(query, params)
                    
                    # Log movement
                    await db.execute(
                        "INSERT INTO stock_movements (product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, 'IN', ?)",
                        (product_id, variant_id, qty, reference_id)
                    )
                    
                    updated_qty = await StockService.get_stock(product_id, variant_id)
                    results.append({"product_id": product_id, "variant_id": variant_id, "quantity": updated_qty, "status": "updated"})

                await db.commit()
                return results
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def bulk_remove_stock(updates: List[dict], global_reference_id: Optional[str] = None) -> List[dict]:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                results = []
                for update in updates:
                    product_id = update["product_id"]
                    variant_id = update.get("variant_id")
                    qty = update["quantity"]
                    reference_id = update.get("reference_id") or global_reference_id
                    
                    if qty <= 0:
                        raise ValueError(f"Quantity for product {product_id} must be positive")

                    await StockService._ensure_product_exists(db, product_id, variant_id)
                    await StockService._init_inventory_if_missing(db, product_id, variant_id)

                    # Idempotency check
                    existing_qty = await StockService._check_idempotency(db, product_id, variant_id, reference_id)
                    if existing_qty is not None:
                        results.append({"product_id": product_id, "variant_id": variant_id, "quantity": existing_qty, "status": "already_processed"})
                        continue

                    # Check current stock
                    current_qty = await StockService.get_stock(product_id, variant_id)
                    if current_qty < qty:
                        raise ValueError(f"Insufficient stock for product {product_id}. Available: {current_qty}, Requested: {qty}")

                    # Update inventory
                    query = "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                    params = [qty, product_id]
                    if variant_id:
                        query += " AND variant_id = ?"
                        params.append(variant_id)
                    else:
                        query += " AND variant_id IS NULL"
                    await db.execute(query, params)

                    # Log movement
                    await db.execute(
                        "INSERT INTO stock_movements (product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, 'OUT', ?)",
                        (product_id, variant_id, -qty, reference_id)
                    )

                    updated_qty = await StockService.get_stock(product_id, variant_id)
                    results.append({"product_id": product_id, "variant_id": variant_id, "quantity": updated_qty, "status": "updated"})

                await db.commit()
                return results
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def get_dashboard_stats() -> dict:
        async with db_helper.get_db_connection() as db:
            # Total Products
            async with db.execute("SELECT COUNT(*) FROM products") as cursor:
                total_products = (await cursor.fetchone())[0]

            # Low Stock Count
            async with db.execute("SELECT COUNT(*) FROM inventory WHERE quantity < low_stock_threshold") as cursor:
                low_stock = (await cursor.fetchone())[0]

            # Pending Reservations
            async with db.execute("SELECT COUNT(*) FROM reservations WHERE status = 'RESERVED'") as cursor:
                pending_reservations = (await cursor.fetchone())[0]

            # 24h Movements
            async with db.execute(
                "SELECT COUNT(*) FROM stock_movements WHERE datetime(created_at) > datetime('now', '-1 day')"
            ) as cursor:
                movements_24h = (await cursor.fetchone())[0]

            # Stock Distribution (Top 5 products by total stock)
            async with db.execute("""
                SELECT p.name, SUM(i.quantity) as total_qty
                FROM inventory i
                JOIN products p ON i.product_id = p.id
                GROUP BY p.id
                ORDER BY total_qty DESC
                LIMIT 5
            """) as cursor:
                rows = await cursor.fetchall()
                stock_distribution = [{"name": r[0], "quantity": r[1]} for r in rows]

            return {
                "total_products": total_products,
                "low_stock_count": low_stock,
                "pending_reservations": pending_reservations,
                "movements_24h": movements_24h,
                "stock_distribution": stock_distribution
            }

stock_service = StockService()
