from fastapi import FastAPI, HTTPException
from app.api.auth import router as auth_router
from app.api.apps import router as apps_router
from app.api.inventory import router as inventory_router
from app.api.products import router as products_router
from app.api.movements import router as movements_router
from app.api.reservations import router as reservations_router
from app.core.config import settings
from app.core.middleware import StructuredLoggingMiddleware, RateLimitMiddleware
from fastapi.middleware.cors import CORSMiddleware
from app.core.exceptions import global_exception_handler, http_exception_handler

import asyncio
from contextlib import asynccontextmanager
from app.services.reservation_service import reservation_service
from app.db.init_db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    await init_db()
    
    # Background Task for Cleanup
    async def cleanup_loop():
        import logging
        logger = logging.getLogger("uvicorn.error")
        while True:
            try:
                await reservation_service.cleanup_stale_reservations(30)
            except Exception as e:
                logger.error(f"Reservation cleanup failed: {e}", exc_info=True)
            await asyncio.sleep(300) # Every 5 minutes

    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware  
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Middleware
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, limit=200, window=60)

# Add Error Handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(apps_router, prefix=settings.API_V1_STR)
app.include_router(inventory_router, prefix=settings.API_V1_STR)
app.include_router(products_router, prefix=settings.API_V1_STR)
app.include_router(movements_router, prefix=settings.API_V1_STR)
app.include_router(reservations_router, prefix=settings.API_V1_STR)

@app.get("/health")
async def health_check():
    from app.db.database import db_helper
    try:
        async with db_helper.get_db_connection() as db:
            await db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}, 503

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
