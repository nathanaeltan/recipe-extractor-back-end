from fastapi import FastAPI, Request
from app.api.routes import router as api_router
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

Base.metadata.create_all(engine)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour", "1000/day"])

app = FastAPI(title="Recipe Extractor API")


app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )
# Include our routes.
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
