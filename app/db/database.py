import aiosqlite
from contextlib import asynccontextmanager
from app.core.config import settings

class Database:
    def __init__(self, db_url: str):
        self.db_url = db_url.replace("sqlite+aiosqlite:///", "")

    @asynccontextmanager
    async def get_db_connection(self):
        db = await aiosqlite.connect(self.db_url)
        await db.execute("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

db_helper = Database(settings.DATABASE_URL)
