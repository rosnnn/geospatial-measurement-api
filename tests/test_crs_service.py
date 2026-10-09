import pytest
from pyproj import CRS
from shapely.geometry import Point, Polygon

from app.services.crs_service import CRSService


def test_parse_crs_valid():
    crs = CRSService.parse_crs("EPSG:4326")
    assert crs.to_epsg() == 4326


def test_parse_crs_fallback():
    crs = CRSService.parse_crs("INVALID_CRS_STRING_1234")
    assert crs.to_epsg() == 4326


def test_determine_utm_zone_northern_hemisphere():
    # Centroid around Bangalore (77.59 E, 12.97 N) -> Zone 43N
    poly = Polygon([(77.58, 12.96), (77.60, 12.96), (77.60, 12.98), (77.58, 12.98), (77.58, 12.96)])
    source_crs = CRS.from_epsg(4326)

    target_crs, desc = CRSService.determine_optimal_projected_crs(poly, source_crs)
    assert target_crs.to_epsg() == 32643
    assert "UTM zone 43N" in desc


def test_determine_utm_zone_southern_hemisphere():
    # Centroid around Sydney, Australia (151.2 E, -33.8 S) -> Zone 56S
    poly = Polygon([(151.19, -33.88), (151.22, -33.88), (151.22, -33.85), (151.19, -33.85), (151.19, -33.88)])
    source_crs = CRS.from_epsg(4326)

    target_crs, desc = CRSService.determine_optimal_projected_crs(poly, source_crs)
    assert target_crs.to_epsg() == 32756
    assert "UTM zone 56S" in desc


def test_determine_polar_ups():
    # High Arctic latitude > 84 degrees
    poly = Polygon([(10.0, 85.0), (12.0, 85.0), (12.0, 86.0), (10.0, 86.0), (10.0, 85.0)])
    source_crs = CRS.from_epsg(4326)

    target_crs, desc = CRSService.determine_optimal_projected_crs(poly, source_crs)
    assert target_crs.to_epsg() == 32661
    assert "UPS North" in desc


def test_reproject_geometry():
    poly = Polygon([(77.0, 12.0), (77.1, 12.0), (77.1, 12.1), (77.0, 12.1), (77.0, 12.0)])
    source_crs = CRS.from_epsg(4326)
    target_crs = CRS.from_epsg(32643)

    projected = CRSService.reproject_geometry(poly, source_crs, target_crs)
    assert projected.is_valid
    assert not projected.is_empty
    # Projected coordinates should be in hundreds of thousands of meters, not degrees
    assert projected.centroid.x > 100000
    assert projected.centroid.y > 1000000
