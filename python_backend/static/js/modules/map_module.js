export class MapModule {
    constructor(state) {
        this.state = state;
        const params = new URLSearchParams(window.location.search);
        this.selectedCircuit = params.get('circuit');
        if (this.selectedCircuit) {
            document.title = `F1 Manager AI - ${this.selectedCircuit}`;
        }

        this.mapContainer = document.getElementById('circuit-map');
        this.dockElement = document.getElementById('player-dock');
        this.circuitContainer = this.mapContainer ? this.mapContainer.parentElement : null;
        this.currentMapHeight = 0;
        this.currentDockHeight = 0;
        this.lastBounds = null;
        this.mapReady = false;

        this.updateMapHeight = this.updateMapHeight.bind(this);
        this.circuitContainer?.style.setProperty('--dock-height', '340px');
        this.updateMapHeight(false);

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
            tap: false
        });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: ' OpenStreetMap contributors  CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(this.map);

        window.addEventListener('resize', this.updateMapHeight);
        if (window.ResizeObserver && this.dockElement) {
            this.dockObserver = new ResizeObserver(this.updateMapHeight);
            this.dockObserver.observe(this.dockElement);
        }
        this.mapReady = true;
        requestAnimationFrame(this.updateMapHeight);
    }

    async loadCircuitGeometry() {
        const circuitQuery = this.selectedCircuit ? `?circuit=${encodeURIComponent(this.selectedCircuit)}` : '';

        if (this.selectedCircuit) {
            try {
                await fetch('/api/load_circuit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ circuit_id: this.selectedCircuit })
                });
            } catch (err) {
                console.error('Failed to set circuit on backend', err);
            }
        }

        const data = await fetch(`/api/circuit${circuitQuery}`).then(response => response.json());
        const geometry = data.type === 'FeatureCollection'
            ? data.features?.[0]?.geometry
            : data.geometry;
        if (!geometry || !geometry.coordinates) {
            throw new Error('Circuit geometry not available');
        }
        const coordinates = geometry.coordinates.map(coord => [coord[1], coord[0]]);

        const circuitLine = L.polyline(coordinates, {
            color: '#ffffff',
            weight: 4,
            opacity: 0.8
        }).addTo(this.map);

        this.fitBoundsWithPadding(circuitLine.getBounds());

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
            this.state.removeCarMarker(car.driver_number);
            return;
        }

        let marker = this.state.getCarMarker(car.driver_number);
        if (!marker) {
            marker = this.createCarMarker(car);
            marker.addTo(this.map);
            this.state.setCarMarker(car.driver_number, marker);
        } else {
            marker.setLatLng([car.position[1], car.position[0]]);
        }
    }

    fitBoundsWithPadding(bounds) {
        if (!this.map) return;
        this.lastBounds = bounds;
        // Use uniform padding that works for both horizontal and vertical circuits
        this.map.fitBounds(bounds, { padding: [40, 40] });
    }

    updateMapHeight(allowRefit = true) {
        if (!this.mapContainer || !this.circuitContainer) return;
        const containerHeight = this.circuitContainer.getBoundingClientRect().height;
        const dockHeight = this.dockElement ? this.dockElement.getBoundingClientRect().height : 0;
        const nextHeight = Math.max(320, containerHeight - dockHeight);
        if (Math.abs(nextHeight - this.currentMapHeight) < 1) return;
        this.currentMapHeight = nextHeight;
        this.currentDockHeight = dockHeight;
        this.circuitContainer.style.setProperty('--dock-height', `${dockHeight}px`);
        this.mapContainer.style.height = `${nextHeight}px`;
        if (!this.mapReady || !this.map) return;
        this.map.invalidateSize();
        if (allowRefit && this.lastBounds) {
            this.fitBoundsWithPadding(this.lastBounds);
        }
    }
}
