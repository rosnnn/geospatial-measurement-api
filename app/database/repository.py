from typing import Any, Dict, List, Optional
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.domain.models import FeatureRecord, FileRecord


class FileRepository:
    """Repository handling database operations for uploaded geospatial files."""

    @staticmethod
    def create_file(
        db: Session,
        filename: str,
        file_type: str,
        file_size_bytes: int,
        crs: str = "EPSG:4326",
    ) -> FileRecord:
        record = FileRecord(
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            crs=crs,
            status="PROCESSING",
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_by_id(db: Session, file_id: str) -> Optional[FileRecord]:
        return db.query(FileRecord).filter(FileRecord.id == file_id).first()

    @staticmethod
    def list_files(db: Session, skip: int = 0, limit: int = 50) -> List[FileRecord]:
        return (
            db.query(FileRecord)
            .order_by(desc(FileRecord.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_files(db: Session) -> int:
        return db.query(FileRecord).count()

    @staticmethod
    def mark_completed(
        db: Session,
        file_id: str,
        feature_count: int,
        crs: str,
        total_area: float,
        total_length: float,
        geometry_counts: Dict[str, int],
    ) -> Optional[FileRecord]:
        record = FileRepository.get_by_id(db, file_id)
        if record:
            record.status = "COMPLETED"
            record.feature_count = feature_count
            record.crs = crs
            record.total_area_sq_meters = total_area
            record.total_length_meters = total_length
            record.geometry_counts = geometry_counts
            record.error_message = None
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def mark_failed(db: Session, file_id: str, error_message: str) -> Optional[FileRecord]:
        record = FileRepository.get_by_id(db, file_id)
        if record:
            record.status = "FAILED"
            record.error_message = error_message
            db.commit()
            db.refresh(record)
        return record

    @staticmethod
    def delete(db: Session, file_id: str) -> bool:
        record = FileRepository.get_by_id(db, file_id)
        if record:
            db.delete(record)
            db.commit()
            return True
        return False


class FeatureRepository:
    """Repository handling database operations for geospatial features."""

    @staticmethod
    def bulk_create(db: Session, feature_records: List[FeatureRecord]) -> None:
        if feature_records:
            db.bulk_save_objects(feature_records)
            db.commit()

    @staticmethod
    def get_by_file_id(
        db: Session,
        file_id: str,
        geometry_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 200,
    ) -> List[FeatureRecord]:
        query = db.query(FeatureRecord).filter(FeatureRecord.file_id == file_id)
        if geometry_type:
            query = query.filter(FeatureRecord.geometry_type.ilike(geometry_type))
        return query.order_by(FeatureRecord.feature_index).offset(skip).limit(limit).all()

    @staticmethod
    def get_all_by_file_id(db: Session, file_id: str) -> List[FeatureRecord]:
        return (
            db.query(FeatureRecord)
            .filter(FeatureRecord.file_id == file_id)
            .order_by(FeatureRecord.feature_index)
            .all()
        )

    @staticmethod
    def count_by_file_id(
        db: Session,
        file_id: str,
        geometry_type: Optional[str] = None,
    ) -> int:
        query = db.query(FeatureRecord).filter(FeatureRecord.file_id == file_id)
        if geometry_type:
            query = query.filter(FeatureRecord.geometry_type.ilike(geometry_type))
        return query.count()
