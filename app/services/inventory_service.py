from typing import List, Optional
from app.db.database import db_helper
from app.models.item import ItemCreate, ItemUpdate
import aiosqlite

class InventoryService:
    @staticmethod
    async def get_all_items() -> List[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT * FROM items") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    async def get_item_by_id(item_id: int) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT * FROM items WHERE id = ?", (item_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def create_item(item: ItemCreate) -> dict:
        async with db_helper.get_db_connection() as db:
            cursor = await db.execute(
                "INSERT INTO items (name, description, price, quantity, sku) VALUES (?, ?, ?, ?, ?)",
                (item.name, item.description, item.price, item.quantity, item.sku)
            )
            await db.commit()
            item_id = cursor.lastrowid
            return await InventoryService.get_item_by_id(item_id)

    @staticmethod
    async def update_item(item_id: int, item_data: ItemUpdate) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            # Dynamically build the update query
            fields = item_data.model_dump(exclude_unset=True)
            if not fields:
                return await InventoryService.get_item_by_id(item_id)

            query = "UPDATE items SET " + ", ".join([f"{k} = ?" for k in fields.keys()]) + ", updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            params = list(fields.values()) + [item_id]
            
            await db.execute(query, params)
            await db.commit()
            return await InventoryService.get_item_by_id(item_id)

    @staticmethod
    async def delete_item(item_id: int) -> bool:
        async with db_helper.get_db_connection() as db:
            cursor = await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
            await db.commit()
            return cursor.rowcount > 0

inventory_service = InventoryService()
