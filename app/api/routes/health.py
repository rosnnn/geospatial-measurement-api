import sys
from fastapi import APIRouter
import pyproj
import shapefile
import shapely

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Service Health and Diagnostics",
    description="Returns service health status, runtime versions, and geospatial library capabilities.",
)
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "python_version": sys.version.split()[0],
        "geospatial_engines": {
            "shapely_version": shapely.__version__,
            "pyproj_version": pyproj.__version__,
            "proj_version": pyproj.__proj_version__,
            "pyshp_version": shapefile.__version__,
        },
        "supported_formats": [
            {"extension": ".zip", "type": "ESRI Shapefile Archive (.shp, .shx, .dbf, .prj)"},
            {"extension": ".kml", "type": "Keyhole Markup Language"},
            {"extension": ".kmz", "type": "Compressed Keyhole Markup Language archive"},
            {"extension": ".geojson", "type": "RFC 7946 GeoJSON FeatureCollection"},
        ],
    }
