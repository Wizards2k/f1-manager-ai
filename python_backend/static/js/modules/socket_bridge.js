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

        const cars = data.cars || [];
        const playerCars = cars.filter(car => car.is_player_controlled);
        if (playerCars.length === 0) {
            console.warn('[SocketBridge] race_update received with no player cars. team=', this.state.getPlayerTeam?.());
        }

        const seenPlayerDrivers = new Set();
        cars.forEach(car => {
            if (car.is_player_controlled) {
                this.playerGarage.applyLocalCarState(car.driver_number, car);
                seenPlayerDrivers.add(car.driver_number);
                this.state.setPlayerCar(car);
                this.playerGarage.handleDriverFeedback(car);
            }
            this.mapModule.updateCarMarker(car);
        });

        this.state.prunePlayerCars(seenPlayerDrivers);
        this.timingPanel.render(cars);

        if (seenPlayerDrivers.size > 0) {
            this.playerGarage.render();
            this.playerGarage.updateDataChips();
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
            const playerCars = [];
            (cars || []).forEach(car => {
                if (car.is_player_controlled) {
                    this.playerGarage.applyLocalCarState(car.driver_number, car);
                    this.state.setPlayerCar(car);
                    playerCars.push(car);
                }
                this.mapModule.updateCarMarker(car);
            });
            this.timingPanel.render(cars || []);
            if (playerCars.length > 0) {
                this.playerGarage.render(true);
            }
        } catch (err) {
            console.error('Failed to load initial cars:', err);
        }
    }
}
