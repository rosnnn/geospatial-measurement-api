from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import files, health, measurements
from app.core.config import settings
from app.core.exceptions import GeospatialException
from app.core.logging import logger
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown routines."""
    logger.info("Initializing GeoMeasure application database and resources...")
    init_db()
    logger.info("Application initialized successfully.")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for domain exceptions
@app.exception_handler(GeospatialException)
async def geospatial_exception_handler(request: Request, exc: GeospatialException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Mount static assets
static_dir = settings.BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API Routers
app.include_router(files.router, prefix=settings.API_V1_PREFIX)
app.include_router(measurements.router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)


# Web UI Dashboard Route
@app.get("/", response_class=HTMLResponse, tags=["Dashboard"], include_in_schema=False)
async def serve_dashboard():
    """Serves the interactive Leaflet GIS visualizer and measurement dashboard."""
    template_path = settings.BASE_DIR / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>GeoMeasure API is running. Visit <a href='/docs'>/docs</a> for Swagger documentation.</h2>")
