from typing import Any, Dict, Optional, Tuple
from pyproj import CRS, Geod
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry
import shapely

from app.core.logging import logger
from app.services.crs_service import CRSService


class MeasurementService:
    """Calculates spatial measurements (area, length, perimeter) with CRS reprojection."""

    _geod = Geod(ellps="WGS84")

    # Conversion factors
    SQ_METERS_TO_HECTARES = 1e-4
    SQ_METERS_TO_SQ_KM = 1e-6
    SQ_METERS_TO_ACRES = 0.000247105
    METERS_TO_KM = 1e-3
    METERS_TO_MILES = 0.000621371

    @classmethod
    def calculate_feature_measurement(
        cls,
        geometry: BaseGeometry,
        source_crs: CRS,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool, Optional[str]]:
        """
        Process a geometry and compute spatial measurements.
        
        Returns:
            Tuple of:
            - measurement_dict (or None for Point/unsupported)
            - projected_crs_name (e.g. "EPSG:32643 (WGS 84 / UTM zone 43N)")
            - is_supported (bool)
            - status_message (str or None)
        """
        if geometry is None or geometry.is_empty:
            return None, None, False, "Geometry is empty or null."

        # Validate geometry; heal minor topological self-intersections if necessary
        if not geometry.is_valid:
            try:
                geometry = shapely.make_valid(geometry)
                logger.info(f"Repaired invalid geometry of type {geometry.geom_type}")
            except Exception as e:
                return None, None, False, f"Geometry is invalid and could not be repaired: {str(e)}"

        geom_type = geometry.geom_type

        # 1. Point / MultiPoint
        if geom_type in ("Point", "MultiPoint"):
            coords = []
            if geom_type == "Point":
                coords = [round(geometry.x, 6), round(geometry.y, 6)]
                msg = f"Points have zero area and length. Position: ({coords[0]}, {coords[1]})."
            else:
                pts = [(round(p.x, 6), round(p.y, 6)) for p in geometry.geoms]
                msg = f"MultiPoint geometry contains {len(geometry.geoms)} point locations."
            return None, None, False, msg

        # 2. Supported measurement geometries: Polygon, MultiPolygon, LineString, MultiLineString, LinearRing
        supported_types = ("Polygon", "MultiPolygon", "LineString", "MultiLineString", "LinearRing")
        if geom_type not in supported_types and geom_type != "GeometryCollection":
            return None, None, False, f"Geometry type '{geom_type}' is not supported for measurement calculations."

        # Determine optimal metric projected CRS
        target_crs, proj_desc = CRSService.determine_optimal_projected_crs(geometry, source_crs)

        # Reproject to metric coordinates
        try:
            proj_geom = CRSService.reproject_geometry(geometry, source_crs, target_crs)
        except Exception as e:
            logger.error(f"Reprojection error for {geom_type}: {e}")
            return None, None, False, f"Projection transformation failed: {str(e)}"

        # 3. Polygon / MultiPolygon Measurements
        if geom_type in ("Polygon", "MultiPolygon"):
            area_m2 = float(proj_geom.area)
            perimeter_m = float(proj_geom.length)

            measurement = {
                "type": "area",
                "area_sq_meters": round(area_m2, 2),
                "area_hectares": round(area_m2 * cls.SQ_METERS_TO_HECTARES, 4),
                "area_sq_km": round(area_m2 * cls.SQ_METERS_TO_SQ_KM, 6),
                "area_acres": round(area_m2 * cls.SQ_METERS_TO_ACRES, 4),
                "perimeter_meters": round(perimeter_m, 2),
                "perimeter_km": round(perimeter_m * cls.METERS_TO_KM, 4),
                "projected_crs": proj_desc,
            }

            # Optional geodesic ellipsoidal cross-verification if coordinates are WGS84
            if source_crs.equals(CRS.from_epsg(4326)):
                try:
                    poly_for_geod = geometry if geom_type == "Polygon" else geometry.geoms[0]
                    ext_coords = poly_for_geod.exterior.coords
                    lons = [c[0] for c in ext_coords]
                    lats = [c[1] for c in ext_coords]
                    geod_area, geod_perimeter = cls._geod.polygon_area_perimeter(lons, lats)
                    measurement["geodesic_verification"] = {
                        "area_sq_meters": round(abs(geod_area), 2),
                        "perimeter_meters": round(geod_perimeter, 2),
                        "ellipsoid": "WGS84",
                    }
                except Exception:
                    pass

            return measurement, proj_desc, True, None

        # 4. LineString / MultiLineString Measurements
        if geom_type in ("LineString", "MultiLineString", "LinearRing"):
            length_m = float(proj_geom.length)

            measurement = {
                "type": "length",
                "length_meters": round(length_m, 2),
                "length_km": round(length_m * cls.METERS_TO_KM, 4),
                "length_miles": round(length_m * cls.METERS_TO_MILES, 4),
                "projected_crs": proj_desc,
            }

            if source_crs.equals(CRS.from_epsg(4326)):
                try:
                    line_for_geod = geometry if geom_type == "LineString" else geometry.geoms[0]
                    coords = line_for_geod.coords
                    lons = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    total_len, _ = cls._geod.line_lengths(lons, lats)
                    measurement["geodesic_verification"] = {
                        "length_meters": round(float(total_len), 2),
                        "ellipsoid": "WGS84",
                    }
                except Exception:
                    pass

            return measurement, proj_desc, True, None

        # 5. GeometryCollection (Graceful Handling)
        if geom_type == "GeometryCollection":
            total_area_m2 = 0.0
            total_len_m = 0.0
            part_types = []

            for part in proj_geom.geoms:
                part_types.append(part.geom_type)
                if part.geom_type in ("Polygon", "MultiPolygon"):
                    total_area_m2 += float(part.area)
                elif part.geom_type in ("LineString", "MultiLineString", "LinearRing"):
                    total_len_m += float(part.length)

            measurement = {
                "type": "geometry_collection",
                "contained_types": list(set(part_types)),
                "area_sq_meters": round(total_area_m2, 2),
                "area_hectares": round(total_area_m2 * cls.SQ_METERS_TO_HECTARES, 4),
                "length_meters": round(total_len_m, 2),
                "length_km": round(total_len_m * cls.METERS_TO_KM, 4),
                "projected_crs": proj_desc,
            }
            return (
                measurement,
                proj_desc,
                True,
                f"GeometryCollection containing {len(proj_geom.geoms)} components measured.",
            )

        return None, None, False, f"Unhandled geometry type: {geom_type}"
