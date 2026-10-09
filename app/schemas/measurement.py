from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class MeasurementSummary(BaseModel):
    """Aggregated measurements for the entire dataset."""

    total_area_sq_meters: float = Field(0.0, description="Total polygon area in square meters")
    total_area_hectares: float = Field(0.0, description="Total polygon area in hectares")
    total_area_sq_km: float = Field(0.0, description="Total polygon area in square kilometers")
    total_length_meters: float = Field(0.0, description="Total linestring length in meters")
    total_length_km: float = Field(0.0, description="Total linestring length in kilometers")
    geometry_counts: Dict[str, int] = Field(default_factory=dict, description="Count of features by geometry type")


class FeatureMeasurementDetail(BaseModel):
    """Detailed measurement information for a single feature."""

    feature_index: int = Field(..., description="Zero-based feature order index")
    feature_id: Union[str, int] = Field(..., description="Feature identifier (from source or generated index)")
    geometry_type: str = Field(..., description="Geometry type (e.g. Polygon, LineString, Point)")
    crs: str = Field(..., description="Source Coordinate Reference System (e.g. EPSG:4326)")
    projected_crs: Optional[str] = Field(None, description="Projected metric CRS used for measurement (e.g. EPSG:32643)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Attributes and properties from source file")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON representation of geometry")
    measurement: Optional[Dict[str, Any]] = Field(None, description="Computed measurement payload (area, length, etc.)")
    is_supported: bool = Field(True, description="Whether this geometry type supports spatial measurement")
    status_message: Optional[str] = Field(None, description="Status or explanation note (e.g. for Point or invalid geometry)")

    model_config = ConfigDict(from_attributes=True)


class FileMeasurementsResponse(BaseModel):
    """Complete response for GET /api/files/{id}/measurements/."""

    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original file name")
    crs: str = Field(..., description="Source CRS")
    status: str = Field(..., description="Processing status")
    total_features: int = Field(..., description="Total feature count")
    summary: MeasurementSummary = Field(..., description="Summary statistics for measurements")
    features: List[FeatureMeasurementDetail] = Field(..., description="Array of feature measurements")
