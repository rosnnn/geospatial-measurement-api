import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pyproj import CRS
import shapefile
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    mapping,
    shape,
)
from shapely.geometry.base import BaseGeometry

from app.core.exceptions import (
    CorruptFileError,
    InvalidFileFormatError,
    MissingShapefileComponentError,
)
from app.core.logging import logger
from app.services.crs_service import CRSService


class ParsedFeature:
    """Intermediate data container for an extracted geospatial feature."""

    def __init__(
        self,
        feature_index: int,
        feature_identifier: str,
        geometry: BaseGeometry,
        properties: Dict[str, Any],
        source_crs: str,
    ):
        self.feature_index = feature_index
        self.feature_identifier = feature_identifier
        self.geometry = geometry
        self.properties = properties
        self.source_crs = source_crs


class ParserService:
    """Resilient parser for Shapefile archives (.zip), KML, KMZ, and GeoJSON files."""

    @classmethod
    def parse_file(
        cls, file_path: Path, filename: str
    ) -> Tuple[List[ParsedFeature], str, str]:
        """
        Dispatches file to appropriate parser based on file extension.
        
        Returns:
            Tuple of:
            - list of ParsedFeature
            - source CRS string (e.g. "EPSG:4326")
            - detected file type ("SHAPEFILE", "KML", "KMZ", "GEOJSON")
        """
        lower_name = filename.lower()

        if lower_name.endswith(".zip"):
            return cls.parse_shapefile_zip(file_path)
        elif lower_name.endswith(".kml"):
            return cls.parse_kml_file(file_path)
        elif lower_name.endswith(".kmz"):
            return cls.parse_kmz_file(file_path)
        elif lower_name.endswith(".geojson") or lower_name.endswith(".json"):
            return cls.parse_geojson_file(file_path)
        else:
            raise InvalidFileFormatError(
                f"Unsupported file extension for '{filename}'. Allowed formats: .zip (Shapefile), .kml, .kmz, .geojson"
            )

    # =========================================================================
    # SHAPEFILE (.ZIP) PARSER
    # =========================================================================
    @classmethod
    def parse_shapefile_zip(cls, zip_path: Path) -> Tuple[List[ParsedFeature], str, str]:
        """Extract and parse a Shapefile zip package."""
        temp_dir = tempfile.mkdtemp(prefix="shp_extract_")
        try:
            if not zipfile.is_zipfile(zip_path):
                raise CorruptFileError("Uploaded .zip file is not a valid zip archive.")

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Protect against zip-slip directory traversal
                for member in zf.namelist():
                    extracted_path = os.path.abspath(os.path.join(temp_dir, member))
                    if not extracted_path.startswith(os.path.abspath(temp_dir)):
                        raise CorruptFileError("Malicious zip archive structure detected.")
                zf.extractall(temp_dir)

            # Locate the .shp file
            shp_files = list(Path(temp_dir).rglob("*.shp"))
            if not shp_files:
                raise MissingShapefileComponentError(
                    "No .shp file found inside the zip archive. Ensure the archive contains your Shapefile components."
                )

            shp_path = shp_files[0]
            shp_stem = shp_path.stem
            shp_dir = shp_path.parent

            # Verify presence of essential shapefile companion files
            dbf_file = shp_dir / f"{shp_stem}.dbf"
            shx_file = shp_dir / f"{shp_stem}.shx"
            prj_file = shp_dir / f"{shp_stem}.prj"

            if not dbf_file.exists():
                raise MissingShapefileComponentError(
                    f"Shapefile is missing required attribute database file: '{shp_stem}.dbf'"
                )

            # Determine CRS from .prj if available
            source_crs_str = "EPSG:4326"
            if prj_file.exists():
                try:
                    with open(prj_file, "r", encoding="utf-8", errors="ignore") as f:
                        prj_content = f.read().strip()
                    if prj_content:
                        parsed_crs = CRSService.parse_crs(prj_content)
                        source_crs_str = CRSService.get_crs_auth_name(parsed_crs)
                except Exception as e:
                    logger.warning(f"Error parsing .prj file: {e}. Defaulting to EPSG:4326.")

            # Read features using pure-Python pyshp
            features: List[ParsedFeature] = []
            with shapefile.Reader(str(shp_path)) as sf:
                field_names = [f[0] for f in sf.fields[1:]]

                for idx, shape_rec in enumerate(sf.shapeRecords()):
                    # Construct geometry from __geo_interface__
                    try:
                        raw_geom_dict = shape_rec.shape.__geo_interface__
                        if not raw_geom_dict or not raw_geom_dict.get("coordinates"):
                            continue
                        geom = shape(raw_geom_dict)
                    except Exception as e:
                        logger.warning(f"Failed to convert shape record {idx} to geometry: {e}")
                        continue

                    # Extract record properties safely
                    props: Dict[str, Any] = {}
                    try:
                        props_dict = shape_rec.record.as_dict()
                        for k, v in props_dict.items():
                            # Clean binary or non-serializable values
                            if isinstance(v, (bytes, bytearray)):
                                try:
                                    props[k] = v.decode("utf-8", errors="ignore")
                                except Exception:
                                    props[k] = str(v)
                            else:
                                props[k] = v
                    except Exception:
                        # Fallback to field names and record values
                        for f_idx, f_name in enumerate(field_names):
                            if f_idx < len(shape_rec.record):
                                val = shape_rec.record[f_idx]
                                props[f_name] = str(val) if val is not None else None

                    feature_id = str(props.get("id") or props.get("ID") or f"shp_{idx}")
                    features.append(
                        ParsedFeature(
                            feature_index=idx,
                            feature_identifier=feature_id,
                            geometry=geom,
                            properties=props,
                            source_crs=source_crs_str,
                        )
                    )

            if not features:
                raise CorruptFileError("Shapefile was read, but contained no valid geometry records.")

            return features, source_crs_str, "SHAPEFILE"

        except (MissingShapefileComponentError, InvalidFileFormatError, CorruptFileError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error parsing shapefile zip: {e}", exc_info=True)
            raise CorruptFileError(f"Failed to process Shapefile archive: {str(e)}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # =========================================================================
    # KML & KMZ PARSER
    # =========================================================================
    @classmethod
    def parse_kml_file(cls, kml_path: Path) -> Tuple[List[ParsedFeature], str, str]:
        """Parse an OGC KML XML file."""
        try:
            with open(kml_path, "rb") as f:
                content = f.read()
            return cls._parse_kml_content(content)
        except CorruptFileError:
            raise
        except Exception as e:
            raise CorruptFileError(f"Error reading KML file: {str(e)}")

    @classmethod
    def parse_kmz_file(cls, kmz_path: Path) -> Tuple[List[ParsedFeature], str, str]:
        """Parse a compressed KMZ archive by reading its contained KML document."""
        if not zipfile.is_zipfile(kmz_path):
            raise CorruptFileError("Uploaded .kmz file is not a valid zip archive.")

        with zipfile.ZipFile(kmz_path, "r") as zf:
            kml_candidates = [n for n in zf.namelist() if n.lower().endswith(".kml")]
            if not kml_candidates:
                raise CorruptFileError("No .kml document found inside the .kmz archive.")

            doc_kml = "doc.kml" if "doc.kml" in kml_candidates else kml_candidates[0]
            content = zf.read(doc_kml)
            features, crs_str, _ = cls._parse_kml_content(content)
            return features, crs_str, "KMZ"

    @classmethod
    def _parse_kml_coordinates(cls, coord_text: str) -> List[Tuple[float, ...]]:
        """Parse space/newline-separated lon,lat,[alt] coordinate tuples from KML."""
        points: List[Tuple[float, ...]] = []
        if not coord_text:
            return points

        for token in coord_text.strip().split():
            parts = token.strip().split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    points.append((lon, lat))
                except ValueError:
                    continue
        return points

    @classmethod
    def _parse_kml_geometry_element(cls, parent_elem: ET.Element) -> Optional[BaseGeometry]:
        """Extract Shapely geometry from a KML XML element (Point, LineString, Polygon, MultiGeometry)."""
        # 1. Point
        pt_elem = parent_elem.find(".//Point/coordinates")
        if pt_elem is not None and pt_elem.text:
            coords = cls._parse_kml_coordinates(pt_elem.text)
            if coords:
                return Point(coords[0])

        # 2. Polygon
        poly_elem = parent_elem.find(".//Polygon")
        if poly_elem is not None:
            outer = poly_elem.find(".//outerBoundaryIs/LinearRing/coordinates")
            if outer is not None and outer.text:
                ext_coords = cls._parse_kml_coordinates(outer.text)
                if len(ext_coords) >= 3:
                    interiors = []
                    for inner in poly_elem.findall(".//innerBoundaryIs/LinearRing/coordinates"):
                        if inner.text:
                            in_coords = cls._parse_kml_coordinates(inner.text)
                            if len(in_coords) >= 3:
                                interiors.append(in_coords)
                    return Polygon(ext_coords, interiors)

        # 3. LineString
        ls_elem = parent_elem.find(".//LineString/coordinates")
        if ls_elem is not None and ls_elem.text:
            coords = cls._parse_kml_coordinates(ls_elem.text)
            if len(coords) >= 2:
                return LineString(coords)

        # 4. MultiGeometry
        mg_elem = parent_elem.find(".//MultiGeometry")
        if mg_elem is not None:
            sub_geoms: List[BaseGeometry] = []
            for child in mg_elem:
                sub_g = cls._parse_kml_geometry_element(child)
                if sub_g is not None and not sub_g.is_empty:
                    sub_geoms.append(sub_g)

            if sub_geoms:
                all_poly = all(isinstance(g, (Polygon, MultiPolygon)) for g in sub_geoms)
                all_lines = all(isinstance(g, (LineString, MultiLineString)) for g in sub_geoms)
                all_pts = all(isinstance(g, (Point, MultiPoint)) for g in sub_geoms)

                if all_poly:
                    polys = []
                    for g in sub_geoms:
                        if isinstance(g, Polygon):
                            polys.append(g)
                        elif isinstance(g, MultiPolygon):
                            polys.extend(g.geoms)
                    return MultiPolygon(polys)
                elif all_lines:
                    lines = []
                    for g in sub_geoms:
                        if isinstance(g, LineString):
                            lines.append(g)
                        elif isinstance(g, MultiLineString):
                            lines.extend(g.geoms)
                    return MultiLineString(lines)
                elif all_pts:
                    pts = []
                    for g in sub_geoms:
                        if isinstance(g, Point):
                            pts.append(g)
                        elif isinstance(g, MultiPoint):
                            pts.extend(g.geoms)
                    return MultiPoint(pts)
                else:
                    return GeometryCollection(sub_geoms)

        return None

    @classmethod
    def _parse_kml_content(cls, content_bytes: bytes) -> Tuple[List[ParsedFeature], str, str]:
        """Parse raw KML XML bytes into parsed features."""
        try:
            root = ET.fromstring(content_bytes)
        except Exception as e:
            raise CorruptFileError(f"Failed to parse KML XML document: {str(e)}")

        # Strip XML namespaces for robust xpath matching
        for elem in root.iter():
            if "}" in elem.tag:
                elem.tag = elem.tag.split("}", 1)[1]

        placemarks = root.findall(".//Placemark")
        if not placemarks:
            raise CorruptFileError("No <Placemark> features found in the KML file.")

        features: List[ParsedFeature] = []
        source_crs = "EPSG:4326"  # KML is natively WGS 84

        for idx, pm in enumerate(placemarks):
            pm_id = pm.get("id") or f"kml_{idx + 1}"
            props: Dict[str, Any] = {}

            name_elem = pm.find("name")
            if name_elem is not None and name_elem.text:
                props["name"] = name_elem.text.strip()

            desc_elem = pm.find("description")
            if desc_elem is not None and desc_elem.text:
                props["description"] = desc_elem.text.strip()

            # Parse ExtendedData elements
            for data in pm.findall(".//Data"):
                attr_name = data.get("name")
                val_elem = data.find("value")
                if attr_name and val_elem is not None and val_elem.text:
                    props[attr_name] = val_elem.text.strip()

            for sdata in pm.findall(".//SimpleData"):
                attr_name = sdata.get("name")
                if attr_name and sdata.text:
                    props[attr_name] = sdata.text.strip()

            geom = cls._parse_kml_geometry_element(pm)
            if geom is not None and not geom.is_empty:
                features.append(
                    ParsedFeature(
                        feature_index=idx,
                        feature_identifier=pm_id,
                        geometry=geom,
                        properties=props,
                        source_crs=source_crs,
                    )
                )

        if not features:
            raise CorruptFileError("Placemarks found in KML, but none contained valid coordinates or geometries.")

        return features, source_crs, "KML"

    # =========================================================================
    # GEOJSON PARSER (BONUS FORMAT)
    # =========================================================================
    @classmethod
    def parse_geojson_file(cls, geojson_path: Path) -> Tuple[List[ParsedFeature], str, str]:
        """Parse standard GeoJSON / JSON file."""
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_features = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
            source_crs = "EPSG:4326"

            # Check if crs member is defined
            crs_member = data.get("crs", {})
            if crs_member and isinstance(crs_member, dict):
                crs_props = crs_member.get("properties", {})
                crs_name = crs_props.get("name")
                if crs_name:
                    parsed_crs = CRSService.parse_crs(crs_name)
                    source_crs = CRSService.get_crs_auth_name(parsed_crs)

            features: List[ParsedFeature] = []
            for idx, f in enumerate(raw_features):
                geom_dict = f.get("geometry")
                if not geom_dict:
                    continue
                geom = shape(geom_dict)
                props = f.get("properties") or {}
                fid = str(f.get("id") or props.get("id") or f"geo_{idx}")

                features.append(
                    ParsedFeature(
                        feature_index=idx,
                        feature_identifier=fid,
                        geometry=geom,
                        properties=props,
                        source_crs=source_crs,
                    )
                )

            if not features:
                raise CorruptFileError("No valid geometries found in GeoJSON file.")

            return features, source_crs, "GEOJSON"

        except CorruptFileError:
            raise
        except Exception as e:
            raise CorruptFileError(f"Failed to parse GeoJSON file: {str(e)}")
