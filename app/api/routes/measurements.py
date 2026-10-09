from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import EntityNotFoundError
from app.database.repository import FeatureRepository
from app.schemas.measurement import (
    FeatureMeasurementDetail,
    FileMeasurementsResponse,
    MeasurementSummary,
)
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Measurements"])


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get spatial measurements for all features in a file",
    description=(
        "Returns calculated measurements for features in the specified file. "
        "Polygons return area (m², ha, km², acres) and perimeter. "
        "LineStrings return length (m, km, miles). "
        "Points gracefully return coordinate position without crashing."
    ),
)
def get_file_measurements(
    id: str,
    geometry_type: Optional[str] = Query(
        None,
        description="Optional filter by geometry type (e.g. 'Polygon', 'LineString', 'Point')",
    ),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(500, ge=1, le=1000, description="Page limit"),
    db: Session = Depends(get_db),
):
    try:
        file_record = FileService.get_file_info(db, id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    feature_records = FeatureRepository.get_by_file_id(
        db=db,
        file_id=id,
        geometry_type=geometry_type,
        skip=skip,
        limit=limit,
    )

    feature_details = [
        FeatureMeasurementDetail(
            feature_index=f.feature_index,
            feature_id=f.feature_identifier or f"feature_{f.feature_index}",
            geometry_type=f.geometry_type,
            crs=f.source_crs,
            projected_crs=f.projected_crs,
            properties=f.properties or {},
            geometry=f.geometry_geojson,
            measurement=f.measurement_data,
            is_supported=f.is_supported,
            status_message=f.status_message,
        )
        for f in feature_records
    ]

    total_area_m2 = file_record.total_area_sq_meters
    total_len_m = file_record.total_length_meters

    summary = MeasurementSummary(
        total_area_sq_meters=round(total_area_m2, 2),
        total_area_hectares=round(total_area_m2 * 1e-4, 4),
        total_area_sq_km=round(total_area_m2 * 1e-6, 6),
        total_length_meters=round(total_len_m, 2),
        total_length_km=round(total_len_m * 1e-3, 4),
        geometry_counts=file_record.geometry_counts or {},
    )

    return FileMeasurementsResponse(
        file_id=file_record.id,
        filename=file_record.filename,
        crs=file_record.crs,
        status=file_record.status,
        total_features=file_record.feature_count,
        summary=summary,
        features=feature_details,
    )
