from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature object conforming to RFC 7946."""

    type: Literal["Feature"] = "Feature"
    id: Any
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection object conforming to RFC 7946."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]
    metadata: Dict[str, Any] = Field(default_factory=dict)
