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

        this.map = L.map('circuit-map', {
            center: [45.6216, 45.6216],
            zoom: 15,
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

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(this.map);

        // V3: NO resize listeners, NO ResizeObserver
        // Map fills container via CSS only
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
        
        const coordinates = geometry.coordinates.map(coord => [coord[1], coord[0]]);

        // White circuit line
        this.circuitLine = L.polyline(coordinates, {
            color: '#ffffff',
            weight: 4,
            opacity: 0.8
        }).addTo(this.map);

        this.fitBoundsWithPadding(this.circuitLine.getBounds());

        // Red accent line
        L.polyline(coordinates, {
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
        if (car.state === 'BOX') {
            const marker = this.carMarkers.get(car.driver_number);
            if (marker) {
                this.map.removeLayer(marker);
                this.carMarkers.delete(car.driver_number);
            }
            return;
        }

        let marker = this.carMarkers.get(car.driver_number);
        if (!marker) {
            marker = this.createCarMarker(car);
            marker.addTo(this.map);
            this.carMarkers.set(car.driver_number, marker);
        } else {
            marker.setLatLng([car.position[1], car.position[0]]);
        }
    }

    removeAllCarMarkers() {
        this.carMarkers.forEach(marker => this.map.removeLayer(marker));
        this.carMarkers.clear();
    }

    fitBoundsWithPadding(bounds) {
        if (!this.map || !bounds) return;
        this.lastBounds = bounds;
        // Slightly tighten bounds so the circuit line occupies more of the canvas
        const tightenedBounds = bounds.pad(-0.08);
        // Shift circuit upward so it's visually centered above the dock
        this.map.fitBounds(tightenedBounds, { 
            paddingTopLeft: [20, 20],
            paddingBottomRight: [20, 130] 
        });
        const currentZoom = this.map.getZoom();
        if (typeof currentZoom === 'number') {
            console.debug('[MapV3] fitBounds zoom', currentZoom);
        }
        // Apply a deterministic zoom-out on the next frame to guarantee it runs after fitBounds
        requestAnimationFrame(() => {
            const latestZoom = this.map.getZoom();
            if (typeof latestZoom !== 'number') return;
            const adjustedZoom = latestZoom - 0.80;
            this.map.setZoom(adjustedZoom);
            console.debug('[MapV3] applied zoom offset', { previous: latestZoom, adjusted: adjustedZoom });
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
