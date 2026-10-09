from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    DESCRIPTION: str = (
        "Production-grade FastAPI service for ingesting geospatial datasets (Shapefiles, KML, KMZ), "
        "reprojecting geographic coordinates to metric projected CRSs (UTM / Equal-Area), and "
        "computing accurate feature measurements (Polygon area, LineString length)."
    )

    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    SAMPLE_DATA_DIR: Path = BASE_DIR / "sample_data"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'geospatial.db'}"

    # File Upload Constraints
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: List[str] = [".zip", ".kml", ".kmz", ".geojson", ".json"]

    # Geospatial Calculation Defaults
    DEFAULT_FALLBACK_CRS: str = "EPSG:4326"
    MAX_FEATURES_PER_PAGE: int = 500

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.SAMPLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
