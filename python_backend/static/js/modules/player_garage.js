export class PlayerGarage {
    constructor(state, { teamLabel, statusMsg, cardsContainer }) {
        this.state = state;
        this.teamLabel = teamLabel;
        this.statusMsg = statusMsg;
        this.cardsContainer = cardsContainer;
        this.tyreOptions = [
            { value: 'soft', label: 'Soft' },
            { value: 'medium', label: 'Medium' },
            { value: 'hard', label: 'Hard' }
        ];
        this.iceOptions = ['Save', 'Standard', 'Push'];
        this.ersOptions = ['Harvest', 'Neutral', 'Deploy', 'Overtake'];
        this.STATE_DISPLAY = {
            BOX: 'BOX',
            OUT_LAP: 'OUT LAP',
            HOT_LAP: 'HOT LAP',
            FLYING_LAP: 'FLYING LAP',
            IN_LAP: 'IN LAP',
            ON_TRACK: 'ON TRACK'
        };
        this.BOX_ONLY_FIELDS = new Set(['tyre_compound', 'fuel_percent', 'stint_target_laps']);
        this.bindEvents();
    }

    bindEvents() {
        if (!this.cardsContainer) return;
        this.cardsContainer.addEventListener('click', (event) => this.handleCardClick(event));
        this.cardsContainer.addEventListener('change', (event) => this.handleFieldChange(event));
        this.cardsContainer.addEventListener('focusout', (event) => this.handleFocusOut(event));
    }

    setStatus(message, tone = 'info') {
        if (!this.statusMsg) return;
        this.statusMsg.textContent = message;
        this.statusMsg.style.color = tone === 'error' ? '#ff7b72' : tone === 'success' ? '#8bdcb8' : '#8bdcb8';
    }

    normalizeStateValue(state) {
        if (!state) return null;
        if (typeof state === 'object' && 'value' in state) {
            state = state.value;
        }
        if (typeof state === 'string') {
            return state.trim().toUpperCase().replace(/\s+/g, '_');
        }
        return state;
    }

    getCarState(car) {
        let baseState = this.normalizeStateValue(car.state);
        if (!baseState) {
            baseState = car.is_on_track ? 'ON_TRACK' : 'BOX';
        }

        const lapsRemaining = typeof car.stint_laps_remaining === 'number'
            ? car.stint_laps_remaining
            : (typeof car.stint_target_laps === 'number' ? car.stint_target_laps : null);

        if ((baseState === 'OUT_LAP' || baseState === 'HOT_LAP' || baseState === 'ON_TRACK') && lapsRemaining !== null && lapsRemaining <= 0) {
            return 'IN_LAP';
        }

        if (baseState === 'FLYING_LAP') {
            return 'HOT_LAP';
        }

        return baseState;
    }

    getStateDisplay(state) {
        return this.STATE_DISPLAY[state] || state?.replace(/_/g, ' ') || 'BOX';
    }

    buildCarCard(car) {
        const tyreChoice = car.player_config?.tyre_compound || car.current_tire || 'medium';
        const fuelPercent = car.player_config?.fuel_percent ?? car.fuel_percent ?? 100;
        const stintTarget = car.player_config?.stint_target_laps ?? car.stint_target_laps ?? 5;
        const paceLevel = car.player_config?.pace_level ?? car.pace_level ?? 5;
        const iceMode = car.player_config?.ice_mode ?? car.ice_mode ?? 'Standard';
        const ersMode = car.player_config?.ers_mode ?? car.ers_mode ?? 'Neutral';
        const maxStint = car.max_stint_laps ?? stintTarget;
        const tireWear = Math.max(0, Math.min(1, car.tire_wear ?? 0));
        const tireHealthPct = Math.round((1 - tireWear) * 100);
        const currentState = this.getCarState(car);
        const lapInfo = typeof car.total_laps === 'number' && car.total_laps > 0 ? `- Lap ${car.total_laps}` : '';
        const stateDisplay = this.getStateDisplay(currentState);
        const driverStatus = currentState === 'BOX'
            ? 'Ready in BOX'
            : `${stateDisplay}${lapInfo ? ` ${lapInfo}` : ''}`;
        const isBox = currentState === 'BOX';

        return `
            <div class="car-card" data-driver="${car.driver_number}" data-state="${currentState}">
                <header>
                    <div>
                        <div class="driver-topline">
                            <div class="team-dot" style="background:${car.team_color};">${car.driver_number}</div>
                            <div>
                                <div class="driver-tag">${car.driver_name || 'Driver'}</div>
                                <div class="driver-subline">Fuel ${Math.round(car.fuel_percent ?? 100)}%  Tyre ${car.current_tire?.toUpperCase() || 'MED'}</div>
                                <div class="driver-status-line">${driverStatus}</div>
                            </div>
                        </div>
                    </div>
                    <span class="state-pill">${stateDisplay}</span>
                </header>
                <div class="control-grid">
                    <div class="field-span-2">
                        <label>Tyre compound</label>
                        <div class="tyre-row">
                            <select class="select-compact" data-field="tyre_compound" ${isBox ? '' : 'disabled'}>
                                ${this.tyreOptions.map(opt => `<option value="${opt.value}" ${opt.value === tyreChoice ? 'selected' : ''}>${opt.label}</option>`).join('')}
                            </select>
                            <span class="wear-indicator">${tireHealthPct}%</span>
                        </div>
                    </div>
                    <div class="offset-left">
                        <label>Fuel %</label>
                        <input class="input-compact" type="number" data-field="fuel_percent" min="1" max="100" value="${fuelPercent}" ${isBox ? '' : 'disabled'}>
                    </div>
                    <div class="offset-left">
                        <label>Stint laps <span class="numeric-hint">max ${maxStint}</span></label>
                        <input class="input-compact" type="number" data-field="stint_target_laps" min="1" max="${maxStint}" value="${stintTarget}" ${isBox ? '' : 'disabled'}>
                    </div>
                    <div class="field-span-2">
                        <label>ICE map</label>
                        <select class="select-compact" data-field="ice_mode">
                            ${this.iceOptions.map(mode => `<option value="${mode}" ${mode === iceMode ? 'selected' : ''}>${mode}</option>`).join('')}
                        </select>
                    </div>
                    <div class="field-span-2 control-dual shift-left">
                        <div class="inline-control offset-left-small" style="margin-right:-6px;">
                            <label>ERS mode</label>
                            <select class="select-compact" data-field="ers_mode">
                                ${this.ersOptions.map(mode => `<option value="${mode}" ${mode === ersMode ? 'selected' : ''}>${mode}</option>`).join('')}
                            </select>
                        </div>
                        <div class="inline-control slider-inline" style="flex:0 0 auto;margin-left:10px;">
                            <label>Driver push (${paceLevel})</label>
                            <input class="compact-range" type="range" data-field="pace_level" min="1" max="10" value="${paceLevel}">
                        </div>
                    </div>
                </div>
                <div class="car-actions">
                    <button class="btn-send" data-action="send" ${isBox ? '' : 'disabled'}>Send Out</button>
                    <button class="btn-box" data-action="box" ${isBox ? 'disabled' : ''}>Box</button>
                </div>
            </div>
        `;
    }

    render(force = false) {
        if (!this.cardsContainer) return;
        if (!force && this.cardsContainer.contains(document.activeElement)) {
            return;
        }

        if (!this.state.getPlayerTeam()) {
            this.cardsContainer.innerHTML = '<p style="color:#777;">No player team configured.</p>';
            return;
        }

        const cars = this.state.getPlayerCarsSorted();
        if (cars.length === 0) {
            this.cardsContainer.innerHTML = '<p style="color:#777;">Waiting for garage data...</p>';
            return;
        }

        this.cardsContainer.innerHTML = cars.map(car => this.buildCarCard(car)).join('');
    }

    collectCardPayload(card) {
        const payload = {};
        card.querySelectorAll('[data-field]').forEach(el => {
            if (el.disabled) return;
            payload[el.dataset.field] = el.type === 'range' || el.type === 'number'
                ? Number(el.value)
                : el.value;
        });
        return payload;
    }

    applyLocalPlayerUpdates(driverNumber, payload = {}) {
        const car = { ...(this.state.getPlayerCar(driverNumber) || {}) };
        if (!car.driver_number) return;
        car.player_config = { ...(car.player_config || {}), ...payload };
        Object.entries(payload).forEach(([key, value]) => {
            if (key === 'tyre_compound') car.current_tire = value;
            if (key === 'fuel_percent') car.fuel_percent = value;
            if (key === 'pace_level') car.pace_level = value;
            if (key === 'ice_mode') car.ice_mode = value;
            if (key === 'ers_mode') car.ers_mode = value;
            if (key === 'stint_target_laps') car.stint_target_laps = value;
        });
        car.state = this.getCarState(car);
        this.state.setPlayerCar(car);
    }

    applyLocalCarState(driverNumber, carPayload) {
        if (!carPayload) return;
        const updated = {
            ...(this.state.getPlayerCar(driverNumber) || {}),
            ...carPayload,
        };
        updated.state = this.getCarState(updated);
        this.state.setPlayerCar(updated);
    }

    async sendPlayerConfig(driverNumber, payload, state) {
        const allowedPayload = { ...payload };
        if (state !== 'BOX') {
            delete allowedPayload.tyre_compound;
            delete allowedPayload.fuel_percent;
            delete allowedPayload.stint_target_laps;
        }
        if (Object.keys(allowedPayload).length === 0) {
            this.setStatus('No configurable fields available right now.', 'error');
            return false;
        }
        try {
            const res = await fetch(`/api/player/car/${driverNumber}/configure`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(allowedPayload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Configuration failed');
            this.setStatus(`Setup stored for #${driverNumber}.`, 'success');
            this.applyLocalPlayerUpdates(driverNumber, allowedPayload);
            this.render(true);
            return true;
        } catch (err) {
            console.error(err);
            this.setStatus(err.message || 'Configuration failed', 'error');
            return false;
        }
    }

    async sendPlayerCarOut(driverNumber) {
        try {
            const res = await fetch(`/api/player/car/${driverNumber}/send_out`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Send out failed');
            this.setStatus(`Car #${driverNumber} released.`, 'success');
            this.applyLocalCarState(driverNumber, data.car);
            this.render(true);
            return true;
        } catch (err) {
            console.error(err);
            this.setStatus(err.message || 'Send out failed', 'error');
            return false;
        }
    }

    async requestPlayerBox(driverNumber) {
        try {
            const res = await fetch(`/api/player/car/${driverNumber}/box`, { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Box call failed');
            this.setStatus(`Box request for #${driverNumber} acknowledged.`, 'success');
            this.applyLocalCarState(driverNumber, data.car);
            this.render(true);
            return true;
        } catch (err) {
            console.error(err);
            this.setStatus(err.message || 'Box call failed', 'error');
            return false;
        }
    }

    handleCardClick(event) {
        const actionBtn = event.target.closest('button[data-action]');
        if (!actionBtn) return;
        const card = actionBtn.closest('.car-card');
        const driverNumber = Number(card?.dataset.driver);
        if (!driverNumber) return;
        const state = card.dataset.state;
        const action = actionBtn.dataset.action;

        if (action === 'send') {
            if (state !== 'BOX') {
                this.setStatus('Car already on track. Box first to change tyres/fuel.', 'error');
                return;
            }
            const payload = this.collectCardPayload(card);
            this.sendPlayerConfig(driverNumber, payload, state).then(configured => {
                if (configured) {
                    this.sendPlayerCarOut(driverNumber);
                }
            });
        } else if (action === 'box') {
            if (state === 'BOX') {
                this.setStatus('Car already in the garage.', 'error');
                return;
            }
            this.requestPlayerBox(driverNumber);
        }
    }

    handleFieldChange(event) {
        const target = event.target;
        const field = target.dataset.field;
        if (!field) return;
        const card = target.closest('.car-card');
        if (!card) return;
        const driverNumber = Number(card.dataset.driver);
        const state = card.dataset.state;
        if (!driverNumber) return;

        if (state !== 'BOX' && this.BOX_ONLY_FIELDS.has(field)) {
            this.setStatus('Bring the car into the garage to change tyres, fuel, or stint laps.', 'error');
            const carData = this.state.getPlayerCar(driverNumber);
            if (carData) {
                const revertValue = carData.player_config?.[field] ?? carData[field];
                if (revertValue !== undefined) {
                    target.value = revertValue;
                }
            }
            return;
        }

        const payload = {};
        payload[field] = target.type === 'range' || target.type === 'number'
            ? Number(target.value)
            : target.value;
        this.sendPlayerConfig(driverNumber, payload, state);
    }

    handleFocusOut(event) {
        if (!this.cardsContainer.contains(event.relatedTarget)) {
            requestAnimationFrame(() => this.render(true));
        }
    }

    async loadPlayerTeamInfo(retryCount = 0) {
        try {
            const res = await fetch('/api/player/team');
            const data = await res.json();
            if (!res.ok || !data?.team_id) {
                throw new Error(data?.error || data?.message || 'Player team unavailable');
            }
            this.state.setPlayerTeam(data.team_id);
            if (this.teamLabel) {
                this.teamLabel.textContent = `${data.team_name} (${data.team_code})`;
            }
            this.setStatus(`${data.team_name} garage ready.`);
            this.render(true);
        } catch (err) {
            console.error('loadPlayerTeamInfo error:', err);
            if (retryCount < 3) {
                this.setStatus('Loading player garage...', 'info');
                setTimeout(() => this.loadPlayerTeamInfo(retryCount + 1), 800);
            } else {
                if (this.teamLabel) {
                    this.teamLabel.textContent = 'No team configured';
                }
                this.setStatus('Player team missing!', 'error');
            }
        }
    }
}
