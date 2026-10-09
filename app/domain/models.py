import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def generate_short_id() -> str:
    """Generate a clean, readable short ID (e.g., 'a8f1b2c4') matching problem statement example 'abc123'."""
    return uuid.uuid4().hex[:8]


class FileRecord(Base):
    """Represents an uploaded geospatial dataset and its processing summary."""

    __tablename__ = "files"

    id = Column(String(32), primary_key=True, default=generate_short_id, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)  # SHAPEFILE, KML, KMZ, GEOJSON
    file_size_bytes = Column(Integer, nullable=False, default=0)
    feature_count = Column(Integer, nullable=False, default=0)
    crs = Column(String(128), nullable=False, default="EPSG:4326")
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = Column(Text, nullable=True)

    # Summary metrics
    total_area_sq_meters = Column(Float, nullable=False, default=0.0)
    total_length_meters = Column(Float, nullable=False, default=0.0)
    geometry_counts = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationship to features
    features = relationship(
        "FeatureRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureRecord.feature_index",
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "feature_count": self.feature_count,
            "crs": self.crs,
            "status": self.status,
            "error_message": self.error_message,
            "total_area_sq_meters": round(self.total_area_sq_meters, 2),
            "total_length_meters": round(self.total_length_meters, 2),
            "geometry_counts": self.geometry_counts or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FeatureRecord(Base):
    """Represents an individual geospatial feature within an uploaded file."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    file_id = Column(String(32), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False, index=True)
    feature_identifier = Column(String(128), nullable=True)  # Original feature ID or index
    geometry_type = Column(String(64), nullable=False, index=True)
    source_crs = Column(String(128), nullable=False)
    projected_crs = Column(String(128), nullable=True)

    # Serialized geospatial payload
    geometry_geojson = Column(JSON, nullable=False)
    properties = Column(JSON, nullable=False, default=dict)
    measurement_data = Column(JSON, nullable=True)

    is_supported = Column(Boolean, nullable=False, default=True)
    status_message = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)

    file = relationship("FileRecord", back_populates="features")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "feature_index": self.feature_index,
            "feature_id": self.feature_identifier or f"feature_{self.feature_index}",
            "geometry_type": self.geometry_type,
            "source_crs": self.source_crs,
            "projected_crs": self.projected_crs,
            "geometry": self.geometry_geojson,
            "properties": self.properties or {},
            "measurement": self.measurement_data,
            "is_supported": self.is_supported,
            "status_message": self.status_message,
        }
