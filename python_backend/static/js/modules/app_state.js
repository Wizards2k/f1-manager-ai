export class AppState {
    constructor() {
        const params = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
        this.sessionBests = {
            best_lap: null,
            best_sectors: { sector1: null, sector2: null, sector3: null }
        };
        this.carMarkers = new Map();
        this.playerCars = new Map();
        this.allCars = new Map();
        this.playerTeamId = null;
        this.timelineEvents = [];
        this.circuitId = params?.get('circuit') || null;
    }

    setCircuitId(circuitId) {
        this.circuitId = circuitId || null;
    }

    getCircuitId() {
        return this.circuitId;
    }

    updateSessionBests(bests) {
        if (!bests) return;
        this.sessionBests = {
            best_lap: bests.best_lap ?? null,
            best_sectors: {
                sector1: bests.best_sectors?.sector1 ?? null,
                sector2: bests.best_sectors?.sector2 ?? null,
                sector3: bests.best_sectors?.sector3 ?? null
            }
        };
    }

    setCarMarker(driverNumber, marker) {
        this.carMarkers.set(driverNumber, marker);
    }

    getCarMarker(driverNumber) {
        return this.carMarkers.get(driverNumber);
    }

    removeCarMarker(driverNumber) {
        const marker = this.carMarkers.get(driverNumber);
        if (marker) {
            marker.remove();
            this.carMarkers.delete(driverNumber);
        }
    }

    setPlayerTeam(teamId) {
        this.playerTeamId = teamId;
    }

    getPlayerTeam() {
        return this.playerTeamId;
    }

    setPlayerCar(car) {
        if (!car || !car.driver_number) return;
        const previous = this.playerCars.get(car.driver_number) || {};
        const merged = {
            ...previous,
            ...car,
            telemetry_rival_target: car.telemetry_rival_target ?? previous.telemetry_rival_target ?? '',
            telemetry_lap_selector: car.telemetry_lap_selector ?? previous.telemetry_lap_selector ?? 'best',
        };
        this.playerCars.set(car.driver_number, merged);
        this.allCars.set(car.driver_number, merged);
    }

    setCar(car) {
        if (!car || !car.driver_number) return;
        this.allCars.set(car.driver_number, car);
    }

    getCar(driverNumber) {
        return this.allCars.get(driverNumber);
    }

    getAllCarsSorted() {
        return [...this.allCars.values()].sort((a, b) => a.driver_number - b.driver_number);
    }

    getPlayerCar(driverNumber) {
        return this.playerCars.get(driverNumber);
    }

    removePlayerCar(driverNumber) {
        this.playerCars.delete(driverNumber);
    }

    getPlayerCarsSorted() {
        return [...this.playerCars.values()].sort((a, b) => a.driver_number - b.driver_number);
    }

    prunePlayerCars(seenDrivers = new Set()) {
        for (const driver of Array.from(this.playerCars.keys())) {
            if (!seenDrivers.has(driver)) {
                this.playerCars.delete(driver);
            }
        }
    }

    addTimelineEvent(event) {
        if (!event) return;
        this.timelineEvents.push(event);
        // Keep only the latest 100 events to avoid unbounded growth
        if (this.timelineEvents.length > 100) {
            this.timelineEvents.splice(0, this.timelineEvents.length - 100);
        }
    }

    getTimelineEvents() {
        return [...this.timelineEvents];
    }

    clearTimelineEvents() {
        this.timelineEvents.length = 0;
    }
}
