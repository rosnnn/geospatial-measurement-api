import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from fastapi import UploadFile
from pyproj import CRS
from shapely.geometry import mapping
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    CorruptFileError,
    EntityNotFoundError,
    InvalidFileFormatError,
)
from app.core.logging import logger
from app.database.repository import FeatureRepository, FileRepository
from app.domain.models import FeatureRecord, FileRecord
from app.services.crs_service import CRSService
from app.services.measurement_service import MeasurementService
from app.services.parser_service import ParserService


class FileService:
    """Orchestrates file upload validation, parsing, spatial measurement, and database persistence."""

    @classmethod
    async def process_uploaded_file(cls, db: Session, upload_file: UploadFile) -> FileRecord:
        """
        Validate, save, parse, and process an uploaded geospatial dataset.
        """
        filename = upload_file.filename or "uploaded_file"
        file_ext = Path(filename).suffix.lower()

        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileFormatError(
                f"File format '{file_ext}' is not supported. Please upload a .zip (Shapefile), .kml, .kmz, or .geojson file."
            )

        # Temporary destination
        temp_dest = settings.UPLOAD_DIR / f"temp_{os.urandom(6).hex()}_{filename}"

        try:
            # Stream upload file to disk and monitor size
            file_size = 0
            with open(temp_dest, "wb") as buffer:
                while content := await upload_file.read(1024 * 1024):  # 1MB chunks
                    file_size += len(content)
                    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
                        raise InvalidFileFormatError(
                            f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB."
                        )
                    buffer.write(content)

            # Create initial file record in DB
            file_record = FileRepository.create_file(
                db=db,
                filename=filename,
                file_type="UNKNOWN",
                file_size_bytes=file_size,
                crs=settings.DEFAULT_FALLBACK_CRS,
            )

            # Move file to permanent storage using file_record.id
            saved_filename = f"{file_record.id}_{filename}"
            final_path = settings.UPLOAD_DIR / saved_filename
            shutil.move(str(temp_dest), str(final_path))

            # Parse features
            parsed_features, source_crs_str, detected_type = ParserService.parse_file(
                file_path=final_path, filename=filename
            )

            file_record.file_type = detected_type
            file_record.crs = source_crs_str
            db.commit()

            # Process measurements for all features
            feature_records: List[FeatureRecord] = []
            geom_counts = Counter()
            total_area_m2 = 0.0
            total_length_m = 0.0

            source_crs_obj = CRSService.parse_crs(source_crs_str)

            for pf in parsed_features:
                geom = pf.geometry
                geom_type = geom.geom_type
                geom_counts[geom_type] += 1

                # Calculate spatial measurement
                (
                    measurement_dict,
                    projected_crs_desc,
                    is_supported,
                    status_msg,
                ) = MeasurementService.calculate_feature_measurement(geom, source_crs_obj)

                # Aggregate totals
                if measurement_dict:
                    if measurement_dict.get("type") == "area":
                        total_area_m2 += measurement_dict.get("area_sq_meters", 0.0)
                    elif measurement_dict.get("type") == "length":
                        total_length_m += measurement_dict.get("length_meters", 0.0)
                    elif measurement_dict.get("type") == "geometry_collection":
                        total_area_m2 += measurement_dict.get("area_sq_meters", 0.0)
                        total_length_m += measurement_dict.get("length_meters", 0.0)

                feature_records.append(
                    FeatureRecord(
                        file_id=file_record.id,
                        feature_index=pf.feature_index,
                        feature_identifier=pf.feature_identifier,
                        geometry_type=geom_type,
                        source_crs=source_crs_str,
                        projected_crs=projected_crs_desc,
                        geometry_geojson=mapping(geom),
                        properties=pf.properties,
                        measurement_data=measurement_dict,
                        is_supported=is_supported,
                        status_message=status_msg,
                    )
                )

            # Persist features
            FeatureRepository.bulk_create(db, feature_records)

            # Mark file completed
            completed_record = FileRepository.mark_completed(
                db=db,
                file_id=file_record.id,
                feature_count=len(feature_records),
                crs=source_crs_str,
                total_area=round(total_area_m2, 2),
                total_length=round(total_length_m, 2),
                geometry_counts=dict(geom_counts),
            )

            logger.info(
                f"Successfully processed file {file_record.id} ({filename}): "
                f"{len(feature_records)} features extracted."
            )
            return completed_record

        except Exception as e:
            logger.error(f"Failed to process file '{filename}': {str(e)}", exc_info=True)
            if "file_record" in locals():
                FileRepository.mark_failed(db, file_record.id, str(e))
            raise
        finally:
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except Exception:
                    pass

    @classmethod
    def get_file_info(cls, db: Session, file_id: str) -> FileRecord:
        """Fetch metadata for a specific uploaded file."""
        record = FileRepository.get_by_id(db, file_id)
        if not record:
            raise EntityNotFoundError(f"File with id '{file_id}' not found.")
        return record

    @classmethod
    def list_files(
        cls, db: Session, skip: int = 0, limit: int = 50
    ) -> Tuple[List[FileRecord], int]:
        """Fetch paginated list of uploaded files."""
        files = FileRepository.list_files(db, skip=skip, limit=limit)
        total = FileRepository.count_files(db)
        return files, total

    @classmethod
    def delete_file(cls, db: Session, file_id: str) -> bool:
        """Delete file record and associated storage files."""
        record = FileRepository.get_by_id(db, file_id)
        if not record:
            raise EntityNotFoundError(f"File with id '{file_id}' not found.")

        # Cleanup stored file from disk
        saved_filename = f"{record.id}_{record.filename}"
        disk_path = settings.UPLOAD_DIR / saved_filename
        if disk_path.exists():
            try:
                disk_path.unlink()
            except Exception as e:
                logger.warning(f"Could not delete physical file {disk_path}: {e}")

        return FileRepository.delete(db, file_id)

    @classmethod
    def get_file_geojson(cls, db: Session, file_id: str) -> Dict[str, Any]:
        """Export file features as an RFC 7946 GeoJSON FeatureCollection."""
        file_rec = cls.get_file_info(db, file_id)
        features = FeatureRepository.get_all_by_file_id(db, file_id)

        geojson_features = []
        for feat in features:
            props = dict(feat.properties or {})
            props["feature_id"] = feat.feature_identifier
            props["geometry_type"] = feat.geometry_type
            props["is_supported"] = feat.is_supported
            props["status_message"] = feat.status_message

            # Embed measurements in properties
            if feat.measurement_data:
                for k, v in feat.measurement_data.items():
                    props[f"measurement_{k}"] = v

            geojson_features.append(
                {
                    "type": "Feature",
                    "id": feat.feature_identifier or feat.feature_index,
                    "geometry": feat.geometry_geojson,
                    "properties": props,
                }
            )

        return {
            "type": "FeatureCollection",
            "metadata": {
                "file_id": file_rec.id,
                "filename": file_rec.filename,
                "feature_count": file_rec.feature_count,
                "crs": file_rec.crs,
                "status": file_rec.status,
                "total_area_sq_meters": file_rec.total_area_sq_meters,
                "total_length_meters": file_rec.total_length_meters,
            },
            "features": geojson_features,
        }
