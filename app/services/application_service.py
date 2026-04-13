from typing import List, Optional, Tuple
from app.db.database import db_helper
from app.schemas.application import ApplicationCreate
from app.auth.security import get_secret_hash, generate_api_key, generate_api_secret
import aiosqlite
from datetime import datetime, timezone
import uuid

class ApplicationService:
    @staticmethod
    async def get_applications(limit: int = 100, offset: int = 0) -> List[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute(
                "SELECT * FROM applications WHERE deleted_at IS NULL LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    @staticmethod
    async def get_application_by_id(app_id: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute("SELECT * FROM applications WHERE id = ?", (app_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def get_application_by_api_key(api_key: str) -> Optional[dict]:
        async with db_helper.get_db_connection() as db:
            async with db.execute(
                "SELECT * FROM applications WHERE api_key = ? AND is_active = 1 AND deleted_at IS NULL",
                (api_key,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def create_application(app: ApplicationCreate) -> Tuple[dict, str]:
        api_key = app.api_key or generate_api_key()
        plain_secret = app.api_secret or generate_api_secret()
        hashed_secret = get_secret_hash(plain_secret)
        app_id = str(uuid.uuid4())
        
        async with db_helper.get_db_connection() as db:
            await db.execute(
                """INSERT INTO applications 
                   (id, name, api_key, api_secret, is_active, is_live_mode, allowed_domains) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (app_id, app.name, api_key, hashed_secret, int(app.is_active), int(app.is_live_mode), app.allowed_domains)
            )
            await db.commit()
            
        db_app = await ApplicationService.get_application_by_id(app_id)
        return db_app, plain_secret

    @staticmethod
    async def delete_application(app_id: str) -> bool:
        async with db_helper.get_db_connection() as db:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "UPDATE applications SET deleted_at = ?, is_active = 0 WHERE id = ?",
                (now, app_id)
            )
            await db.commit()
            return True

application_service = ApplicationService()
