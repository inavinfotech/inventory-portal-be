import aiosqlite
import os
from contextlib import asynccontextmanager
from app.core.config import settings


def _resolve_db_path(url: str) -> str:
    """Resolve DATABASE_URL to an absolute filesystem path."""
    raw = url.replace("sqlite+aiosqlite:///", "")
    if os.path.isabs(raw):
        return raw
    # Anchor to the backend/ directory (parent of the 'app' package)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(backend_dir, raw.lstrip("./"))


class Database:
    def __init__(self, db_url: str):
        self.db_path = _resolve_db_path(db_url)

    @asynccontextmanager
    async def get_db_connection(self):
        db = await aiosqlite.connect(self.db_path)
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("PRAGMA journal_mode=WAL;")
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()


db_helper = Database(settings.DATABASE_URL)
