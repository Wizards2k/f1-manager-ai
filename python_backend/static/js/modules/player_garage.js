export class PlayerGarage {
    constructor(state, { teamLabel, statusMsg, cardsContainer, overlayContainer, dockElement, notificationsContainer }) {
        this.state = state;
        this.teamLabel = teamLabel;
        this.statusMsg = statusMsg;
        this.cardsContainer = cardsContainer;
        this.overlayContainer = overlayContainer;
        this.dockElement = dockElement;
        this.notificationsContainer = notificationsContainer;
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
        this.SETUP_FIELDS = [
            'front_wing',
            'rear_wing',
            'ride_height_front',
            'ride_height_rear',
            'suspension_front',
            'suspension_rear'
        ];
        this.setupDefaults = {
            front_wing: 50,
            rear_wing: 50,
            ride_height_front: 50,
            ride_height_rear: 50,
            suspension_front: 50,
            suspension_rear: 50
        };
        this.setupOpenDrivers = new Set();
        this.setupDrafts = new Map();
        this.notificationTimers = new WeakMap();
        this.bindEvents();
    }

    bindEvents() {
        if (!this.cardsContainer) return;
        this.cardsContainer.addEventListener('click', (event) => this.handleCardClick(event));
        this.cardsContainer.addEventListener('change', (event) => this.handleFieldChange(event));
        this.cardsContainer.addEventListener('input', (event) => this.handleSetupInput(event));
        this.cardsContainer.addEventListener('focusout', (event) => this.handleFocusOut(event));
        if (this.overlayContainer) {
            this.overlayContainer.addEventListener('click', (event) => {
                const actionBtn = event.target.closest('[data-action]');
                if (actionBtn) {
                    const driver = Number(this.overlayContainer.dataset.driver);
                    if (driver) {
                        this.handleOverlayAction(driver, actionBtn.dataset.action);
                    }
                }
            });
            this.overlayContainer.addEventListener('input', (event) => {
                if (!event.target.dataset.setupField) return;
                const driver = Number(this.overlayContainer.dataset.driver);
                if (driver) {
                    this.handleSetupInput(event, driver, this.overlayContainer);
                }
            });
        }
    }

    setStatus(message, tone = 'info') {
        if (this.statusMsg) {
            this.statusMsg.textContent = message;
            this.statusMsg.style.color = tone === 'error' ? '#ff7b72' : tone === 'success' ? '#8bdcb8' : '#8bdcb8';
        }
        this.pushNotification(message, tone);
    }

    pushNotification(message, tone = 'info') {
        if (!this.notificationsContainer || !message) return;
        const toast = document.createElement('div');
        toast.className = `garage-toast ${tone}`;
        toast.textContent = message;
        this.notificationsContainer.appendChild(toast);

        const toasts = this.notificationsContainer.querySelectorAll('.garage-toast');
        if (toasts.length > 3) {
            toasts[0].classList.add('hide');
            setTimeout(() => toasts[0].remove(), 220);
        }

        const timer = setTimeout(() => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 220);
        }, 4500);
        this.notificationTimers.set(toast, timer);
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
        const telemetry = this.buildTelemetryStrip(car);

        return `
            <div class="car-card" data-driver="${car.driver_number}" data-state="${currentState}">
                <header>
                    <div>
                        <div class="driver-topline">
                            <div class="team-dot" style="background:${car.team_color};">${car.driver_number}</div>
                            <div>
                                <div class="driver-tag">${car.driver_name || 'Driver'}</div>
                                <div class="driver-status-line">${driverStatus}</div>
                            </div>
                        </div>
                    </div>
                    <span class="state-pill">${stateDisplay}</span>
                </header>
                ${telemetry}
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
                <div class="car-actions with-setup">
                    <div class="drive-actions">
                        <button class="btn-send" data-action="send" ${isBox ? '' : 'disabled'}>Send Out</button>
                        <button class="btn-box" data-action="box" ${isBox ? 'disabled' : ''}>Box</button>
                    </div>
                    <button class="btn-setup" data-action="setup" ${isBox ? '' : 'disabled'}>Setup</button>
                </div>
            </div>
        `;
    }

    buildTelemetryStrip(car) {
        const bestLap = typeof car.best_lap_time === 'number' ? car.best_lap_time : null;
        const lastLap = Array.isArray(car.lap_times) && car.lap_times.length ? car.lap_times[car.lap_times.length - 1] : null;
        const delta = bestLap && lastLap ? lastLap - bestLap : null;
        const deltaLabel = delta === null
            ? (bestLap ? `${bestLap.toFixed(3)}s best` : 'No lap yet')
            : `${delta >= 0 ? '+' : '-'}${Math.abs(delta).toFixed(3)}s vs best`;

        const sectors = ['sector1', 'sector2', 'sector3'].map(key => {
            const current = car.current_lap_sectors?.[key];
            const best = car.best_sectors?.[key];
            const status = !current
                ? 'idle'
                : !best || current < best - 0.02 ? 'purple'
                : current <= best + 0.1 ? 'green'
                : 'yellow';
            return `<span class="telemetry-sector ${status}" aria-label="${key}">${current ? current.toFixed(2) : '--'}</span>`;
        }).join('');

        const tireWear = typeof car.tire_wear === 'number' ? Math.max(0, Math.min(1, car.tire_wear)) : 0;
        const tireHealthPct = Math.round((1 - tireWear) * 100);
        const fuel = Math.round(car.fuel_percent ?? car.player_config?.fuel_percent ?? 100);

        return `
            <div class="telemetry-strip">
                <div class="telemetry-lap" title="Lap delta">
                    <span class="telemetry-label">Lap</span>
                    <span class="telemetry-delta">${deltaLabel}</span>
                </div>
                <div class="telemetry-sectors">
                    ${sectors}
                </div>
                <div class="telemetry-bars">
                    <div class="telemetry-bar" title="Fuel ${fuel}%">
                        <span>Fuel</span>
                        <div class="bar-track"><span style="width:${fuel}%"></span></div>
                    </div>
                    <div class="telemetry-bar" title="Tires ${tireHealthPct}%">
                        <span>Tires</span>
                        <div class="bar-track"><span style="width:${tireHealthPct}%"></span></div>
                    </div>
                </div>
            </div>
        `;
    }

    getSetupPayload(car) {
        const baseConfig = car.player_config?.setup || {};
        const draftKey = car.driver_number;
        const draft = this.setupDrafts.get(draftKey) || {};
        const values = {};
        this.SETUP_FIELDS.forEach(field => {
            const carValue = baseConfig[field] ?? car[field] ?? this.setupDefaults[field];
            values[field] = draft[field] ?? carValue ?? this.setupDefaults[field];
        });
        const recommendation = car.setup_recommendation || {};
        return { values, recommendation };
    }

    buildSetupOverlay(car, isBox) {
        if (!this.overlayContainer) return;
        const driverNumber = car.driver_number;
        const setupState = this.getSetupPayload(car);
        const { values, recommendation } = setupState;
        const fieldFeedback = recommendation?.fields || {};

        const groupings = [
            {
                title: 'Aerodynamics',
                pairs: [
                    { field: 'front_wing', label: 'Front wing' },
                    { field: 'rear_wing', label: 'Rear wing' }
                ]
            },
            {
                title: 'Ride height',
                pairs: [
                    { field: 'ride_height_front', label: 'Front ride height' },
                    { field: 'ride_height_rear', label: 'Rear ride height' }
                ]
            },
            {
                title: 'Suspension',
                pairs: [
                    { field: 'suspension_front', label: 'Front suspension' },
                    { field: 'suspension_rear', label: 'Rear suspension' }
                ]
            }
        ];

        const controls = groupings.map(group => `
            <section class="setup-group">
                <div class="setup-group-title">${group.title}</div>
                <div class="setup-pair">
                    ${group.pairs.map(cfg => this.buildSetupControl(driverNumber, cfg.field, cfg.label, values[cfg.field], fieldFeedback[cfg.field])).join('')}
                </div>
            </section>
        `).join('');

        const recommendationMsg = recommendation?.message || 'Adjust the sliders to explore balance. Recommendations coming soon.';
        const recommendationTone = recommendation?.tone || 'info';
        const score = typeof recommendation?.score === 'number' ? recommendation.score.toFixed(2) : null;

        this.overlayContainer.dataset.driver = driverNumber;
        this.overlayContainer.classList.add('is-visible');
        this.overlayContainer.classList.remove('is-hiding');
        if (this.dockElement) {
            this.dockElement.classList.add('setup-open');
        }
        // Add setup-active class to circuit-container for CSS control
        const circuitContainer = this.dockElement?.closest('.circuit-container');
        if (circuitContainer) {
            circuitContainer.classList.add('setup-active');
        }
        // Force-hide notifications to avoid overlay gap
        if (this.notificationsContainer) {
            this.notificationsContainer.dataset.prevDisplay = this.notificationsContainer.style.display;
            this.notificationsContainer.style.display = 'none';
        }
        document.body.classList.add('setup-active');
        // Trigger layout recalculation (map height) after setup open
        window.dispatchEvent(new Event('resize'));
        this.overlayContainer.innerHTML = `
            <div class="setup-panel">
                <div class="setup-header">
                    <div>
                        <h4>Setup - #${driverNumber}</h4>
                        <div class="setup-status-pill">${isBox ? 'In garage' : 'On track'}${score ? ` • Score ${score}` : ''}</div>
                    </div>
                    <button class="setup-close" data-action="close-setup" aria-label="Close setup">×</button>
                </div>
                <div class="setup-feedback ${recommendationTone}">${recommendationMsg}</div>
                <div class="setup-groups">
                    ${controls}
                </div>
                <div class="setup-footer">
                    <button class="reset" data-action="reset-setup">Reset</button>
                    <button class="apply" data-action="apply-setup">Apply</button>
                </div>
            </div>
        `;
    }

    buildSetupControl(driverNumber, field, label, value, feedback = {}) {
        const range = feedback?.range;
        const rangeLabel = range ? `${range.min}-${range.max}` : 'No range yet';
        const statusClass = feedback?.status ? `status-${feedback.status}` : 'status-missing';
        const deltaLabel = feedback?.delta_label || 'Pending data';
        const displayValue = typeof feedback?.value === 'number' ? feedback.value : value;
        return `
            <div class="setup-control ${statusClass}" data-field="${field}" data-driver="${driverNumber}">
                <div class="setup-control-header">
                    <span>${label}</span>
                    <span class="setup-range-badge">${rangeLabel}</span>
                </div>
                <input type="range" min="1" max="100" value="${displayValue}" data-setup-field="${field}" />
                <div class="setup-control-footer">
                    <span class="setup-value">${displayValue}</span>
                    <span class="setup-delta ${statusClass}">${deltaLabel}</span>
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

    toggleSetupOverlay(driverNumber, open = true) {
        if (!this.overlayContainer) return;
        if (open) {
            this.setupOpenDrivers.add(driverNumber);
            const car = this.state.getPlayerCar(driverNumber);
            if (car) {
                this.overlayContainer.classList.add('is-visible');
                this.overlayContainer.classList.remove('is-hiding');
                this.buildSetupOverlay(car, car?.state === 'BOX');
            }
        } else {
            this.setupOpenDrivers.delete(driverNumber);
            const panel = this.overlayContainer.querySelector('.setup-panel');
            if (panel) {
                this.overlayContainer.classList.add('is-hiding');
                panel.classList.add('closing');
                panel.addEventListener('animationend', () => this.resetSetupOverlayState(), { once: true });
            } else {
                this.resetSetupOverlayState();
            }
        }
    }

    resetSetupOverlayState() {
        if (!this.overlayContainer) return;
        this.overlayContainer.classList.remove('is-visible', 'is-hiding');
        this.overlayContainer.removeAttribute('data-driver');
        this.overlayContainer.innerHTML = '';
        if (this.dockElement) {
            this.dockElement.classList.remove('setup-open');
        }
        const circuitContainer = this.dockElement?.closest('.circuit-container');
        if (circuitContainer) {
            circuitContainer.classList.remove('setup-active');
        }
        if (this.notificationsContainer) {
            const prev = this.notificationsContainer.dataset.prevDisplay ?? '';
            this.notificationsContainer.style.display = prev;
            delete this.notificationsContainer.dataset.prevDisplay;
        }
        document.body.classList.remove('setup-active');
        // Trigger layout recalculation (map height) after setup close
        window.dispatchEvent(new Event('resize'));
    }

    getSetupDraft(driverNumber) {
        if (!this.setupDrafts.has(driverNumber)) {
            this.setupDrafts.set(driverNumber, {});
        }
        return this.setupDrafts.get(driverNumber);
    }

    resetSetupDraft(driverNumber) {
        this.setupDrafts.delete(driverNumber);
    }

    buildSetupPayloadFromDraft(driverNumber, car) {
        const draft = this.setupDrafts.get(driverNumber) || {};
        const payload = {};
        this.SETUP_FIELDS.forEach(field => {
            payload[field] = draft[field] ?? car.player_config?.setup?.[field] ?? car[field] ?? this.setupDefaults[field];
        });
        return payload;
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

    handleOverlayAction(driverNumber, action) {
        if (action === 'close-setup') {
            this.toggleSetupOverlay(driverNumber, false);
        } else if (action === 'reset-setup') {
            this.resetSetupDraft(driverNumber);
            const carData = this.state.getPlayerCar(driverNumber);
            if (carData) {
                this.buildSetupOverlay(carData, this.getCarState(carData) === 'BOX');
            }
        } else if (action === 'apply-setup') {
            const carData = this.state.getPlayerCar(driverNumber);
            if (!carData) {
                this.setStatus('Player car unavailable.', 'error');
                return;
            }
            const state = this.getCarState(carData);
            const payload = this.buildSetupPayloadFromDraft(driverNumber, carData);
            this.submitSetupConfig(driverNumber, payload, state);
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
        } else if (action === 'setup') {
            this.toggleSetupOverlay(driverNumber, true);
        } else if (action === 'close-setup') {
            this.toggleSetupOverlay(driverNumber, false);
        } else if (action === 'reset-setup') {
            this.resetSetupDraft(driverNumber);
            this.toggleSetupOverlay(driverNumber, true);
        } else if (action === 'apply-setup') {
            const carData = this.state.getPlayerCar(driverNumber);
            if (!carData) {
                this.setStatus('Player car unavailable.', 'error');
                return;
            }
            const payload = this.buildSetupPayloadFromDraft(driverNumber, carData);
            this.submitSetupConfig(driverNumber, payload, state);
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

    handleSetupInput(event, forcedDriverNumber, forcedContainer) {
        const setupField = event.target.dataset.setupField;
        if (!setupField) return;
        const container = forcedContainer || event.target.closest('.car-card');
        if (!container) return;
        const driverNumber = forcedDriverNumber || Number(container.dataset.driver);
        if (!driverNumber) return;
        const value = Number(event.target.value);
        const draft = this.getSetupDraft(driverNumber);
        draft[setupField] = value;
        const control = event.target.closest('.setup-control');
        if (control) {
            const valueLabel = control.querySelector('.setup-value');
            if (valueLabel) valueLabel.textContent = value;
        }
    }

    async submitSetupConfig(driverNumber, setupPayload, state) {
        if (state !== 'BOX') {
            this.setStatus('Bring the car into the garage to edit the setup.', 'error');
            return;
        }
        try {
            const res = await fetch(`/api/player/car/${driverNumber}/setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ setup: setupPayload })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Setup update failed');
            this.setStatus(`Setup stored for #${driverNumber}.`, 'success');
            this.applySetupLocally(driverNumber, setupPayload, data.recommendation);
            this.resetSetupDraft(driverNumber);
            this.toggleSetupOverlay(driverNumber, false);
        } catch (err) {
            console.error(err);
            this.setStatus(err.message || 'Setup update failed', 'error');
        }
    }

    applySetupLocally(driverNumber, setupPayload, recommendation) {
        const car = { ...(this.state.getPlayerCar(driverNumber) || {}) };
        if (!car.driver_number) return;
        car.player_config = car.player_config || {};
        car.player_config.setup = { ...(car.player_config.setup || {}), ...setupPayload };
        if (recommendation) {
            car.setup_recommendation = recommendation;
        }
        this.state.setPlayerCar(car);
        this.render(true);
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
