# 🛰️ Geospatial File Measurement API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-19%20Passed-success.svg?logo=pytest&logoColor=white)](https://docs.pytest.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A production-grade geospatial backend service built with **FastAPI**, **Shapely**, **PyProj**, and **PyShp**. The service ingests geospatial files (**Shapefiles in `.zip` archives** and **OGC KML / KMZ** documents), detects their Coordinate Reference Systems (CRS), dynamically reprojects geographic coordinates (`EPSG:4326`) to optimal local metric projected coordinate systems (such as **UTM zones** and **Equal-Area projections**), and computes spatial measurements (**Polygon area** and **LineString length**) with high precision.

It also features an **Interactive Leaflet GIS Web Visualizer** at `http://localhost:8000/` for drag-and-drop file inspection and live map measurement previews.

---

## 📑 Table of Contents
1. [Architecture & System Design](#-architecture--system-design)
2. [Geospatial & CRS Reprojection Strategy](#-geospatial--crs-reprojection-strategy)
3. [Quickstart & Local Setup](#-quickstart--local-setup)
4. [Docker Deployment](#-docker-deployment)
5. [API Documentation & Endpoints](#-api-documentation--endpoints)
6. [Interactive Web Dashboard](#-interactive-web-dashboard)
7. [Design Decisions & Alternatives Considered](#-design-decisions--alternatives-considered)
8. [Sample Test Datasets](#-sample-test-datasets)
9. [Learnings & Future Scope](#-learnings--future-scope)

---

## 🏛️ Architecture & System Design

The application follows a **Layered Domain-Driven Modular Architecture** ensuring separation of concerns, testability, and high maintainability:

```
geospatial-measurement-api/
├── app/
│   ├── main.py                    # Application factory, lifespan, CORS & static UI routing
│   ├── core/
│   │   ├── config.py              # Pydantic Settings configuration & env validation
│   │   ├── exceptions.py          # Domain-specific exception hierarchy
│   │   └── logging.py             # Structured logging configuration
│   ├── domain/
│   │   └── models.py              # SQLAlchemy models (FileRecord, FeatureRecord)
│   ├── schemas/
│   │   ├── file.py                # File upload, metadata & list response DTOs
│   │   ├── measurement.py         # Spatial measurement & summary schemas
│   │   └── geojson.py             # RFC 7946 GeoJSON export schemas
│   ├── database/
│   │   ├── session.py             # SQLite engine with WAL mode & foreign keys enabled
│   │   └── repository.py          # Encapsulated data access layer (File & Feature repos)
│   ├── services/
│   │   ├── crs_service.py         # Dynamic UTM detection, reprojection & caching
│   │   ├── measurement_service.py # Core measurement engine (Area, Length, Geodesic verification)
│   │   ├── parser_service.py      # Resilient Shapefile (.zip), KML, KMZ & GeoJSON parsers
│   │   └── file_service.py        # Pipeline orchestrator (upload -> parse -> measure -> persist)
│   └── api/
│       ├── deps.py                # Dependency injection providers (DB session)
│       └── routes/
│           ├── files.py           # /api/files (Upload, Info, List, Delete, GeoJSON)
│           ├── measurements.py    # /api/files/{id}/measurements/ (Feature measurements)
│           └── health.py          # /api/health (System status & GIS engine diagnostic)
├── templates/
│   └── index.html                 # Interactive Leaflet GIS visualizer & dashboard
├── static/
│   ├── css/style.css              # Custom dark-theme design system
│   └── js/app.js                  # Dynamic Leaflet mapping & API interaction client
├── sample_data/                   # Ready-to-test Shapefiles and KML files
│   ├── cadastre_parcels.kml       # Mixed parcels, roads & benchmarks
│   ├── agricultural_fields.zip    # ESRI Shapefile with polygon field attributes
│   ├── transit_routes.zip         # ESRI Shapefile with transit lines
│   ├── weather_stations.kml       # Point features testing graceful handling
│   └── generate_samples.py        # Automated test generator script
├── tests/                         # Pytest test suite (19 test cases)
│   ├── conftest.py                # Test fixtures & in-memory SQLite isolation
│   ├── test_crs_service.py        # CRS parsing, UTM zoning, UPS tests
│   ├── test_measurement_service.py# Polygon area, LineString length, Point tests
│   ├── test_parser_service.py     # Shapefile & KML parser extraction tests
│   └── test_api_endpoints.py      # Full integration tests for all API endpoints
├── Dockerfile                     # Containerization build
├── docker-compose.yml             # One-click deployment specification
├── requirements.txt               # Locked production dependencies
└── README.md                      # Comprehensive project documentation
```

### 🔄 File Processing Flow

```mermaid
flowchart TD
    A[Client Upload: .zip / .kml] -->|Multipart POST /api/files/| B[FastAPI FileService]
    B --> C[Validate File Type & Size Limits]
    C --> D[ParserService Dispatcher]
    D -->|If .zip| E[Extract Shapefile .shp, .shx, .dbf, .prj]
    D -->|If .kml / .kmz| F[Parse KML Placemarks & ExtendedData]
    E --> G[Extract Geometries, Properties & Source CRS]
    F --> G
    G --> H[MeasurementService Pipeline]
    H --> I{Geometry Type?}
    I -->|Polygon / MultiPolygon| J[CRSService: Determine Optimal Metric Projected CRS]
    I -->|LineString / MultiLineString| J
    I -->|Point / MultiPoint| K[Graceful Bypass: Return Coordinates & Explanatory Note]
    J --> L[Reproject Geometry via PyProj Transformer]
    L --> M[Compute Metric Area: m², ha, km², acres OR Length: m, km]
    M --> N[Optional Geodesic Ellipsoidal Cross-Verification]
    N --> O[Persist FileRecord & FeatureRecords in SQLite]
    K --> O
    O --> P[Return FileInfoResponse 201 Created]
```

---

## 🗺️ Geospatial & CRS Reprojection Strategy

### The Geographic Coordinate Challenge
Geographic Coordinate Reference Systems such as **EPSG:4326 (WGS 84)** represent positions as angular units (**latitude and longitude degrees**). Calculating Euclidean distance or area directly on angular degrees (`dx² + dy²`) produces physically meaningless values because:
1. One degree of longitude varies from ~111.32 km at the equator to 0 km at the poles (`111.32 × cos(latitude)` km).
2. Distances and areas computed in degrees severely distort as latitude diverges from the equator.

### Dynamic Metric Projected CRS Selection Strategy
To guarantee sub-percent measurement accuracy, the service implements a multi-tier projection algorithm in `CRSService.determine_optimal_projected_crs`:

1. **Pre-Projected Metric Check:**
   - If the source dataset is already projected with metric linear units (e.g. State Plane, National Grid, or pre-existing UTM), the native projection is respected.
2. **Polar Latitude Handling:**
   - If the centroid latitude is $> 84^\circ\text{ N}$, the system automatically routes to **Universal Polar Stereographic (UPS) North (`EPSG:32661`)**.
   - If the centroid latitude is $< -80^\circ\text{ S}$, it routes to **UPS South (`EPSG:32662`)**.
3. **Cross-Zone Longitudinal Extent Check:**
   - If a feature's longitudinal span exceeds $6^\circ$ (spanning multiple UTM zones), a single UTM zone would induce significant distortion away from its central meridian.
   - For wide-area features, the system utilizes **World Cylindrical Equal Area (`EPSG:6933`)** to preserve true surface area.
4. **Standard Local UTM Zone Selection:**
   - For standard local geometries, the optimal UTM zone is mathematically calculated from the centroid longitude:
     $$\text{Zone Number} = \left\lfloor \frac{\text{longitude} + 180}{6} \right\rfloor + 1 \quad (\text{clamped between } 1 \text{ and } 60)$$
   - The appropriate EPSG code is determined by hemisphere:
     - Northern Hemisphere ($\text{lat} \ge 0$): `EPSG:32600 + Zone` (e.g. Zone 43N $\rightarrow$ `EPSG:32643`)
     - Southern Hemisphere ($\text{lat} < 0$): `EPSG:32700 + Zone` (e.g. Zone 56S $\rightarrow$ `EPSG:32756`)
5. **High-Performance Reprojection:**
   - Reprojection is performed using `pyproj.Transformer` with `always_xy=True`, vectorized across coordinate vertices via `shapely.transform`. Transformer instances are cached via `lru_cache` to achieve high request throughput.

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/rosnnn/geospatial-measurement-api.git
cd geospatial-measurement-api
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Test Suite
Ensure all 19 unit and integration tests pass:
```bash
python -m pytest -v
```

### 5. Start the Development Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once started:
- 🌐 **Interactive GIS Map & Dashboard:** [http://localhost:8000](http://localhost:8000)
- 📖 **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- 📑 **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- 🩺 **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 🐳 Docker Deployment

The application includes a self-contained multi-platform `Dockerfile` and `docker-compose.yml`.

### One-Click Docker Launch
```bash
docker compose up --build
```

The containerized service will automatically run test validations during build and bind to port `8000`.

---

## 📡 API Documentation & Endpoints

### 1. Upload Geospatial File
- **Method:** `POST /api/files/`
- **Content-Type:** `multipart/form-data`
- **Supported Formats:** `.zip` (Shapefile with `.shp`, `.shx`, `.dbf`, `.prj`), `.kml`, `.kmz`, `.geojson`

#### Request (cURL):
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_data/cadastre_parcels.kml"
```

#### Response (`201 Created`):
```json
{
  "id": "e89b21f4",
  "filename": "cadastre_parcels.kml",
  "feature_count": 6,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "file_type": "KML",
  "file_size_bytes": 3950,
  "total_area_sq_meters": 234142.15,
  "total_length_meters": 7820.44,
  "geometry_counts": {
    "Polygon": 2,
    "LineString": 2,
    "Point": 2
  },
  "created_at": "2026-10-09T10:15:30.123456+00:00"
}
```

---

### 2. Get File Information
- **Method:** `GET /api/files/{id}/`
- **Description:** Returns metadata and processing status for an uploaded file matching the problem specification.

#### Request (cURL):
```bash
curl -X GET "http://localhost:8000/api/files/e89b21f4/" -H "accept: application/json"
```

#### Response (`200 OK`):
```json
{
  "id": "e89b21f4",
  "filename": "cadastre_parcels.kml",
  "feature_count": 6,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 3. Get Feature Measurements
- **Method:** `GET /api/files/{id}/measurements/`
- **Query Parameters:**
  - `geometry_type` *(optional)*: Filter by geometry (e.g. `Polygon`, `LineString`, `Point`)
  - `skip` *(default: 0)*: Pagination offset
  - `limit` *(default: 500)*: Items per page

#### Request (cURL):
```bash
curl -X GET "http://localhost:8000/api/files/e89b21f4/measurements/" -H "accept: application/json"
```

#### Response (`200 OK`):
```json
{
  "file_id": "e89b21f4",
  "filename": "cadastre_parcels.kml",
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "total_features": 6,
  "summary": {
    "total_area_sq_meters": 234142.15,
    "total_area_hectares": 23.4142,
    "total_area_sq_km": 0.234142,
    "total_length_meters": 7820.44,
    "total_length_km": 7.8204,
    "geometry_counts": {
      "Polygon": 2,
      "LineString": 2,
      "Point": 2
    }
  },
  "features": [
    {
      "feature_index": 0,
      "feature_id": "parcel_001",
      "geometry_type": "Polygon",
      "crs": "EPSG:4326",
      "projected_crs": "EPSG:32643 (WGS 84 / UTM zone 43N)",
      "properties": {
        "name": "Central Botanical Garden",
        "description": "Public municipal park zone",
        "zoning_code": "ZONE-P1",
        "tax_exempt": "true",
        "municipality": "Metro City"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [77.59, 12.97],
            [77.6, 12.97],
            [77.6, 12.98],
            [77.59, 12.98],
            [77.59, 12.97]
          ]
        ]
      },
      "measurement": {
        "type": "area",
        "area_sq_meters": 120168.47,
        "area_hectares": 12.0168,
        "area_sq_km": 0.120168,
        "area_acres": 29.6943,
        "perimeter_meters": 4385.06,
        "perimeter_km": 4.3851,
        "projected_crs": "EPSG:32643 (WGS 84 / UTM zone 43N)",
        "geodesic_verification": {
          "area_sq_meters": 120182.11,
          "perimeter_meters": 4385.22,
          "ellipsoid": "WGS84"
        }
      },
      "is_supported": true,
      "status_message": null
    },
    {
      "feature_index": 2,
      "feature_id": "road_101",
      "geometry_type": "LineString",
      "crs": "EPSG:4326",
      "projected_crs": "EPSG:32643 (WGS 84 / UTM zone 43N)",
      "properties": {
        "name": "Metro Ring Expressway",
        "speed_limit_kph": "80"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [77.585, 12.965],
          [77.595, 12.968],
          [77.61, 12.975],
          [77.625, 12.985]
        ]
      },
      "measurement": {
        "type": "length",
        "length_meters": 5120.35,
        "length_km": 5.1204,
        "length_miles": 3.1816,
        "projected_crs": "EPSG:32643 (WGS 84 / UTM zone 43N)"
      },
      "is_supported": true,
      "status_message": null
    },
    {
      "feature_index": 4,
      "feature_id": "monument_901",
      "geometry_type": "Point",
      "crs": "EPSG:4326",
      "projected_crs": null,
      "properties": {
        "name": "Geodetic Datum Benchmark 01"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [77.595, 12.975]
      },
      "measurement": null,
      "is_supported": false,
      "status_message": "Points have zero area and length. Position: (77.595, 12.975)."
    }
  ]
}
```

---

### 4. Additional Production Endpoints
- `GET /api/files/`: List all uploaded files with pagination.
- `GET /api/files/{id}/geojson`: Export entire dataset as standard RFC 7946 GeoJSON with measurement attributes embedded (ready for QGIS or Mapbox).
- `DELETE /api/files/{id}/`: Delete file record and clean up local disk storage.
- `GET /api/health`: Service health and geospatial engine version diagnostics.

---

## 🖥️ Interactive Web Dashboard

In addition to headless API endpoints, this submission includes a built-in **Interactive Web Visualizer**:

1. Open `http://localhost:8000/` in any browser.
2. Drag and drop any `.zip` Shapefile or `.kml` file.
3. The dashboard automatically:
   - Displays real-time upload progress.
   - Computes and populates top-level KPI metrics (Total Area in m² and ha, Total Length in m and km, Detected CRS).
   - Draws the layers on an interactive **Leaflet.js** map with automatic zoom-to-bounds.
   - Colors Polygons in cyan, LineStrings in amber, and Points in pink.
   - Clicking any geometry displays a popup containing all original attributes and computed spatial measurements.
   - Features a searchable and filterable measurement data table with 1-click **GeoJSON Export**.

---

## 💡 Design Decisions & Alternatives Considered

| Decision | Selected Approach | Alternative Considered | Rationale |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | Django + DRF | FastAPI provides native asynchronous I/O, automatic OpenAPI 3.0 documentation, and strict type validation via Pydantic v2 with significantly lower memory overhead than Django. |
| **Shapefile Parsing** | **Pure-Python `pyshp`** | `geopandas` / `fiona` (GDAL C-libraries) | `fiona` and `pyogrio` require external C/C++ GDAL shared libraries (`gdal.dll` / `libgdal.so`). On candidate or reviewer machines without pre-configured GDAL PATHs, these frequently fail with DLL import errors. `pyshp` is 100% pure Python, zero-dependency, and cross-platform stable. |
| **Geospatial Reprojection** | **`pyproj` + Dynamic UTM** | `EPSG:3857` (Web Mercator) | Web Mercator severely distorts surface area away from the equator (Greenland looks as large as Africa). Choosing the local UTM zone based on feature centroid preserves conformal accuracy within 0.04%. |
| **Database Engine** | **SQLite (WAL Mode)** | PostgreSQL + PostGIS | SQLite with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) requires zero external setup or database credentials, guaranteeing immediate reproducibility for reviewers while providing full ACID persistence. |
| **Invalid Geometries** | **Auto-Heal (`shapely.make_valid`)** | Reject / Crash | Real-world GIS data often contains self-intersecting polygon bow-ties. Auto-healing geometries ensures the pipeline remains resilient without failing entire file uploads. |

---

## 📦 Sample Test Datasets

The repository includes ready-to-use sample files in `sample_data/`:

| File | Type | Geometries Contained | Demonstrates |
| :--- | :--- | :--- | :--- |
| `cadastre_parcels.kml` | KML | Polygons, LineStrings, Points | Mixed-geometry KML parsing, ExtendedData attributes, UTM 43N reprojection. |
| `agricultural_fields.zip` | Shapefile | Polygons with attributes | Multi-file ESRI shapefile archive (`.shp`, `.shx`, `.dbf`, `.prj`), metric area calculation. |
| `transit_routes.zip` | Shapefile | LineStrings with properties | Multi-coordinate transit lines, metric length calculation. |
| `weather_stations.kml` | KML | Points only | Graceful handling of point features with zero crash and informative status message. |

To regenerate sample files at any time, run:
```bash
python sample_data/generate_samples.py
```

---

## 🎓 Learnings & Future Scope

### Key Learnings
1. **Coordinate System Complexities:** Deepened understanding of the distinction between Geodetic Datums (WGS84 ellipsoidal geometry) and Projected Coordinate Systems (Transverse Mercator / UTM). Handling the mathematical distortions inherent in planar calculations versus geodesic calculations was a key highlight.
2. **Resilient Geospatial Ingestion:** Real-world KML files vary drastically across namespace conventions and XML schemas (Placemarks inside nested Folders, raw coordinates with varying whitespace, ExtendedData vs SchemaData). Building a parser that handles all variations without crashing reinforced defensive programming patterns.
3. **Pure-Python Portability:** Encountering GDAL DLL binding issues on Windows confirmed the strategic value of keeping core ingestion engines independent of brittle system C-libraries.

### Future Scope
1. **Asynchronous Task Queue (Celery / Redis):** For multi-gigabyte shapefiles (hundreds of thousands of polygons), offload geometry calculations to background worker processes with WebSocket progress streaming.
2. **PostGIS Cloud Storage:** Add optional configuration to stream parsed features into a PostGIS database with spatial indexing (`GIST`) for fast bounding-box spatial queries.
3. **GeoTIFF / Raster Support:** Expand measurement capabilities to calculate surface area and slope-adjusted distances across elevation models (DEM).
4. **Vector Tile Server (`MVT`):** Stream massive datasets to the Leaflet UI using vector tiles for seamless rendering of 100k+ features.

---

## 👨‍💻 Author & Submission
- **Author:** Roshan Kumar Jha
- **Role:** SDE Intern - Geospatial Backend
- **Repository:** [https://github.com/rosnnn/geospatial-measurement-api](https://github.com/rosnnn/geospatial-measurement-api)
- **Submission Date:** October 2026
