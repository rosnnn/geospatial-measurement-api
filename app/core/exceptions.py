from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class GeospatialException(Exception):
    """Base exception for all geospatial processing errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidFileFormatError(GeospatialException):
    """Raised when an uploaded file is not a supported geospatial format."""
    pass


class CorruptFileError(GeospatialException):
    """Raised when an uploaded file cannot be parsed or is corrupted."""
    pass


class MissingShapefileComponentError(GeospatialException):
    """Raised when a shapefile zip is missing required components (.shp, .shx, .dbf)."""
    pass


class CRSProjectionError(GeospatialException):
    """Raised when coordinates or geometries cannot be transformed to a projected CRS."""
    pass


class EntityNotFoundError(GeospatialException):
    """Raised when a requested resource (e.g. file ID) does not exist."""
    pass
