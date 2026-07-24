from typing import List, Optional, Tuple, Any
from app.db.database import db_helper


class MovementService:
    @staticmethod
    async def get_movements(
        product_id: Optional[str] = None,
        type: Optional[str] = None,
        reference_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[dict], int]:
        async with db_helper.get_db_connection() as db:
            query = "SELECT * FROM stock_movements WHERE 1=1"
            count_query = "SELECT COUNT(*) FROM stock_movements WHERE 1=1"
            params: List[Any] = []

            if product_id:
                query += " AND product_id = ?"
                count_query += " AND product_id = ?"
                params.append(product_id)
            if type:
                query += " AND type = ?"
                count_query += " AND type = ?"
                params.append(type)
            if reference_id:
                query += " AND reference_id = ?"
                count_query += " AND reference_id = ?"
                params.append(reference_id)

            async with db.execute(count_query, params) as cursor:
                total = (await cursor.fetchone())[0]

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                items = [dict(row) for row in rows]

            return items, total


movement_service = MovementService()
