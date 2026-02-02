export class MapModule {
    constructor(state) {
        this.state = state;
        const params = new URLSearchParams(window.location.search);
        this.selectedCircuit = params.get('circuit');
        if (this.selectedCircuit) {
            document.title = `F1 Manager AI - ${this.selectedCircuit}`;
        }

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

        this.map.fitBounds(circuitLine.getBounds(), { padding: [20, 20] });

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
}
