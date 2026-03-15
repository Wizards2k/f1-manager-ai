/**
 * MapModuleV3 - Fixed layout, no dynamic resize
 * Map size controlled purely by CSS Grid
 */

export const DEFAULT_VISUAL_SPEED_MULT = 4;

export class MapModuleV3 {
    constructor(state = null) {
        this.state = state;
        const params = new URLSearchParams(window.location.search);
        this.selectedCircuit = params.get('circuit');
        this.state?.setCircuitId?.(this.selectedCircuit);
        if (this.selectedCircuit) {
            document.title = `F1 Manager AI - ${this.selectedCircuit}`;
        }

        this.mapContainer = document.getElementById('circuit-map');
        this.carMarkers = new Map();
        this.carDrivers = new Map();
        this.circuitLine = null;
        this.lastBounds = null;
        this.rotationAngle = 0;
        this.centerPoint = null;
        this.trackSamples = [];
        this.trackLengthMeters = 0;
        this.visualDriverEnabled = params.get('visual_driver') !== '0';
        this._animationFrameId = null;
        this._lastAnimationTs = null;
        this.isPaused = false;
        this.speedMultiplier = DEFAULT_VISUAL_SPEED_MULT;

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

        if (this.visualDriverEnabled) {
            this._startVisualLoop();
        }
    }

    syncClock(timestamp) {
        if (!Number.isFinite(timestamp)) {
            return;
        }
        this.lastStepTs = timestamp;
        if (!Number.isFinite(this.lastServerTs)) {
            this.lastServerTs = timestamp;
        }
        if (!Number.isFinite(this.prevServerTs)) {
            this.prevServerTs = timestamp;
        }
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
            this.state?.setCircuitId?.(this.selectedCircuit);
        }

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

MapModuleV3.prototype.setSpeedMultiplier = function(multiplier) {
    if (!this.visualDriverEnabled) {
        return;
    }
    const value = Number(multiplier);
    const sanitized = Number.isFinite(value)
        ? Math.max(0.25, Math.min(value, DEFAULT_VISUAL_SPEED_MULT * 8))
        : DEFAULT_VISUAL_SPEED_MULT;
    if (sanitized === this.speedMultiplier) {
        return;
    }
    this.speedMultiplier = sanitized;
    this.carDrivers.forEach(driver => driver?.setSpeedMultiplier?.(sanitized));
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
        this._buildTrackSamples(rotatedPoints);
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
        if (car.state === 'BOX' || car.is_on_track === false || !this.centerPoint) {
            const marker = this.carMarkers.get(car.driver_number);
            if (marker) {
                this.map.removeLayer(marker);
                this.carMarkers.delete(car.driver_number);
            }
            this.carDrivers.delete(car.driver_number);
            return;
        }

        if (!this.visualDriverEnabled || !this.trackSamples.length) {
            this._updateMarkerDirect(car);
            return;
        }

        const driver = this._ensureDriver(car);
        if (!driver) {
            return;
        }
        let projectedDistance = this._getTrackDistanceFromCar(car);
        if (!Number.isFinite(projectedDistance)) {
            projectedDistance = this._projectCarDistance(car);
        }
        if (!Number.isFinite(projectedDistance)) {
            return;
        }
        driver.ingestServerSample({
            projectedDistance,
            timestamp: performance.now(),
            lapCount: car.total_laps || 0,
            raw: car,
        });
    }

    removeAllCarMarkers() {
        this.carMarkers.forEach(marker => this.map.removeLayer(marker));
        this.carMarkers.clear();
        this.carDrivers.clear();
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

// ----------------------------
// Visual driver implementation
// ----------------------------

MapModuleV3.prototype._buildTrackSamples = function(rotatedPoints) {
    if (!rotatedPoints || !rotatedPoints.length) {
        this.trackSamples = [];
        this.trackLengthMeters = 0;
        return;
    }

    const samples = [];
    let cumulative = 0;
    for (let i = 0; i < rotatedPoints.length; i += 1) {
        if (i > 0) {
            const prev = rotatedPoints[i - 1];
            const curr = rotatedPoints[i];
            cumulative += Math.hypot(curr[0] - prev[0], curr[1] - prev[1]);
        }
        samples.push({
            distance: cumulative,
            rotX: rotatedPoints[i][0],
            rotY: rotatedPoints[i][1],
        });
    }
    // close loop
    if (rotatedPoints.length > 1) {
        const first = rotatedPoints[0];
        const last = rotatedPoints[rotatedPoints.length - 1];
        cumulative += Math.hypot(first[0] - last[0], first[1] - last[1]);
        samples.push({
            distance: cumulative,
            rotX: first[0],
            rotY: first[1],
        });
    }

    this.trackSamples = samples;
    this.trackLengthMeters = cumulative;
};

MapModuleV3.prototype._startVisualLoop = function() {
    if (this._animationFrameId) {
        cancelAnimationFrame(this._animationFrameId);
    }
    const loop = (ts) => {
        if (this.visualDriverEnabled) {
            this._stepVisualDrivers(ts || performance.now());
            this._animationFrameId = requestAnimationFrame(loop);
        }
    };
    this._animationFrameId = requestAnimationFrame(loop);
};

MapModuleV3.prototype._stepVisualDrivers = function(timestamp) {
    if (this.isPaused) {
        return;
    }
    this.carDrivers.forEach((driver, carId) => {
        const point = driver.step(timestamp);
        if (!point) {
            return;
        }
        this._setMarkerPosition(carId, [point.rotY, point.rotX], driver.rawCar);
    });
};

MapModuleV3.prototype.setPaused = function(paused) {
    if (!this.visualDriverEnabled) {
        return;
    }
    const newState = Boolean(paused);
    if (newState === this.isPaused) {
        return;
    }
    this.isPaused = newState;
    if (!newState) {
        const now = performance.now();
        this.carDrivers.forEach(driver => driver?.syncClock(now));
    }
};

MapModuleV3.prototype._updateMarkerDirect = function(car) {
    const [localX, localY] = this.gpsToMeters(
        car.position[0],
        car.position[1],
        this.centerPoint.lon,
        this.centerPoint.lat
    );
    const [rotX, rotY] = this.rotatePoint(localX, localY, this.rotationAngle);
    this._setMarkerPosition(car.driver_number, [rotY, rotX], car);
};

MapModuleV3.prototype._setMarkerPosition = function(carId, latLng, car) {
    let marker = this.carMarkers.get(carId);
    if (!marker) {
        marker = this.createCarMarker(car);
        marker.addTo(this.map);
        this.carMarkers.set(carId, marker);
    }
    marker.setLatLng(latLng);
};

MapModuleV3.prototype._ensureDriver = function(car) {
    let driver = this.carDrivers.get(car.driver_number);
    if (driver) {
        driver.rawCar = car;
        driver.setSpeedMultiplier?.(this.speedMultiplier);
        return driver;
    }
    if (!this.trackLengthMeters || !this.trackSamples.length) {
        return null;
    }
    driver = new VisualCarDriver(car, {
        track: this.trackSamples,
        trackLength: this.trackLengthMeters,
        getPointAtDistance: (distance) => this._getPointAtTrackDistance(distance),
        getBaselineSpeed: (distance) => this._getBaselineSpeed(distance),
        speedMultiplier: this.speedMultiplier,
        maxMultiplier: DEFAULT_VISUAL_SPEED_MULT * 8,
    });
    this.carDrivers.set(car.driver_number, driver);
    return driver;
};

MapModuleV3.prototype._projectCarDistance = function(car) {
    const [localX, localY] = this.gpsToMeters(
        car.position[0],
        car.position[1],
        this.centerPoint.lon,
        this.centerPoint.lat
    );
    const [rotX, rotY] = this.rotatePoint(localX, localY, this.rotationAngle);
    let closest = null;
    let bestDist = Infinity;
    for (let i = 0; i < this.trackSamples.length; i += 1) {
        const sample = this.trackSamples[i];
        const dist = Math.hypot(sample.rotX - rotX, sample.rotY - rotY);
        if (dist < bestDist) {
            bestDist = dist;
            closest = sample;
        }
    }
    return closest ? closest.distance : null;
};

MapModuleV3.prototype._getTrackDistanceFromCar = function(car) {
    if (!car) {
        return null;
    }
    const lapDistance = Number(car.distance_traveled_m ?? car.distance_traveled ?? null);
    if (Number.isFinite(lapDistance) && this.trackLengthMeters > 0) {
        return lapDistance;
    }
    return null;
};

MapModuleV3.prototype._getPointAtTrackDistance = function(distance) {
    if (!this.trackSamples.length) {
        return null;
    }
    let normalized = distance;
    const total = this.trackLengthMeters || 1;
    normalized = ((normalized % total) + total) % total;
    for (let i = 1; i < this.trackSamples.length; i += 1) {
        const prev = this.trackSamples[i - 1];
        const next = this.trackSamples[i];
        if (normalized <= next.distance) {
            const span = Math.max(next.distance - prev.distance, 1e-6);
            const t = (normalized - prev.distance) / span;
            return {
                rotX: prev.rotX + (next.rotX - prev.rotX) * t,
                rotY: prev.rotY + (next.rotY - prev.rotY) * t,
            };
        }
    }
    const first = this.trackSamples[0];
    return { rotX: first.rotX, rotY: first.rotY };
};

MapModuleV3.prototype._getBaselineSpeed = function(distance) {
    // baseline 75 m/s (~270 km/h), modulated by simple sine to avoid flat speed
    const base = 75;
    const variance = Math.sin((distance / (this.trackLengthMeters || 1)) * Math.PI * 2) * 10;
    return Math.max(40, base + variance);
};

class VisualCarDriver {
    constructor(car, options) {
        this.rawCar = car;
        this.trackLength = Math.max(options.trackLength || 0, 1);
        this.getPointAtDistance = options.getPointAtDistance;
        this.getBaselineSpeed = options.getBaselineSpeed;
        this.displayDistance = 0;
        this.displaySpeed = 70; // m/s ~250 km/h
        this.serverAbsDistance = null;
        this.lastServerAbsDistance = null;
        this.prevServerTs = null;
        this.lastServerTs = null;
        this.lastStepTs = performance.now();
        this.maxMultiplier = Math.max(0.25, options.maxMultiplier || (DEFAULT_VISUAL_SPEED_MULT * 8));
        this.baseMaxSpeed = 110;
        this.config = {
            maxSpeed: this.baseMaxSpeed,
            minSpeed: 25,  // 90 km/h
            correctionGain: 0.12,
        };
        this.speedMultiplier = this._sanitizeMultiplier(options.speedMultiplier || 1);
        this.config.maxSpeed = this.baseMaxSpeed * this.speedMultiplier;
    }

    _sanitizeMultiplier(value) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) {
            return 1;
        }
        return Math.max(0.25, Math.min(numeric, this.maxMultiplier));
    }

    setSpeedMultiplier(multiplier) {
        const sanitized = this._sanitizeMultiplier(multiplier);
        if (sanitized === this.speedMultiplier) {
            return;
        }
        this.speedMultiplier = sanitized;
        this.config.maxSpeed = this.baseMaxSpeed * this.speedMultiplier;
    }

    ingestServerSample(sample) {
        if (!Number.isFinite(sample.projectedDistance)) {
            return;
        }
        const projectedDistance = sample.projectedDistance;
        const timestamp = sample.timestamp || performance.now();

        if (this.serverAbsDistance == null) {
            this.serverAbsDistance = projectedDistance;
            this.displayDistance = projectedDistance;
            this.displaySpeed = this.getBaselineSpeed(projectedDistance);
            this.lastServerAbsDistance = this.serverAbsDistance;
            this.prevServerTs = timestamp;
            this.lastServerTs = timestamp;
            this.lastStepTs = timestamp;
            return;
        }

        const prevWrapped = this.serverAbsDistance % this.trackLength;
        const half = this.trackLength / 2;
        let adjusted = projectedDistance;
        if ((adjusted - prevWrapped) > half) {
            adjusted -= this.trackLength;
        } else if ((adjusted - prevWrapped) < -half) {
            adjusted += this.trackLength;
        }

        this.lastServerAbsDistance = this.serverAbsDistance;
        this.serverAbsDistance += adjusted - prevWrapped;
        this.prevServerTs = this.lastServerTs;
        this.lastServerTs = timestamp;
    }

    step(timestamp) {
        if (this.serverAbsDistance == null) {
            return null;
        }

        if (!Number.isFinite(this.lastStepTs)) {
            this.lastStepTs = timestamp;
        }

        const dtSeconds = Math.max(0.001, Math.min((timestamp - this.lastStepTs) / 1000, 0.2));
        this.lastStepTs = timestamp;

        const baselineSpeed = this.getBaselineSpeed(this.displayDistance) * this.speedMultiplier;
        const serverSpeed = this._estimateServerSpeed();
        const desiredSpeed = Math.max(baselineSpeed, serverSpeed);

        const speedApproach = desiredSpeed - this.displaySpeed;
        this.displaySpeed += speedApproach * 0.2;
        this.displaySpeed = Math.min(this.config.maxSpeed, Math.max(this.config.minSpeed, this.displaySpeed));

        const error = this.serverAbsDistance - this.displayDistance;
        if (error >= 0) {
            const correction = Math.min(error, 60) * this.config.correctionGain;
            this.displayDistance += this.displaySpeed * dtSeconds + correction;
        } else {
            const slowDown = Math.min(Math.abs(error), 60) * 0.05;
            this.displaySpeed = Math.max(this.config.minSpeed, this.displaySpeed - slowDown);
            this.displayDistance += this.displaySpeed * dtSeconds;
        }

        return this.getPointAtDistance(this.displayDistance);
    }

    _estimateServerSpeed() {
        if (
            !Number.isFinite(this.lastServerAbsDistance) ||
            !Number.isFinite(this.serverAbsDistance) ||
            !Number.isFinite(this.lastServerTs) ||
            !Number.isFinite(this.prevServerTs) ||
            this.lastServerTs <= this.prevServerTs
        ) {
            return 0;
        }
        const delta = this.serverAbsDistance - this.lastServerAbsDistance;
        const dtSeconds = (this.lastServerTs - this.prevServerTs) / 1000;
        if (dtSeconds <= 0.05 || dtSeconds > 2) {
            return 0;
        }
        const rawSpeed = delta / dtSeconds;
        if (!Number.isFinite(rawSpeed) || rawSpeed <= 0) {
            return 0;
        }
        return Math.min(this.config.maxSpeed, Math.max(this.config.minSpeed, rawSpeed));
    }
}
