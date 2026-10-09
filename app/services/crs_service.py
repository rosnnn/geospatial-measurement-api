import functools
import math
from typing import Optional, Tuple
import numpy as np
import pyproj
from pyproj import CRS, Transformer
import shapely
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import CRSProjectionError
from app.core.logging import logger


class CRSService:
    """Service providing CRS parsing, dynamic UTM/equal-area selection, and reprojection."""

    @staticmethod
    def parse_crs(crs_input: Optional[str]) -> CRS:
        """
        Parse a CRS string (EPSG code, WKT from .prj, PROJ string, or auth string) into a pyproj.CRS object.
        Falls back safely to EPSG:4326 if unparsable or None.
        """
        if not crs_input or not crs_input.strip():
            return CRS.from_epsg(4326)

        cleaned = crs_input.strip()
        try:
            return CRS.from_user_input(cleaned)
        except Exception as e:
            logger.warning(f"Could not parse CRS '{crs_input[:60]}...': {e}. Falling back to EPSG:4326.")
            return CRS.from_epsg(4326)

    @staticmethod
    def get_crs_auth_name(crs: CRS) -> str:
        """Return a clean identifier for a CRS, e.g., 'EPSG:4326' or 'EPSG:32643'."""
        try:
            auth = crs.to_authority()
            if auth and len(auth) >= 2:
                return f"{auth[0]}:{auth[1]}"
            epsg = crs.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
        except Exception:
            pass
        return crs.name or "CUSTOM_CRS"

    @classmethod
    def determine_optimal_projected_crs(
        cls,
        geometry: BaseGeometry,
        source_crs: CRS,
    ) -> Tuple[CRS, str]:
        """
        Determine the optimal metric projected CRS for a geometry based on its location and extent.
        
        Strategy:
        1. If source CRS is already projected with metric units (meters), preserve it.
        2. If geographic (coordinates in degrees, e.g. EPSG:4326, EPSG:4269):
           a. Check latitude for polar regions:
              - Latitude > 84° N -> Universal Polar Stereographic (UPS) North (EPSG:32661)
              - Latitude < -80° S -> Universal Polar Stereographic (UPS) South (EPSG:32662)
           b. Check longitudinal extent:
              - If bounds span > 6° longitude (cross-zone), use Cylindrical Equal Area (EPSG:6933)
                to preserve area fidelity across wide boundaries.
           c. Otherwise standard local UTM Zone:
              - Zone = floor((lon + 180) / 6) + 1
              - EPSG: 32600 + zone (North) or 32700 + zone (South)
              - Provides conformal, highly accurate local scale (distortion < 0.04% at central meridian).
        """
        try:
            # 1. Check if source is already projected in meters
            if source_crs.is_projected:
                axis_units = [axis.unit_name.lower() for axis in source_crs.axis_info if hasattr(axis, "unit_name")]
                if any("metre" in u or "meter" in u for u in axis_units):
                    auth_name = cls.get_crs_auth_name(source_crs)
                    return source_crs, f"{auth_name} (Source Projected Metric CRS)"

            # 2. Get centroid coordinates in WGS84 for zone selection
            centroid = geometry.centroid
            if centroid.is_empty:
                default_crs = CRS.from_epsg(3857)
                return default_crs, "EPSG:3857 (Web Mercator Fallback)"

            lon, lat = centroid.x, centroid.y

            # If source_crs is not 4326, reproject centroid to 4326 to find lon/lat
            if not source_crs.equals(CRS.from_epsg(4326)):
                try:
                    to_wgs84 = cls.get_cached_transformer(source_crs, CRS.from_epsg(4326))
                    pts = to_wgs84.transform(lon, lat)
                    lon, lat = pts[0], pts[1]
                except Exception as e:
                    logger.debug(f"Reprojection of centroid to 4326 failed: {e}")

            # Check polar extents
            if lat > 84.0:
                ups_north = CRS.from_epsg(32661)
                return ups_north, "EPSG:32661 (UPS North Stereographic)"
            if lat < -80.0:
                ups_south = CRS.from_epsg(32662)
                return ups_south, "EPSG:32662 (UPS South Stereographic)"

            # Check cross-zone span
            minx, _, maxx, _ = geometry.bounds
            span_lon = abs(maxx - minx)
            if span_lon > 6.0:
                # Wide area: Cylindrical Equal-Area (EPSG:6933)
                try:
                    equal_area = CRS.from_epsg(6933)
                    return equal_area, "EPSG:6933 (World Cylindrical Equal Area - Global Extent)"
                except Exception:
                    pass

            # Standard UTM Zone calculation
            zone_number = int(math.floor((lon + 180.0) / 6.0)) + 1
            zone_number = max(1, min(60, zone_number))

            if lat >= 0:
                epsg_code = 32600 + zone_number
                desc = f"EPSG:{epsg_code} (WGS 84 / UTM zone {zone_number}N)"
            else:
                epsg_code = 32700 + zone_number
                desc = f"EPSG:{epsg_code} (WGS 84 / UTM zone {zone_number}S)"

            target_crs = CRS.from_epsg(epsg_code)
            return target_crs, desc

        except Exception as e:
            logger.error(f"Error determining optimal projected CRS: {e}. Falling back to EPSG:3857.")
            fallback = CRS.from_epsg(3857)
            return fallback, "EPSG:3857 (Web Mercator Fallback)"

    @classmethod
    @functools.lru_cache(maxsize=128)
    def get_cached_transformer(cls, source_crs: CRS, target_crs: CRS) -> Transformer:
        """Create and cache pyproj Transformer instances for maximum throughput."""
        return Transformer.from_crs(source_crs, target_crs, always_xy=True)

    @classmethod
    def reproject_geometry(
        cls,
        geometry: BaseGeometry,
        source_crs: CRS,
        target_crs: CRS,
    ) -> BaseGeometry:
        """
        Reproject a Shapely geometry from source_crs to target_crs.
        Handles 2D, 3D coordinates and preserves topological validity.
        """
        if geometry.is_empty:
            return geometry

        if source_crs.equals(target_crs):
            return geometry

        try:
            transformer = cls.get_cached_transformer(source_crs, target_crs)

            def _transform_coords(coords: np.ndarray) -> np.ndarray:
                if coords.ndim == 1:
                    coords = coords.reshape(1, -1)
                x, y = coords[:, 0], coords[:, 1]
                res_x, res_y = transformer.transform(x, y)
                if coords.shape[1] > 2:
                    # Preserve z coordinates
                    return np.column_stack([res_x, res_y, coords[:, 2]])
                return np.column_stack([res_x, res_y])

            transformed = shapely.transform(geometry, _transform_coords)
            return transformed

        except Exception as e:
            raise CRSProjectionError(
                f"Failed to reproject geometry from {cls.get_crs_auth_name(source_crs)} "
                f"to {cls.get_crs_auth_name(target_crs)}: {str(e)}"
            )
