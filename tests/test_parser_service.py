from pathlib import Path
import pytest

from app.core.exceptions import CorruptFileError, MissingShapefileComponentError
from app.services.parser_service import ParserService


def test_parse_kml_file(sample_kml_path: Path):
    features, crs_str, file_type = ParserService.parse_file(sample_kml_path, sample_kml_path.name)
    assert file_type == "KML"
    assert crs_str == "EPSG:4326"
    assert len(features) == 6

    geom_types = [f.geometry.geom_type for f in features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types

    # Verify properties extracted
    polygon_feat = next(f for f in features if f.geometry.geom_type == "Polygon")
    assert "zoning_code" in polygon_feat.properties or "name" in polygon_feat.properties


def test_parse_shapefile_zip(sample_shp_zip_path: Path):
    features, crs_str, file_type = ParserService.parse_file(sample_shp_zip_path, sample_shp_zip_path.name)
    assert file_type == "SHAPEFILE"
    assert "EPSG:4326" in crs_str
    assert len(features) == 3

    for f in features:
        assert f.geometry.geom_type == "Polygon"
        assert "crop_type" in f.properties
        assert "field_id" in f.properties


def test_parse_points_kml(sample_points_kml_path: Path):
    features, crs_str, file_type = ParserService.parse_file(sample_points_kml_path, sample_points_kml_path.name)
    assert file_type == "KML"
    assert len(features) == 2
    for f in features:
        assert f.geometry.geom_type == "Point"
