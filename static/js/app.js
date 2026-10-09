// GeoMeasure API - Interactive GIS Map & Dashboard Application

let map = null;
let currentGeoJsonLayer = null;
let currentFileId = null;
let allMeasurements = [];

// Initialize DOM and Map on load
document.addEventListener('DOMContentLoaded', () => {
  initMap();
  setupEventListeners();
  fetchFilesList();
});

function initMap() {
  // Center roughly at default coordinates
  map = L.map('map').setView([20.5937, 78.9629], 5);

  // CartoDB Dark Matter Basemap
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(map);
}

function setupEventListeners() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const refreshBtn = document.getElementById('refresh-files-btn');
  const filterSelect = document.getElementById('filter-geom-type');
  const recenterBtn = document.getElementById('fit-bounds-btn');
  const downloadBtn = document.getElementById('download-geojson-btn');

  // Drag and drop
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });

  refreshBtn.addEventListener('click', fetchFilesList);

  filterSelect.addEventListener('change', (e) => {
    renderMeasurementsTable(e.target.value);
  });

  recenterBtn.addEventListener('click', () => {
    if (currentGeoJsonLayer && currentGeoJsonLayer.getLayers().length > 0) {
      map.fitBounds(currentGeoJsonLayer.getBounds(), { padding: [20, 20] });
    }
  });

  downloadBtn.addEventListener('click', () => {
    if (currentFileId) {
      window.open(`/api/files/${currentFileId}/geojson`, '_blank');
    }
  });
}

function showStatus(message, type = 'info') {
  const statusEl = document.getElementById('upload-status');
  statusEl.className = `status-box ${type}`;
  statusEl.textContent = message;
  statusEl.classList.remove('hidden');

  if (type === 'success') {
    setTimeout(() => {
      statusEl.classList.add('hidden');
    }, 4000);
  }
}

async function uploadFile(file) {
  showStatus(`Uploading and processing "${file.name}"...`, 'info');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/files/', {
      method: 'POST',
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Upload failed');
    }

    showStatus(`Successfully parsed ${data.feature_count} features from "${data.filename}"!`, 'success');
    await fetchFilesList();
    loadFileDetails(data.id);
  } catch (err) {
    showStatus(`Error: ${err.message}`, 'error');
  }
}

async function fetchFilesList() {
  try {
    const res = await fetch('/api/files/?limit=20');
    const data = await res.json();
    const listEl = document.getElementById('files-list');

    if (!data.items || data.items.length === 0) {
      listEl.innerHTML = '<div class="empty-state text-muted text-center py-4">No files uploaded yet. Upload a Shapefile (.zip) or .kml file above!</div>';
      return;
    }

    listEl.innerHTML = '';
    data.items.forEach((f) => {
      const item = document.createElement('div');
      item.className = `file-item ${f.id === currentFileId ? 'active' : ''}`;
      item.onclick = (e) => {
        if (!e.target.classList.contains('btn-delete-file')) {
          loadFileDetails(f.id);
        }
      };

      item.innerHTML = `
        <div class="file-item-info">
          <div class="file-item-title" title="${f.filename}">${f.filename}</div>
          <div class="file-item-sub">${f.feature_count} features • ${f.crs} • ${f.file_type || ''}</div>
        </div>
        <button class="btn-delete-file" title="Delete file" onclick="deleteFile('${f.id}', event)">✕</button>
      `;

      listEl.appendChild(item);
    });

    // Auto-select latest file if none selected
    if (!currentFileId && data.items.length > 0) {
      loadFileDetails(data.items[0].id);
    }
  } catch (err) {
    console.error('Error fetching file list:', err);
  }
}

async function deleteFile(fileId, event) {
  event.stopPropagation();
  if (!confirm('Are you sure you want to delete this dataset?')) return;

  try {
    const res = await fetch(`/api/files/${fileId}/`, { method: 'DELETE' });
    if (res.ok) {
      if (currentFileId === fileId) {
        currentFileId = null;
        clearDashboard();
      }
      fetchFilesList();
    }
  } catch (err) {
    alert('Failed to delete file');
  }
}

function clearDashboard() {
  if (currentGeoJsonLayer) {
    map.removeLayer(currentGeoJsonLayer);
    currentGeoJsonLayer = null;
  }
  document.getElementById('metric-dataset-name').textContent = 'None Selected';
  document.getElementById('metric-file-id').textContent = 'ID: -';
  document.getElementById('metric-feature-count').textContent = '0';
  document.getElementById('metric-geom-types').textContent = 'Types: -';
  document.getElementById('metric-total-area').textContent = '0 m²';
  document.getElementById('metric-area-hectares').textContent = '0.00 ha';
  document.getElementById('metric-total-length').textContent = '0 m';
  document.getElementById('metric-length-km').textContent = '0.00 km';
  document.getElementById('download-geojson-btn').disabled = true;
  document.getElementById('measurements-table-body').innerHTML = `
    <tr><td colspan="7" class="text-center text-muted py-4">Select or upload a dataset to view measurements.</td></tr>
  `;
}

async function loadFileDetails(fileId) {
  currentFileId = fileId;
  highlightActiveFile(fileId);

  try {
    // 1. Fetch file info
    const infoRes = await fetch(`/api/files/${fileId}/`);
    const fileInfo = await infoRes.json();

    // 2. Fetch measurements
    const measRes = await fetch(`/api/files/${fileId}/measurements/`);
    const measData = await measRes.json();
    allMeasurements = measData.features || [];

    // 3. Fetch GeoJSON for map display
    const geoRes = await fetch(`/api/files/${fileId}/geojson`);
    const geojsonData = await geoRes.json();

    // Update Metrics
    document.getElementById('metric-dataset-name').textContent = fileInfo.filename;
    document.getElementById('metric-file-id').textContent = `ID: ${fileInfo.id}`;
    document.getElementById('metric-feature-count').textContent = fileInfo.feature_count;

    const typeSummary = Object.entries(fileInfo.geometry_counts || {})
      .map(([k, v]) => `${k}: ${v}`)
      .join(', ');
    document.getElementById('metric-geom-types').textContent = typeSummary || 'N/A';

    document.getElementById('metric-total-area').textContent = `${fileInfo.total_area_sq_meters.toLocaleString()} m²`;
    const ha = (fileInfo.total_area_sq_meters * 0.0001).toFixed(2);
    document.getElementById('metric-area-hectares').textContent = `${ha} hectares`;

    document.getElementById('metric-total-length').textContent = `${fileInfo.total_length_meters.toLocaleString()} m`;
    const km = (fileInfo.total_length_meters * 0.001).toFixed(2);
    document.getElementById('metric-length-km').textContent = `${km} km`;

    document.getElementById('metric-crs').textContent = fileInfo.crs;

    document.getElementById('download-geojson-btn').disabled = false;

    // Render on Map
    renderGeoJsonOnMap(geojsonData);

    // Render Table
    renderMeasurementsTable();
  } catch (err) {
    console.error('Error loading file details:', err);
  }
}

function highlightActiveFile(fileId) {
  document.querySelectorAll('.file-item').forEach((item) => {
    item.classList.remove('active');
  });
  // Refresh file list item state
  fetchFilesList();
}

function renderGeoJsonOnMap(geojsonData) {
  if (currentGeoJsonLayer) {
    map.removeLayer(currentGeoJsonLayer);
  }

  currentGeoJsonLayer = L.geoJSON(geojsonData, {
    style: function (feature) {
      const type = feature.geometry.type;
      if (type.includes('Polygon')) {
        return {
          color: '#06b6d4',
          weight: 2,
          opacity: 0.9,
          fillColor: '#0891b2',
          fillOpacity: 0.35,
        };
      } else if (type.includes('Line')) {
        return {
          color: '#f59e0b',
          weight: 3.5,
          opacity: 0.9,
        };
      }
    },
    pointToLayer: function (feature, latlng) {
      return L.circleMarker(latlng, {
        radius: 6,
        fillColor: '#ec4899',
        color: '#be185d',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8,
      });
    },
    onEachFeature: function (feature, layer) {
      const p = feature.properties || {};
      let popupContent = `<div style="font-family: 'Inter', sans-serif; font-size: 13px;">`;
      popupContent += `<strong style="color: #06b6d4;">${p.feature_id || 'Feature'}</strong> (${p.geometry_type})<hr style="border: 0; border-top: 1px solid #ddd; margin: 6px 0;">`;

      if (p.measurement_type === 'area') {
        popupContent += `<div><b>Area:</b> ${p.measurement_area_sq_meters?.toLocaleString()} m² (${p.measurement_area_hectares} ha)</div>`;
        popupContent += `<div><b>Perimeter:</b> ${p.measurement_perimeter_meters?.toLocaleString()} m</div>`;
      } else if (p.measurement_type === 'length') {
        popupContent += `<div><b>Length:</b> ${p.measurement_length_meters?.toLocaleString()} m (${p.measurement_length_km} km)</div>`;
      } else if (p.status_message) {
        popupContent += `<div style="color: #666;"><i>${p.status_message}</i></div>`;
      }

      if (p.name) popupContent += `<div><b>Name:</b> ${p.name}</div>`;
      if (p.description) popupContent += `<div><b>Desc:</b> ${p.description}</div>`;

      popupContent += `</div>`;
      layer.bindPopup(popupContent);
    },
  }).addTo(map);

  // Zoom map to bounds
  if (currentGeoJsonLayer.getLayers().length > 0) {
    map.fitBounds(currentGeoJsonLayer.getBounds(), { padding: [30, 30] });
  }
}

function renderMeasurementsTable(filterType = '') {
  const tbody = document.getElementById('measurements-table-body');
  const filtered = filterType
    ? allMeasurements.filter((m) => m.geometry_type.toLowerCase().includes(filterType.toLowerCase()))
    : allMeasurements;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No features match the filter "${filterType}".</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((feat) => {
      const m = feat.measurement;
      let areaStr = '-';
      let lenStr = '-';

      if (m && m.type === 'area') {
        areaStr = `<span class="val-highlight">${m.area_sq_meters?.toLocaleString()} m²</span> <br><small class="text-muted">(${m.area_hectares} ha / ${m.area_acres} acres)</small>`;
        lenStr = `<small class="text-muted">Perimeter: ${m.perimeter_meters?.toLocaleString()} m</small>`;
      } else if (m && m.type === 'length') {
        lenStr = `<span class="val-length">${m.length_meters?.toLocaleString()} m</span> <br><small class="text-muted">(${m.length_km} km)</small>`;
      } else if (feat.status_message) {
        areaStr = `<small class="text-muted">${feat.status_message}</small>`;
      }

      const propsStr = Object.entries(feat.properties || {})
        .map(([k, v]) => `<code>${k}</code>: ${v}`)
        .join(', ');

      return `
        <tr>
          <td>#${feat.feature_index}</td>
          <td><b>${feat.feature_id}</b></td>
          <td><span class="badge ${feat.geometry_type.includes('Poly') ? 'badge-accent' : ''}">${feat.geometry_type}</span></td>
          <td>${areaStr}</td>
          <td>${lenStr}</td>
          <td><small class="text-muted">${feat.projected_crs || 'N/A'}</small></td>
          <td><small>${propsStr || 'None'}</small></td>
        </tr>
      `;
    })
    .join('');
}
