"""
FastAPI application entry point for Surf Tracker API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

# TODO: Import routers when implemented
# from routers import auth, profile, sessions, admin

app = FastAPI(
    title="Surf Tracker API",
    description="API for surf video analysis and tracking",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("[INFO] Starting Surf Tracker API...")
    # TODO: Initialize database connection pool
    # TODO: Verify Redis connection


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("[INFO] Shutting down Surf Tracker API...")
    # TODO: Close database connections
    # TODO: Close Redis connections


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "message": "Surf Tracker API is running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "database": "not_implemented",  # TODO: Check DB connection
        "redis": "not_implemented",  # TODO: Check Redis connection
        "celery": "not_implemented",  # TODO: Check Celery worker status
    }


# TODO: Include routers
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
# app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
# app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
