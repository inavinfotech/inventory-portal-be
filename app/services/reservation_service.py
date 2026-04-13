from typing import Optional, List, Tuple
from app.db.database import db_helper
from app.services.stock_service import stock_service
import aiosqlite

class ReservationService:
    @staticmethod
    async def get_available_stock(product_id: int) -> int:
        physical_stock = await stock_service.get_stock(product_id)
        async with db_helper.get_db_connection() as db:
            async with db.execute(
                "SELECT SUM(quantity) FROM reservations WHERE product_id = ? AND status = 'RESERVED'",
                (product_id,)
            ) as cursor:
                row = await cursor.fetchone()
                reserved_stock = row[0] if row[0] else 0
                return physical_stock - reserved_stock

    @staticmethod
    async def create_reservation(product_id: int, qty: int) -> dict:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 1. Validate App & Product existence via FKs (SQLite will check on insert, but we check available stock first)
                available = await ReservationService.get_available_stock(product_id)
                if available < qty:
                    raise ValueError(f"Insufficient available stock. Available: {available}, Requested: {qty}")

                # 2. Insert reservation
                cursor = await db.execute(
                    "INSERT INTO reservations (product_id, quantity, status) VALUES (?, ?, 'RESERVED')",
                    (product_id, qty)
                )
                res_id = cursor.lastrowid
                await db.commit()
                
                # return the newly created reservation
                async with db.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)) as cursor:
                    return dict(await cursor.fetchone())
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def confirm_reservation(reservation_id: int) -> dict:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # 1. Get reservation details
                async with db.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)) as cursor:
                    res = await cursor.fetchone()
                    if not res:
                        raise ValueError("Reservation not found")
                    res = dict(res)
                    if res["status"] != "RESERVED":
                        raise ValueError(f"Cannot confirm reservation in status: {res['status']}")

                # 2. Confirm: status -> CONFIRMED, physical stock -> reduce
                await db.execute(
                    "UPDATE reservations SET status = 'CONFIRMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reservation_id,)
                )
                
                # Physical stock reduction using the same internal logic as remove_stock but without double-checking available (since it was reserved)
                # However, to maintain integrity and audit log, we'll call stock_service or handle it here.
                # Calling stock_service.remove_stock would create a NEW transaction, which we can't do within this one.
                # So we manually perform the update and log movement.
                
                await db.execute(
                    "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?",
                    (res["quantity"], res["product_id"])
                )
                
                await db.execute(
                    "INSERT INTO stock_movements (product_id, quantity, type, reference_id) VALUES (?, ?, 'OUT', ?)",
                    (res["product_id"], -res["quantity"], f"RESERVATION-CONFIRM-{reservation_id}")
                )

                await db.commit()
                res["status"] = "CONFIRMED"
                return res
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def release_reservation(reservation_id: int) -> dict:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)) as cursor:
                    res = await cursor.fetchone()
                    if not res:
                        raise ValueError("Reservation not found")
                    res = dict(res)
                    if res["status"] != "RESERVED":
                        raise ValueError(f"Cannot release reservation in status: {res['status']}")

                await db.execute(
                    "UPDATE reservations SET status = 'RELEASED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reservation_id,)
                )
                await db.commit()
                res["status"] = "RELEASED"
                return res
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def cleanup_stale_reservations(minutes: int = 30) -> int:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # Find reserved records older than threshold
                async with db.execute(
                    "UPDATE reservations SET status = 'RELEASED', updated_at = CURRENT_TIMESTAMP WHERE status = 'RESERVED' AND datetime(created_at, '+' || ? || ' minutes') < datetime('now')",
                    (minutes,)
                ) as cursor:
                    count = cursor.rowcount
                    await db.commit()
                    return count
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def get_reservations(limit: int = 10, offset: int = 0) -> Tuple[List[dict], int]:
        async with db_helper.get_db_connection() as db:
            # Get total count
            async with db.execute("SELECT COUNT(*) FROM reservations") as cursor:
                total = (await cursor.fetchone())[0]

            # Get paginated items
            async with db.execute(
                "SELECT * FROM reservations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                items = [dict(row) for row in rows]
                
            return items, total

reservation_service = ReservationService()
