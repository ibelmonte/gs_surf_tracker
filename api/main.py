"""
FastAPI application entry point for Surf Tracker API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import engine, Base

# Import routers
from routers import auth, profile, sessions, files

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

    # Create database tables if they don't exist
    # Note: In production, use Alembic migrations instead
    try:
        # Import models to register them
        from models import User, Profile, SurfingSession
        Base.metadata.create_all(bind=engine)
        print("[INFO] Database tables initialized")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")

    # Create data directories
    import os
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.QUEUE_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.PROFILE_PICTURES_DIR, exist_ok=True)
    print("[INFO] Data directories initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("[INFO] Shutting down Surf Tracker API...")


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
        "database": "connected",  # TODO: Add actual health check
        "redis": "not_implemented",  # TODO: Check Redis connection
        "celery": "not_implemented",  # TODO: Check Celery worker status
    }


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
