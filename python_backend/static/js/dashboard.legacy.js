        class AppState {
            constructor() {
                this.sessionBests = {
                    best_lap: null,
                    best_sectors: { sector1: null, sector2: null, sector3: null }
                };
                this.carMarkers = new Map();
                this.playerCars = new Map();
                this.playerTeamId = null;
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
                this.playerCars.set(car.driver_number, car);
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
        }

        class MapModule {
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

        class TimingPanel {
            constructor(state, tableElement, timerElement) {
                this.state = state;
                this.tableElement = tableElement;
                this.timerElement = timerElement;
            }

            static formatLapTime(seconds) {
                if (seconds == null) return '--:--.---';
                const mins = Math.floor(seconds / 60);
                const secs = (seconds % 60).toFixed(3);
                return `${mins}:${secs.padStart(6, '0')}`;
            }

            static formatSectorTime(seconds) {
                if (!seconds) return '--:--';
                const mins = Math.floor(seconds / 60);
                const secs = (seconds % 60).toFixed(3);
                return mins > 0 ? `${mins}:${secs.padStart(6, '0')}` : secs;
            }

            static formatDelta(current, reference) {
                if (current == null || reference == null) return null;
                const delta = current - reference;
                const sign = delta >= 0 ? '+' : '-';
                return `${sign}${Math.abs(delta).toFixed(3)}`;
            }

            lapClass(lapTime, personalBest) {
                const sessionBest = this.state.sessionBests.best_lap;
                if (!lapTime) return '';
                if (sessionBest && Math.abs(lapTime - sessionBest) < 0.001) return 'time-session-best';
                if (personalBest && Math.abs(lapTime - personalBest) < 0.001) return 'time-personal-best';
                if (sessionBest && lapTime > sessionBest * 1.07) return 'time-slow';
                return 'time-normal';
            }

            sectorClass(sectorTime, personalBest, sectorKey) {
                const sessionBest = this.state.sessionBests.best_sectors?.[sectorKey];
                if (!sectorTime) return '';
                if (sessionBest && Math.abs(sectorTime - sessionBest) < 0.001) return 'time-session-best';
                if (personalBest && Math.abs(sectorTime - personalBest) < 0.001) return 'time-personal-best';
                return 'time-normal';
            }

            render(cars) {
                if (!this.tableElement) return;
                const sorted = [...cars].sort((a, b) => {
                    if (!a.best_lap_time) return 1;
                    if (!b.best_lap_time) return -1;
                    return a.best_lap_time - b.best_lap_time;
                });

                const rows = sorted.map((car, index) => {
                    const isInBox = car.state === 'BOX';
                    const stateClass = car.state ? car.state.toLowerCase().replace('_', '-') : 'box';
                    const sectorKeys = ['sector1', 'sector2', 'sector3'];
                    const sectorHtml = sectorKeys.map((key, idx) => {
                        const current = car.current_lap_sectors?.[key];
                        const reference = car.best_lap_sectors?.[key];
                        const delta = TimingPanel.formatDelta(current, reference);
                        const deltaClass = delta ? ((current - reference) >= 0 ? 'positive' : 'negative') : '';
                        return `
                            <div class="sector-row">
                                <span>S${idx + 1}:</span>
                                <span class="sector-time ${this.sectorClass(current, car.best_sectors?.[key], key)}">${current ? TimingPanel.formatSectorTime(current) : '--:--'}</span>
                                ${delta ? `<span class="sector-delta ${deltaClass}">(${delta})</span>` : '<span class="sector-delta"></span>'}
                            </div>
                        `;
                    }).join('');

                    return `
                        <div class="driver-row ${isInBox ? 'in-box' : 'on-track'}" style="border-left-color: ${car.team_color}">
                            <div class="position">${index + 1}</div>
                            <div class="driver-number" style="background: ${car.team_color}">
                                ${car.driver_number}
                            </div>
                            <div class="driver-info">
                                <div class="driver-name-team">
                                    <div class="driver-name">${car.driver_name ? car.driver_name.split(' ').pop() : ''}</div>
                                    <div class="driver-team">${car.team_name}</div>
                                    <div class="driver-laps">Lap ${car.total_laps} (${car.session_laps} total)</div>
                                </div>
                            </div>
                            <img src="/static/tires/${car.current_tire || 'medium'}.svg" class="tire-icon" alt="${car.current_tire || 'MEDIUM'} tire">
                            <div class="lap-times">
                                <div class="best-lap ${this.lapClass(car.best_lap_time, car.best_lap_time)}">
                                    ${car.best_lap_time ? TimingPanel.formatLapTime(car.best_lap_time) : '--:--.---'}
                                    <small>BEST</small>
                                </div>
                                <div class="sector-times">${sectorHtml}</div>
                                <div class="last-lap ${this.lapClass(car.last_lap_time, car.best_lap_time)}">
                                    ${car.last_lap_time ? TimingPanel.formatLapTime(car.last_lap_time) : '--:--.---'}
                                    <small>LAST</small>
                                    ${car.last_lap_type && car.last_lap_type !== 'HOT_LAP' ? `<small style="color:#888;">(${car.last_lap_type})</small>` : ''}
                                </div>
                            </div>
                            <div class="lap-count"></div>
                            <div class="state-indicator ${stateClass}">
                                ${car.state || 'BOX'}
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    `;
                }).join('');

                this.tableElement.innerHTML = rows;
            }

            updateSessionTimer(secondsRemaining) {
                if (!this.timerElement) return;
                if (secondsRemaining == null) {
                    this.timerElement.textContent = '00:00';
                    this.timerElement.classList.remove('warning', 'danger');
                    return;
                }

                const mins = Math.floor(secondsRemaining / 60);
                const secs = (secondsRemaining % 60).toFixed(0).padStart(2, '0');
                this.timerElement.textContent = `${mins}:${secs}`;
                this.timerElement.classList.toggle('warning', secondsRemaining < 300);
                this.timerElement.classList.toggle('danger', secondsRemaining < 60);
            }
        }

        const appState = new AppState();
        const mapModule = new MapModule(appState);
        mapModule.loadCircuitGeometry().catch(err => console.error('Circuit geometry load failed', err));
        const timingPanel = new TimingPanel(appState, document.getElementById('timing-table'), document.getElementById('session-timer'));

        class PlayerGarage {
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
                this.ersOptions = ['RECHARGE', 'STANDARD', 'OVERTAKE', 'QUALIFY', 'DEFENCE'];
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
                const ersMode = car.player_config?.ers_mode ?? car.ers_mode ?? 'STANDARD';
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

        class SessionControls {
            constructor({ pauseButton, speedButtons, speedIndicator }) {
                this.pauseButton = pauseButton;
                this.speedButtons = Array.from(speedButtons || []);
                this.speedIndicator = speedIndicator;
                this.currentSpeed = 1;
                this.isPaused = false;
                this.bindEvents();
                this.updateSpeedIndicator(this.currentSpeed);
                this.updatePauseButton(this.isPaused);
            }

            bindEvents() {
                if (this.pauseButton) {
                    this.pauseButton.addEventListener('click', () => this.togglePause());
                }
                this.speedButtons.forEach(btn => {
                    btn.addEventListener('click', () => {
                        const speed = parseFloat(btn.dataset.speed);
                        this.changeSpeed(speed);
                    });
                });
            }

            updateSpeedIndicator(speed) {
                if (this.speedIndicator) {
                    this.speedIndicator.textContent = `Speed: ${speed}x`;
                }
                this.speedButtons.forEach(btn => {
                    btn.classList.toggle('active', parseFloat(btn.dataset.speed) === speed);
                });
            }

            updatePauseButton(isPaused) {
                if (!this.pauseButton) return;
                if (isPaused) {
                    this.pauseButton.textContent = '';
                    this.pauseButton.classList.add('paused');
                    this.pauseButton.title = 'Resume';
                } else {
                    this.pauseButton.textContent = 'ũ';
                    this.pauseButton.classList.remove('paused');
                    this.pauseButton.title = 'Pause';
                }
            }

            async togglePause() {
                try {
                    const response = await fetch('/api/toggle_pause', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const data = await response.json();
                    this.isPaused = Boolean(data.is_paused);
                    this.updatePauseButton(this.isPaused);
                } catch (error) {
                    console.error('Error toggling pause:', error);
                }
            }

            async changeSpeed(speed) {
                try {
                    const response = await fetch('/api/set_speed', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ speed })
                    });
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    await response.json();
                    this.currentSpeed = speed;
                    this.updateSpeedIndicator(speed);
                } catch (error) {
                    console.error('Network error setting speed:', error);
                }
            }

            applyServerState({ is_paused: isPaused, game_speed: gameSpeed } = {}) {
                if (typeof isPaused === 'boolean') {
                    this.isPaused = isPaused;
                    this.updatePauseButton(this.isPaused);
                }
                if (typeof gameSpeed === 'number' && !Number.isNaN(gameSpeed)) {
                    this.currentSpeed = gameSpeed;
                    this.updateSpeedIndicator(this.currentSpeed);
                }
            }
        }

        const playerGarage = new PlayerGarage(appState, {
            teamLabel: document.getElementById('player-team-label'),
            statusMsg: document.getElementById('player-status-msg'),
            cardsContainer: document.getElementById('player-car-cards')
        });

        const sessionControls = new SessionControls({
            pauseButton: document.getElementById('pause-btn'),
            speedButtons: document.querySelectorAll('.speed-btn'),
            speedIndicator: document.getElementById('current-speed')
        });

        class SocketBridge {
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

        const socketBridge = new SocketBridge({
            state: appState,
            mapModule,
            timingPanel,
            playerGarage,
            sessionControls
        });
