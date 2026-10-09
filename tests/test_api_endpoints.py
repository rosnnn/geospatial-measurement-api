from pathlib import Path
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "geospatial_engines" in data


def test_upload_and_measure_kml(client: TestClient, sample_kml_path: Path):
    # 1. Upload KML
    with open(sample_kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )
    assert response.status_code == 201
    file_data = response.json()

    # Verify fields match problem statement
    assert "id" in file_data
    assert file_data["filename"] == "cadastre_parcels.kml"
    assert file_data["feature_count"] == 6
    assert file_data["crs"] == "EPSG:4326"
    assert file_data["status"] == "COMPLETED"

    file_id = file_data["id"]

    # 2. GET /api/files/{id}/
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["filename"] == "cadastre_parcels.kml"
    assert info_data["feature_count"] == 6
    assert info_data["crs"] == "EPSG:4326"
    assert info_data["status"] == "COMPLETED"

    # 3. GET /api/files/{id}/measurements/
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["file_id"] == file_id
    assert meas_data["total_features"] == 6
    assert len(meas_data["features"]) == 6

    # Verify Polygons have area, LineStrings have length, Points have graceful note
    polygon_features = [f for f in meas_data["features"] if f["geometry_type"] == "Polygon"]
    assert len(polygon_features) == 2
    for pf in polygon_features:
        assert pf["measurement"] is not None
        assert pf["measurement"]["type"] == "area"
        assert pf["measurement"]["area_sq_meters"] > 0
        assert "UTM" in pf["projected_crs"]

    line_features = [f for f in meas_data["features"] if f["geometry_type"] == "LineString"]
    assert len(line_features) == 2
    for lf in line_features:
        assert lf["measurement"] is not None
        assert lf["measurement"]["type"] == "length"
        assert lf["measurement"]["length_meters"] > 0

    point_features = [f for f in meas_data["features"] if f["geometry_type"] == "Point"]
    assert len(point_features) == 2
    for ptf in point_features:
        assert ptf["measurement"] is None
        assert ptf["is_supported"] is False
        assert "Points have zero area and length" in ptf["status_message"]

    # 4. Filter by geometry_type
    poly_filter_res = client.get(f"/api/files/{file_id}/measurements/?geometry_type=Polygon")
    assert poly_filter_res.status_code == 200
    assert len(poly_filter_res.json()["features"]) == 2

    # 5. GET /api/files/{id}/geojson
    geo_res = client.get(f"/api/files/{file_id}/geojson")
    assert geo_res.status_code == 200
    geo_data = geo_res.json()
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) == 6


def test_upload_and_measure_shapefile_zip(client: TestClient, sample_shp_zip_path: Path):
    with open(sample_shp_zip_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_shp_zip_path.name, f, "application/zip")},
        )
    assert response.status_code == 201
    file_data = response.json()

    assert file_data["filename"] == "agricultural_fields.zip"
    assert file_data["feature_count"] == 3
    assert file_data["status"] == "COMPLETED"

    file_id = file_data["id"]
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert len(meas_data["features"]) == 3
    for f in meas_data["features"]:
        assert f["geometry_type"] == "Polygon"
        assert f["measurement"]["area_sq_meters"] > 0


def test_list_and_delete_files(client: TestClient, sample_kml_path: Path):
    # Upload
    with open(sample_kml_path, "rb") as f:
        upload_res = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = upload_res.json()["id"]

    # List
    list_res = client.get("/api/files/")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # Delete
    del_res = client.delete(f"/api/files/{file_id}/")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Confirm 404 after deletion
    get_res = client.get(f"/api/files/{file_id}/")
    assert get_res.status_code == 404


def test_invalid_extension_upload(client: TestClient):
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", b"plain text data", "text/plain")},
    )
    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_nonexistent_file_404(client: TestClient):
    response = client.get("/api/files/nonexistent_id_999/")
    assert response.status_code == 404
