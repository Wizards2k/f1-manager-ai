export class SocketBridge {
    constructor({ state, mapModule, timingPanel, playerGarage, sessionControls, timelinePanel }) {
        this.state = state;
        this.mapModule = mapModule;
        this.timingPanel = timingPanel;
        this.playerGarage = playerGarage;
        this.sessionControls = sessionControls;
        this.timelinePanel = timelinePanel;
        this.socket = io();
        this.registerHandlers();
        this.bootstrap();
    }

    registerHandlers() {
        this.socket.on('race_update', (data) => this.handleRaceUpdate(data));
        this.socket.on('event_feed', (events) => this.handleEventFeed(events));
        this.socket.on('connect_error', (err) => console.error('Socket connection error:', err));
        this.socket.on('tyre_inventory_update', (payload) => this.handleTyreInventoryUpdate(payload));
    }

    handleTyreInventoryUpdate(payload = {}) {
        const driverId = payload.driver_id || payload.car_id || null;
        const inventory = payload.inventory || null;
        if (!driverId || !inventory || !this.playerGarage?.primeTyreInventory) {
            return;
        }
        this.playerGarage.primeTyreInventory(driverId, inventory);
        this.playerGarage.render();
        this.playerGarage.updateDataChips?.();
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
            this.state.setCar?.(car);
            if (car.is_player_controlled) {
                // Clear pendingSend only when server confirms car is on track (no longer pending)
                const isOnTrack = car.is_on_track === true || (car.state && car.state !== 'BOX');
                if (isOnTrack && this.playerGarage.pendingSendDrivers.has(car.driver_number)) {
                    this.playerGarage.pendingSendDrivers.delete(car.driver_number);
                }
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

        if (data.session_flag) {
            this.timingPanel.updateFlag(data.session_flag);
        }

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
                this.state.setCar?.(car);
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

    handleEventFeed(events = []) {
        if (!Array.isArray(events) || events.length === 0) {
            return;
        }

        events.forEach((event) => {
            if (!event || typeof event !== 'object') {
                return;
            }

            this.state.addTimelineEvent?.(event);
            this.timelinePanel?.render();

            const targets = Array.isArray(event.ui_targets) ? event.ui_targets : [];
            if (targets.includes('notification_bar')) {
                const { message, tone } = this.formatNotification(event);
                if (message && this.playerGarage?.pushNotification) {
                    this.playerGarage.pushNotification(message, tone);
                }
            }

            if (targets.includes('hud_overlay') && this.playerGarage?.pushHudBanner) {
                const banner = this.formatHudBanner(event);
                if (banner) {
                    this.playerGarage.pushHudBanner(banner);
                }
            }
        });
    }

    formatNotification(event) {
        const tone = this.mapTone(event.event_type);
        const baseName = event.driver_name || event.team_name || 'AI Car';
        const payload = event.payload || {};
        let message = event.payload?.message;

        if (!message) {
            switch (event.event_type) {
                case 'ai_run_started':
                    message = `${baseName}: ${payload.program || 'Run'} started (${payload.laps_planned || '?'} laps)`;
                    break;
                case 'ai_run_completed':
                    message = `${baseName}: ${payload.program || 'Run'} complete – best ${payload.best_lap_s ? this.formatLapTime(payload.best_lap_s) : '--'}`;
                    break;
                case 'ai_setup_adjustment':
                    message = `${baseName}: Setup adjustment applied`;
                    break;
                case 'ai_setup_converged':
                    message = `${baseName}: Setup OK – thresholds met`;
                    break;
                case 'brake_hot_section':
                    message = `${baseName}: ${payload.message || 'Brakes near critical temperature'}`;
                    break;
                case 'brake_duct_low':
                    message = `${baseName}: ${payload.message || 'Brake ducts too closed'}`;
                    break;
                case 'brake_duct_high':
                    message = `${baseName}: ${payload.message || 'Brake ducts too open'}`;
                    break;
                default:
                    if (event.event_type?.startsWith('battle_')) {
                        message = payload.message
                            || `${payload.attacker_name || 'Attacker'} vs ${payload.defender_name || 'Defender'} (${payload.section || 'track'})`;
                    }
                    break;
            }
        }

        return { message, tone };
    }

    formatHudBanner(event) {
        const tone = this.mapTone(event.event_type);
        const payload = event.payload || {};
        const title = this.getHudTitle(event.event_type);
        const body = payload.message
            || this.buildBattleBody(payload)
            || this.buildGenericBody(event);

        if (!body) return null;

        return {
            title,
            body,
            tone,
            duration: tone === 'error' ? 6000 : 4000,
        };
    }

    buildBattleBody(payload = {}) {
        if (!payload.attacker_name && !payload.defender_name) return null;
        const attacker = payload.attacker_name || payload.attacker_id || 'Car A';
        const defender = payload.defender_name || payload.defender_id || 'Car B';
        const section = payload.section || 'track';
        const outcome = payload.outcome ? payload.outcome.replace(/_/g, ' ') : '';
        return `${attacker} vs ${defender} – ${outcome || 'battle'} (${section})`;
    }

    buildGenericBody(event) {
        const payload = event.payload || {};
        if (event.event_type === 'ai_setup_converged') {
            const driver = event.driver_name || 'Driver';
            return `${driver} setup completed (score ${payload.final_score ?? '--'})`;
        }
        if (event.event_type === 'ai_run_completed') {
            const driver = event.driver_name || 'Driver';
            const timeLabel = payload.best_lap_s ? ` (${this.formatLapTime(payload.best_lap_s)})` : '';
            return `${driver}: ${payload.program || 'Run'} complete${timeLabel}`;
        }
        return null;
    }

    getHudTitle(eventType = '') {
        if (eventType.startsWith('battle_')) {
            if (eventType === 'battle_collision') return 'Collision';
            if (eventType === 'battle_blocked') return 'Blocked';
            if (eventType === 'battle_side_by_side') return 'Side by Side';
            return 'Overtake';
        }
        switch (eventType) {
            case 'ai_setup_converged':
                return 'Setup';
            case 'ai_setup_adjustment':
                return 'Setup';
            case 'brake_hot_section':
                return 'Brake Warning';
            case 'brake_duct_low':
            case 'brake_duct_high':
                return 'Brake Duct';
            default:
                return 'Event';
        }
    }

    mapTone(eventType = '') {
        if (eventType === 'battle_collision') {
            return 'error';
        }
        if (eventType === 'battle_blocked' || eventType === 'battle_side_by_side') {
            return 'warning';
        }
        if (eventType === 'brake_hot_section') {
            return 'error';
        }
        if (eventType === 'brake_duct_low' || eventType === 'brake_duct_high') {
            return 'warning';
        }
        if (eventType === 'ai_setup_converged') {
            return 'success';
        }
        return 'info';
    }

    formatLapTime(seconds) {
        if (!seconds || Number.isNaN(seconds)) return '--:--.---';
        const totalMs = Math.max(0, seconds) * 1000;
        const minutes = Math.floor(totalMs / 60000);
        const remMs = totalMs - minutes * 60000;
        const secs = Math.floor(remMs / 1000);
        const millis = Math.round(remMs % 1000);
        const pad = (val, len) => String(val).padStart(len, '0');
        return `${minutes}:${pad(secs, 2)}.${pad(millis, 3)}`;
    }
}
