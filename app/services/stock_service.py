from typing import Optional, List
from app.db.database import db_helper
import aiosqlite
from datetime import datetime

class StockService:
    @staticmethod
    async def get_stock(product_id: int) -> int:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    @staticmethod
    async def _ensure_product_exists(db: aiosqlite.Connection, product_id: int):
        async with db.execute("SELECT id FROM products WHERE id = ?", (product_id,)) as cursor:
            if not await cursor.fetchone():
                raise ValueError(f"Product with id {product_id} does not exist")

    @staticmethod
    async def _init_inventory_if_missing(db: aiosqlite.Connection, product_id: int):
        async with db.execute("SELECT id FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
            if not await cursor.fetchone():
                await db.execute("INSERT INTO inventory (product_id, quantity) VALUES (?, 0)", (product_id,))

    @staticmethod
    async def _check_idempotency(db: aiosqlite.Connection, product_id: int, reference_id: Optional[str]) -> Optional[int]:
        if not reference_id:
            return None
        async with db.execute(
            "SELECT id FROM stock_movements WHERE product_id = ? AND reference_id = ?",
            (product_id, reference_id)
        ) as cursor:
            if await cursor.fetchone():
                async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as q_cursor:
                    row = await q_cursor.fetchone()
                    return row[0] if row else 0
        return None

    @staticmethod
    async def add_stock(product_id: int, qty: int, reference_id: Optional[str] = None) -> int:
        if qty <= 0:
            raise ValueError("Quantity must be positive")
            
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id)
                await StockService._init_inventory_if_missing(db, product_id)
                
                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, reference_id)
                if existing_qty is not None:
                    await db.rollback()
                    return existing_qty

                # Update inventory
                await db.execute(
                    "UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                    (qty, product_id)
                )
                
                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'IN', ?)",
                    (product_id, qty, reference_id)
                )
                
                # Get updated qty
                async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                    updated_qty = (await cursor.fetchone())[0]

                await db.commit()
                return updated_qty
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def remove_stock(product_id: int, qty: int, reference_id: Optional[str] = None) -> int:
        if qty <= 0:
            raise ValueError("Quantity must be positive")

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id)
                await StockService._init_inventory_if_missing(db, product_id)

                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, reference_id)
                if existing_qty is not None:
                    await db.rollback()
                    return existing_qty

                # Check current stock
                async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                    current_qty = (await cursor.fetchone())[0]
                    if current_qty < qty:
                        raise ValueError(f"Insufficient stock. Available: {current_qty}, Requested: {qty}")

                # Update inventory
                await db.execute(
                    "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                    (qty, product_id)
                )

                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'OUT', ?)",
                    (product_id, -qty, reference_id)
                )

                # Get updated qty
                async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                    updated_qty = (await cursor.fetchone())[0]

                await db.commit()
                return updated_qty
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def adjust_stock(product_id: int, new_qty: int, reference_id: Optional[str] = None) -> int:
        if new_qty < 0:
            raise ValueError("Stock quantity cannot be negative")

        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await StockService._ensure_product_exists(db, product_id)
                await StockService._init_inventory_if_missing(db, product_id)

                # Idempotency check
                existing_qty = await StockService._check_idempotency(db, product_id, reference_id)
                if existing_qty is not None:
                    # Note: For ADJUST, it's a bit tricky. If we already adjusted to X, and we try again, we return X.
                    # But we'll follow the same pattern: if the movement exists, we assume success.
                    await db.rollback()
                    return existing_qty

                # Update inventory
                await db.execute(
                    "UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                    (new_qty, product_id)
                )

                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'ADJUST', ?)",
                    (product_id, new_qty, reference_id)
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
                    qty = update["quantity"]
                    reference_id = update.get("reference_id") or global_reference_id
                    
                    if qty <= 0:
                        raise ValueError(f"Quantity for product {product_id} must be positive")
                        
                    await StockService._ensure_product_exists(db, product_id)
                    await StockService._init_inventory_if_missing(db, product_id)
                    
                    # Idempotency check
                    existing_qty = await StockService._check_idempotency(db, product_id, reference_id)
                    if existing_qty is not None:
                        results.append({"product_id": product_id, "quantity": existing_qty, "status": "already_processed"})
                        continue

                    # Update inventory
                    await db.execute(
                        "UPDATE inventory SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                        (qty, product_id)
                    )
                    
                    # Log movement
                    await db.execute(
                        "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'IN', ?)",
                        (product_id, qty, reference_id)
                    )
                    
                    # Get updated qty
                    async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                        updated_qty = (await cursor.fetchone())[0]
                        results.append({"product_id": product_id, "quantity": updated_qty, "status": "updated"})

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
                    qty = update["quantity"]
                    reference_id = update.get("reference_id") or global_reference_id
                    
                    if qty <= 0:
                        raise ValueError(f"Quantity for product {product_id} must be positive")

                    await StockService._ensure_product_exists(db, product_id)
                    await StockService._init_inventory_if_missing(db, product_id)

                    # Idempotency check
                    existing_qty = await StockService._check_idempotency(db, product_id, reference_id)
                    if existing_qty is not None:
                        results.append({"product_id": product_id, "quantity": existing_qty, "status": "already_processed"})
                        continue

                    # Check current stock
                    async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                        current_qty = (await cursor.fetchone())[0]
                        if current_qty < qty:
                            raise ValueError(f"Insufficient stock for product {product_id}. Available: {current_qty}, Requested: {qty}")

                    # Update inventory
                    await db.execute(
                        "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                        (qty, product_id)
                    )

                    # Log movement
                    await db.execute(
                        "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'OUT', ?)",
                        (product_id, -qty, reference_id)
                    )

                    # Get updated qty
                    async with db.execute("SELECT quantity FROM inventory WHERE product_id = ?", (product_id,)) as cursor:
                        updated_qty = (await cursor.fetchone())[0]
                        results.append({"product_id": product_id, "quantity": updated_qty, "status": "updated"})

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

            return {
                "total_products": total_products,
                "low_stock_count": low_stock,
                "pending_reservations": pending_reservations,
                "movements_24h": movements_24h
            }

stock_service = StockService()
