from typing import Optional, List, Tuple
from app.db.database import db_helper
from app.services.stock_service import stock_service
import aiosqlite
import uuid


class ReservationService:

    @staticmethod
    async def get_available_stock(product_id: str, variant_id: Optional[str] = None) -> int:
        physical_stock = await stock_service.get_stock(product_id, variant_id)
        async with db_helper.get_db_connection() as db:
            query = "SELECT SUM(quantity) FROM reservations WHERE product_id = ? AND status = 'RESERVED'"
            params: list = [product_id]
            if variant_id:
                query += " AND variant_id = ?"
                params.append(variant_id)
            else:
                query += " AND variant_id IS NULL"

            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                reserved_stock = row[0] if row[0] else 0
                return physical_stock - reserved_stock

    @staticmethod
    async def create_reservation(product_id: str, qty: int, variant_id: Optional[str] = None) -> dict:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                available = await ReservationService.get_available_stock(product_id, variant_id)
                if available < qty:
                    variant_info = f" for variant {variant_id}" if variant_id else ""
                    raise ValueError(
                        f"Insufficient available stock{variant_info}. Available: {available}, Requested: {qty}"
                    )

                res_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO reservations (id, product_id, variant_id, quantity, status) VALUES (?, ?, ?, ?, 'RESERVED')",
                    (res_id, product_id, variant_id, qty)
                )
                await db.commit()

                async with db.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)) as cursor:
                    return dict(await cursor.fetchone())
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def confirm_reservation(reservation_id: str) -> dict:
        async with db_helper.get_db_connection() as db:
            await db.execute("BEGIN IMMEDIATE")
            try:
                async with db.execute("SELECT * FROM reservations WHERE id = ?", (reservation_id,)) as cursor:
                    res = await cursor.fetchone()
                    if not res:
                        raise ValueError("Reservation not found")
                    res = dict(res)
                    if res["status"] != "RESERVED":
                        raise ValueError(f"Cannot confirm reservation in status: {res['status']}")

                await db.execute(
                    "UPDATE reservations SET status = 'CONFIRMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reservation_id,)
                )

                # Reduce physical stock
                query = "UPDATE inventory SET quantity = quantity - ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?"
                params: list = [res["quantity"], res["product_id"]]
                if res["variant_id"]:
                    query += " AND variant_id = ?"
                    params.append(res["variant_id"])
                else:
                    query += " AND variant_id IS NULL"
                await db.execute(query, params)

                # Log movement
                await db.execute(
                    "INSERT INTO stock_movements (id, product_id, variant_id, quantity, type, reference_id) VALUES (?, ?, ?, ?, 'OUT', ?)",
                    (str(uuid.uuid4()), res["product_id"], res["variant_id"], -res["quantity"], f"RESERVATION-CONFIRM-{reservation_id}")
                )

                await db.commit()
                res["status"] = "CONFIRMED"
                return res
            except Exception as e:
                await db.rollback()
                raise e

    @staticmethod
    async def release_reservation(reservation_id: str) -> dict:
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
                async with db.execute(
                    "UPDATE reservations SET status = 'RELEASED', updated_at = CURRENT_TIMESTAMP "
                    "WHERE status = 'RESERVED' AND datetime(created_at, '+' || ? || ' minutes') < datetime('now')",
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
            async with db.execute("SELECT COUNT(*) FROM reservations") as cursor:
                total = (await cursor.fetchone())[0]

            async with db.execute(
                "SELECT * FROM reservations ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                items = [dict(row) for row in rows]

            return items, total


reservation_service = ReservationService()
