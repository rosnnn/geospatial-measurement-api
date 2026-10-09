from typing import Any, Dict
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.exceptions import (
    CorruptFileError,
    EntityNotFoundError,
    InvalidFileFormatError,
    MissingShapefileComponentError,
)
from app.schemas.file import DeleteFileResponse, FileInfoResponse, FileListResponse
from app.schemas.geojson import GeoJSONFeatureCollection
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["Files"])


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description=(
        "Upload a geospatial file (.zip containing Shapefile components, .kml, .kmz, or .geojson). "
        "The service extracts all features, identifies geometries, detects CRS, dynamically selects "
        "appropriate projected coordinate systems, and computes spatial measurements (area/length)."
    ),
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file archive (.zip) or KML file (.kml)"),
    db: Session = Depends(get_db),
):
    try:
        record = await FileService.process_uploaded_file(db, file)
        return FileInfoResponse(
            id=record.id,
            filename=record.filename,
            feature_count=record.feature_count,
            crs=record.crs,
            status=record.status,
            file_type=record.file_type,
            file_size_bytes=record.file_size_bytes,
            total_area_sq_meters=record.total_area_sq_meters,
            total_length_meters=record.total_length_meters,
            geometry_counts=record.geometry_counts or {},
            error_message=record.error_message,
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
    except (InvalidFileFormatError, MissingShapefileComponentError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CorruptFileError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the geospatial file: {str(e)}",
        )


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get geospatial file metadata",
    description="Returns metadata and processing status for an uploaded geospatial file by ID.",
)
def get_file_info(
    id: str,
    db: Session = Depends(get_db),
):
    try:
        record = FileService.get_file_info(db, id)
        return FileInfoResponse(
            id=record.id,
            filename=record.filename,
            feature_count=record.feature_count,
            crs=record.crs,
            status=record.status,
            file_type=record.file_type,
            file_size_bytes=record.file_size_bytes,
            total_area_sq_meters=record.total_area_sq_meters,
            total_length_meters=record.total_length_meters,
            geometry_counts=record.geometry_counts or {},
            error_message=record.error_message,
            created_at=record.created_at.isoformat() if record.created_at else None,
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List all uploaded geospatial files",
    description="Returns a paginated list of uploaded geospatial files and summary metrics.",
)
def list_files(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    records, total = FileService.list_files(db, skip=skip, limit=limit)
    items = [
        FileInfoResponse(
            id=r.id,
            filename=r.filename,
            feature_count=r.feature_count,
            crs=r.crs,
            status=r.status,
            file_type=r.file_type,
            file_size_bytes=r.file_size_bytes,
            total_area_sq_meters=r.total_area_sq_meters,
            total_length_meters=r.total_length_meters,
            geometry_counts=r.geometry_counts or {},
            error_message=r.error_message,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]
    return FileListResponse(total=total, skip=skip, limit=limit, items=items)


@router.delete(
    "/{id}/",
    response_model=DeleteFileResponse,
    summary="Delete a geospatial file",
    description="Deletes the file record, associated features, and local storage data.",
)
def delete_file(
    id: str,
    db: Session = Depends(get_db),
):
    try:
        success = FileService.delete_file(db, id)
        return DeleteFileResponse(
            id=id,
            message="Geospatial dataset and associated measurements deleted successfully.",
            success=success,
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{id}/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Export dataset as standard GeoJSON",
    description="Returns the processed features and calculated measurements as an RFC 7946 GeoJSON FeatureCollection.",
)
def get_file_geojson(
    id: str,
    db: Session = Depends(get_db),
):
    try:
        return FileService.get_file_geojson(db, id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
