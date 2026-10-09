from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FileInfoResponse(BaseModel):
    """File metadata response matching problem statement specification."""

    id: str = Field(..., description="Unique identifier of the uploaded file (e.g. 'abc123')")
    filename: str = Field(..., description="Original name of the uploaded file")
    feature_count: int = Field(..., description="Total number of geospatial features extracted")
    crs: str = Field(..., description="Source Coordinate Reference System (e.g. 'EPSG:4326')")
    status: str = Field(..., description="Processing status: 'PROCESSING', 'COMPLETED', or 'FAILED'")

    # Extended production attributes
    file_type: Optional[str] = Field(None, description="Format type: SHAPEFILE, KML, KMZ, GEOJSON")
    file_size_bytes: Optional[int] = Field(None, description="Size of uploaded file in bytes")
    total_area_sq_meters: Optional[float] = Field(0.0, description="Sum of areas across all polygon features in m²")
    total_length_meters: Optional[float] = Field(0.0, description="Sum of lengths across all linestring features in meters")
    geometry_counts: Optional[Dict[str, int]] = Field(default_factory=dict, description="Count breakdown by geometry type")
    error_message: Optional[str] = Field(None, description="Details of failure if status is FAILED")
    created_at: Optional[str] = Field(None, description="Upload timestamp")

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    """Paginated list of uploaded geospatial files."""

    total: int = Field(..., description="Total number of uploaded files")
    skip: int = Field(..., description="Pagination offset")
    limit: int = Field(..., description="Pagination limit")
    items: List[FileInfoResponse] = Field(..., description="List of file records")


class DeleteFileResponse(BaseModel):
    """Response returned upon file deletion."""

    id: str
    message: str
    success: bool
