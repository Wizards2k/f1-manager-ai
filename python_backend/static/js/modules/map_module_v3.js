/**
 * MapModuleV3 - Fixed layout, no dynamic resize
 * Map size controlled purely by CSS Grid
 */

export class MapModuleV3 {
    constructor(state = null) {
        this.state = state;
        const params = new URLSearchParams(window.location.search);
        this.selectedCircuit = params.get('circuit');
        if (this.selectedCircuit) {
            document.title = `F1 Manager AI - ${this.selectedCircuit}`;
        }

        this.mapContainer = document.getElementById('circuit-map');
        this.carMarkers = new Map();
        this.circuitLine = null;
        this.lastBounds = null;
        this.rotationAngle = 0;
        this.centerPoint = null;

        this.map = L.map('circuit-map', {
            crs: L.CRS.Simple,
            center: [0, 0],
            zoom: 1,
            minZoom: -20,
            zoomControl: false,
            dragging: false,
            touchZoom: false,
            doubleClickZoom: false,
            scrollWheelZoom: false,
            boxZoom: false,
            keyboard: false,
            tap: false,
            zoomSnap: 0,
            zoomDelta: 0.25,
        });

        // Background is now handled by CSS (transparent/dark)
        // V3: NO resize listeners, NO ResizeObserver
        // Map fills container via CSS only
    }

    // Helper to project GPS to local meters (approximate equirectangular)
    gpsToMeters(lon, lat, centerLon, centerLat) {
        const R = 6371000; // Earth radius in meters
        const rad = Math.PI / 180;
        const x = R * (lon - centerLon) * rad * Math.cos(centerLat * rad);
        const y = R * (lat - centerLat) * rad;
        return [x, y];
    }

    // Rotate point [x, y] around origin [0, 0] by angle (radians)
    rotatePoint(x, y, angle) {
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        return [
            x * cos - y * sin,
            x * sin + y * cos
        ];
    }

    async loadCircuitGeometry() {
        const circuitQuery = this.selectedCircuit 
            ? `?circuit=${encodeURIComponent(this.selectedCircuit)}` 
            : '';

        if (this.selectedCircuit) {
            try {
                await fetch('/api/load_circuit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ circuit_id: this.selectedCircuit })
                });
            } catch (err) {
                console.error('[MapV3] Failed to set circuit on backend', err);
            }
        }

        const response = await fetch(`/api/circuit${circuitQuery}`);
        const data = await response.json();
        
        const geometry = data.type === 'FeatureCollection'
            ? data.features?.[0]?.geometry
            : data.geometry;
            
        if (!geometry || !geometry.coordinates) {
            throw new Error('Circuit geometry not available');
        }
        
        // 1. Find center of bounding box to use as origin
        let minLon = Infinity, maxLon = -Infinity;
        let minLat = Infinity, maxLat = -Infinity;
        
        geometry.coordinates.forEach(coord => {
            const [lon, lat] = coord;
            if (lon < minLon) minLon = lon;
            if (lon > maxLon) maxLon = lon;
            if (lat < minLat) minLat = lat;
            if (lat > maxLat) maxLat = lat;
        });

        this.centerPoint = {
            lon: (minLon + maxLon) / 2,
            lat: (minLat + maxLat) / 2
        };

        // 2. Convert to local Cartesian coordinates (meters)
        const localPoints = geometry.coordinates.map(coord => 
            this.gpsToMeters(coord[0], coord[1], this.centerPoint.lon, this.centerPoint.lat)
        );

        // 3. Find the longest axis to determine rotation angle
        let maxDistSq = 0;
        let furthestPair = [localPoints[0], localPoints[0]];

        const step = Math.max(1, Math.floor(localPoints.length / 100));
        for (let i = 0; i < localPoints.length; i += step) {
            for (let j = i + 1; j < localPoints.length; j += step) {
                const dx = localPoints[i][0] - localPoints[j][0];
                const dy = localPoints[i][1] - localPoints[j][1];
                const distSq = dx * dx + dy * dy;
                if (distSq > maxDistSq) {
                    maxDistSq = distSq;
                    furthestPair = [localPoints[i], localPoints[j]];
                }
            }
        }

        const dx = furthestPair[1][0] - furthestPair[0][0];
        const dy = furthestPair[1][1] - furthestPair[0][1];
        let axisAngle = Math.atan2(dy, dx);
        
        // Normalize angle to be between -PI/2 and PI/2 to prevent 180-degree upside-down flips
        if (axisAngle > Math.PI / 2) axisAngle -= Math.PI;
        if (axisAngle < -Math.PI / 2) axisAngle += Math.PI;
        
        // Force perfect horizontal alignment to maximize space usage
        this.rotationAngle = -axisAngle;

        // 4. Rotate all points
        const rotatedPoints = localPoints.map(p => this.rotatePoint(p[0], p[1], this.rotationAngle));

        // Leaflet expects [y, x] for its LatLng representation even in CRS.Simple
        const leafletCoords = rotatedPoints.map(p => [p[1], p[0]]);

        // White circuit line
        this.circuitLine = L.polyline(leafletCoords, {
            color: '#ffffff',
            weight: 4,
            opacity: 0.8
        }).addTo(this.map);

        this.fitBoundsWithPadding(this.circuitLine.getBounds());

        // Red accent line
        L.polyline(leafletCoords, {
            color: '#e10600',
            weight: 6,
            opacity: 0.3
        }).addTo(this.map);
    }

    createCarMarker(car) {
        const icon = L.divIcon({
            className: 'car-marker',
            html: `<div style="
                background: ${car.team_color};
                width: 20px;
                height: 20px;
                border-radius: 50%;
                border: 2px solid white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 10px;
                color: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            ">${car.driver_number}</div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });
        return L.marker([car.position[1], car.position[0]], { icon });
    }

    updateCarMarker(car) {
        if (car.state === 'BOX' || !this.centerPoint) {
            const marker = this.carMarkers.get(car.driver_number);
            if (marker) {
                this.map.removeLayer(marker);
                this.carMarkers.delete(car.driver_number);
            }
            return;
        }

        // 1. Convert GPS to local Cartesian
        const [localX, localY] = this.gpsToMeters(
            car.position[0], 
            car.position[1], 
            this.centerPoint.lon, 
            this.centerPoint.lat
        );

        // 2. Rotate to match circuit
        const [rotX, rotY] = this.rotatePoint(localX, localY, this.rotationAngle);

        // 3. Update marker (Leaflet expects [y, x])
        const latLng = [rotY, rotX];

        let marker = this.carMarkers.get(car.driver_number);
        if (!marker) {
            marker = this.createCarMarker(car);
            marker.setLatLng(latLng);
            marker.addTo(this.map);
            this.carMarkers.set(car.driver_number, marker);
        } else {
            marker.setLatLng(latLng);
        }
    }

    removeAllCarMarkers() {
        this.carMarkers.forEach(marker => this.map.removeLayer(marker));
        this.carMarkers.clear();
    }

    fitBoundsWithPadding(bounds) {
        if (!this.map || !bounds) return;
        this.lastBounds = bounds;
        
        // Let Leaflet handle the exact centering and zooming using only pixel padding.
        // paddingTopLeft: [left, top] padding in pixels
        // paddingBottomRight: [right, bottom] padding in pixels
        // We leave 280px at the bottom for the player docks (which are 265px + margins)
        this.map.fitBounds(bounds, { 
            paddingTopLeft: [50, 50],
            paddingBottomRight: [50, 280]
        });
    }

    setZoom(zoom) {
        if (!this.map) return;
        this.map.setZoom(zoom);
    }

    getMap() {
        return this.map;
    }

    // V3: NO onSetupOverlayToggled - no resize needed
    // V3: NO updateMapHeight - CSS Grid handles sizing
    // V3: NO invalidateSize calls
}
