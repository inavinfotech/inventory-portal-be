import time
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app")

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": int(process_time * 1000),
            "client_ip": request.client.host if request.client else "unknown",
        }
        
        logger.info(json.dumps(log_data))
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.buckets = {} # In-memory storage (client_ip -> [timestamps])

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old timestamps
        if client_ip not in self.buckets:
            self.buckets[client_ip] = []
        
        self.buckets[client_ip] = [t for t in self.buckets[client_ip] if now - t < self.window]
        
        if len(self.buckets[client_ip]) >= self.limit:
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded"}),
                status_code=429,
                media_type="application/json"
            )
        
        self.buckets[client_ip].append(now)
        return await call_next(request)
