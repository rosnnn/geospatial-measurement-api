import os
from pathlib import Path
import zipfile
import shapefile

SAMPLE_DIR = Path(__file__).resolve().parent


def generate_cadastre_kml():
    """Generates a rich KML file with Polygons, LineStrings, and Points."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Metropolitan Cadastral Survey 2026</name>
    <description>Sample dataset containing urban parcels, road network, and survey monuments.</description>
    
    <!-- Polygon 1: Central Botanical Garden -->
    <Placemark id="parcel_001">
      <name>Central Botanical Garden</name>
      <description>Public municipal park zone</description>
      <ExtendedData>
        <Data name="zoning_code"><value>ZONE-P1</value></Data>
        <Data name="tax_exempt"><value>true</value></Data>
        <Data name="municipality"><value>Metro City</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.6000,12.9700,0
              77.6000,12.9800,0
              77.5900,12.9800,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- Polygon 2: Tech Innovation Campus -->
    <Placemark id="parcel_002">
      <name>Tech Innovation Campus</name>
      <description>Commercial IT sector complex</description>
      <ExtendedData>
        <Data name="zoning_code"><value>COM-IT</value></Data>
        <Data name="occupancy_rate"><value>94.2</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.6050,12.9720,0
              77.6150,12.9720,0
              77.6180,12.9790,0
              77.6070,12.9810,0
              77.6050,12.9720,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- LineString 1: Metro Ring Expressway -->
    <Placemark id="road_101">
      <name>Metro Ring Expressway</name>
      <description>6-lane primary urban arterial highway</description>
      <ExtendedData>
        <Data name="surface_type"><value>Asphalt</value></Data>
        <Data name="lanes"><value>6</value></Data>
        <Data name="speed_limit_kph"><value>80</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5850,12.9650,0
          77.5950,12.9680,0
          77.6100,12.9750,0
          77.6250,12.9850,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- LineString 2: Riverside Greenway Trail -->
    <Placemark id="trail_202">
      <name>Riverside Greenway Trail</name>
      <description>Pedestrian and bicycle recreational trail</description>
      <ExtendedData>
        <Data name="surface_type"><value>Paved Gravel</value></Data>
        <Data name="grade"><value>Class A</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.5880,12.9690,0
          77.5920,12.9730,0
          77.5980,12.9770,0
          77.6040,12.9820,0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Point 1: Geodetic Datum Station 01 -->
    <Placemark id="monument_901">
      <name>Geodetic Datum Benchmark 01</name>
      <description>Primary brass benchmark marker</description>
      <ExtendedData>
        <Data name="elevation_msl_m"><value>920.45</value></Data>
        <Data name="accuracy"><value>Sub-Centimeter</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.5950,12.9750,920.45</coordinates>
      </Point>
    </Placemark>

    <!-- Point 2: Geodetic Datum Station 02 -->
    <Placemark id="monument_902">
      <name>Geodetic Datum Benchmark 02</name>
      <description>Secondary triangulation monument</description>
      <ExtendedData>
        <Data name="elevation_msl_m"><value>915.12</value></Data>
        <Data name="accuracy"><value>Sub-Centimeter</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.6120,12.9800,915.12</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    dest = SAMPLE_DIR / "cadastre_parcels.kml"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Generated: {dest}")


def generate_agricultural_shapefile_zip():
    """Generates an ESRI Shapefile .zip package with polygon agricultural plots and EPSG:4326 PRJ."""
    base_name = SAMPLE_DIR / "temp_fields"
    w = shapefile.Writer(str(base_name))
    w.field("field_id", "C", size=20)
    w.field("crop_type", "C", size=30)
    w.field("soil_ph", "N", decimal=1)
    w.field("irrigated", "C", size=5)

    # Plot 1: Wheat Field
    w.poly([[[75.80, 26.85], [75.82, 26.85], [75.82, 26.87], [75.80, 26.87], [75.80, 26.85]]])
    w.record("FIELD-01", "Durum Wheat", 6.8, "YES")

    # Plot 2: Mustard Seed Field
    w.poly([[[75.83, 26.86], [75.85, 26.86], [75.86, 26.89], [75.84, 26.89], [75.83, 26.86]]])
    w.record("FIELD-02", "Yellow Mustard", 7.2, "NO")

    # Plot 3: Barley Field
    w.poly([[[75.81, 26.88], [75.83, 26.88], [75.83, 26.90], [75.81, 26.90], [75.81, 26.88]]])
    w.record("FIELD-03", "Barley", 6.5, "YES")

    w.close()

    # Create WGS84 PRJ
    prj_content = (
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
    )
    prj_path = SAMPLE_DIR / "temp_fields.prj"
    with open(prj_path, "w", encoding="utf-8") as f:
        f.write(prj_content)

    # Zip files into agricultural_fields.zip
    zip_dest = SAMPLE_DIR / "agricultural_fields.zip"
    with zipfile.ZipFile(zip_dest, "w") as z:
        for ext in ["shp", "shx", "dbf", "prj"]:
            fn = SAMPLE_DIR / f"temp_fields.{ext}"
            if fn.exists():
                z.write(fn, arcname=f"agricultural_fields.{ext}")
                fn.unlink()

    print(f"Generated: {zip_dest}")


def generate_transit_shapefile_zip():
    """Generates an ESRI Shapefile .zip package with LineString transit routes."""
    base_name = SAMPLE_DIR / "temp_transit"
    w = shapefile.Writer(str(base_name))
    w.field("route_id", "C", size=20)
    w.field("line_name", "C", size=40)
    w.field("mode", "C", size=20)

    # Route 1
    w.line([[[77.55, 12.92], [77.58, 12.95], [77.62, 12.98], [77.66, 13.01]]])
    w.record("LINE-PURPLE", "East-West Metro Corridor", "METRO_RAIL")

    # Route 2
    w.line([[[77.56, 13.03], [77.58, 12.97], [77.60, 12.91], [77.61, 12.87]]])
    w.record("LINE-GREEN", "North-South Commuter Line", "COMMUTER_RAIL")

    w.close()

    prj_content = (
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
    )
    prj_path = SAMPLE_DIR / "temp_transit.prj"
    with open(prj_path, "w", encoding="utf-8") as f:
        f.write(prj_content)

    zip_dest = SAMPLE_DIR / "transit_routes.zip"
    with zipfile.ZipFile(zip_dest, "w") as z:
        for ext in ["shp", "shx", "dbf", "prj"]:
            fn = SAMPLE_DIR / f"temp_transit.{ext}"
            if fn.exists():
                z.write(fn, arcname=f"transit_routes.{ext}")
                fn.unlink()

    print(f"Generated: {zip_dest}")


def generate_points_kml():
    """Generates a KML with Points only to test graceful no-measurement handling."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Global Meteorological Stations</name>
    <Placemark id="station_delhi">
      <name>New Delhi Weather Observatory</name>
      <ExtendedData>
        <Data name="station_id"><value>DEL-01</value></Data>
        <Data name="temp_celsius"><value>28.4</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>77.2090,28.6139,216</coordinates>
      </Point>
    </Placemark>
    <Placemark id="station_mumbai">
      <name>Mumbai Coastal Station</name>
      <ExtendedData>
        <Data name="station_id"><value>BOM-02</value></Data>
        <Data name="humidity_pct"><value>82</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>72.8777,19.0760,14</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    dest = SAMPLE_DIR / "weather_stations.kml"
    with open(dest, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Generated: {dest}")


if __name__ == "__main__":
    generate_cadastre_kml()
    generate_agricultural_shapefile_zip()
    generate_transit_shapefile_zip()
    generate_points_kml()
    print("All sample datasets successfully generated!")
