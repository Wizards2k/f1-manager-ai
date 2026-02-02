export class SocketBridge {
    constructor({ state, mapModule, timingPanel, playerGarage, sessionControls }) {
        this.state = state;
        this.mapModule = mapModule;
        this.timingPanel = timingPanel;
        this.playerGarage = playerGarage;
        this.sessionControls = sessionControls;
        this.socket = io();
        this.registerHandlers();
        this.bootstrap();
    }

    registerHandlers() {
        this.socket.on('race_update', (data) => this.handleRaceUpdate(data));
        this.socket.on('connect_error', (err) => console.error('Socket connection error:', err));
    }

    handleRaceUpdate(data = {}) {
        if (data.session_bests) {
            this.state.updateSessionBests(data.session_bests);
        }

        const seenPlayerDrivers = new Set();
        (data.cars || []).forEach(car => {
            if (car.is_player_controlled) {
                this.playerGarage.applyLocalCarState(car.driver_number, car);
                seenPlayerDrivers.add(car.driver_number);
                this.state.setPlayerCar(car);
            }
            this.mapModule.updateCarMarker(car);
        });

        this.state.prunePlayerCars(seenPlayerDrivers);
        this.timingPanel.render(data.cars || []);

        if (seenPlayerDrivers.size > 0) {
            this.playerGarage.render();
        }

        this.timingPanel.updateSessionTimer(data.session_time_remaining ?? null);

        if (this.sessionControls) {
            this.sessionControls.applyServerState({
                is_paused: data.is_paused,
                game_speed: data.game_speed
            });
        }
    }

    async bootstrap() {
        this.playerGarage.loadPlayerTeamInfo();

        try {
            const cars = await fetch('/api/cars').then(response => response.json());
            (cars || []).forEach(car => {
                if (car.is_player_controlled) {
                    this.state.setPlayerCar(car);
                }
                this.mapModule.updateCarMarker(car);
            });
            this.timingPanel.render(cars || []);
            this.playerGarage.render();
        } catch (err) {
            console.error('Failed to load initial cars:', err);
        }
    }
}
