import pytest
from pyproj import CRS
from shapely.geometry import LineString, Point, Polygon

from app.services.measurement_service import MeasurementService


def test_polygon_measurement():
    poly = Polygon([(77.59, 12.97), (77.60, 12.97), (77.60, 12.98), (77.59, 12.98), (77.59, 12.97)])
    source_crs = CRS.from_epsg(4326)

    meas, proj_desc, is_supported, msg = MeasurementService.calculate_feature_measurement(poly, source_crs)

    assert is_supported is True
    assert meas is not None
    assert meas["type"] == "area"
    assert meas["area_sq_meters"] > 0
    assert meas["area_hectares"] > 0
    assert meas["perimeter_meters"] > 0
    assert "UTM zone 43N" in proj_desc


def test_linestring_measurement():
    line = LineString([(77.59, 12.97), (77.60, 12.97), (77.61, 12.98)])
    source_crs = CRS.from_epsg(4326)

    meas, proj_desc, is_supported, msg = MeasurementService.calculate_feature_measurement(line, source_crs)

    assert is_supported is True
    assert meas is not None
    assert meas["type"] == "length"
    assert meas["length_meters"] > 0
    assert meas["length_km"] > 0


def test_point_measurement_graceful():
    pt = Point(77.59, 12.97)
    source_crs = CRS.from_epsg(4326)

    meas, proj_desc, is_supported, msg = MeasurementService.calculate_feature_measurement(pt, source_crs)

    assert is_supported is False
    assert meas is None
    assert "Points have zero area and length" in msg


def test_self_intersecting_polygon_repair():
    # Bow-tie polygon (self-intersecting)
    bow_tie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    source_crs = CRS.from_epsg(4326)

    meas, proj_desc, is_supported, msg = MeasurementService.calculate_feature_measurement(bow_tie, source_crs)
    # Should not crash; heals into MultiPolygon or Polygon and computes area
    assert is_supported is True
    assert meas is not None
    assert meas["area_sq_meters"] > 0
