export class PlayerGarageV3 {
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
            'beam_wing',
            'ride_height_front',
            'ride_height_rear',
            'suspension_front',
            'suspension_rear',
            'antiroll_front',
            'antiroll_rear',
            'brake_balance',
            'brake_duct'
        ];
        this.setupDefaults = {
            front_wing: 50,
            rear_wing: 50,
            beam_wing: 50,
            ride_height_front: 50,
            ride_height_rear: 50,
            suspension_front: 50,
            suspension_rear: 50,
            antiroll_front: 50,
            antiroll_rear: 50,
            brake_balance: 50,
            brake_duct: 50
        };
        this.circuitMapping = null;
        this.validateTimer = null;
        this.lastValidation = null;
        this.PHYS_UNITS = {
            front_wing: '°', rear_wing: '°', beam_wing: '°',
            ride_height_front: 'mm', ride_height_rear: 'mm',
            suspension_front: '', suspension_rear: '',
            antiroll_front: '', antiroll_rear: '',
            brake_balance: '%', brake_duct: '%'
        };
        this.CAT_COLORS = {
            cornering: '#63d59f', speed: '#7fb4ff', traction: '#f2c059',
            stability: '#c49bff', braking: '#ff9a7c'
        };
        this.SETUP_GROUPINGS = [
            {
                title: 'Aerodynamics',
                pairs: [
                    { field: 'front_wing', label: 'Front wing' },
                    { field: 'rear_wing', label: 'Rear wing' },
                    { field: 'beam_wing', label: 'Beam wing' }
                ]
            },
            {
                title: 'Ride Height',
                pairs: [
                    { field: 'ride_height_front', label: 'Front' },
                    { field: 'ride_height_rear', label: 'Rear' }
                ]
            },
            {
                title: 'Suspension & Anti-roll',
                pairs: [
                    { field: 'suspension_front', label: 'Susp. front' },
                    { field: 'suspension_rear', label: 'Susp. rear' },
                    { field: 'antiroll_front', label: 'Antiroll F' },
                    { field: 'antiroll_rear', label: 'Antiroll R' }
                ]
            },
            {
                title: 'Brakes',
                pairs: [
                    { field: 'brake_balance', label: 'Brake balance' },
                    { field: 'brake_duct', label: 'Brake duct' }
                ]
            }
        ];
        this.setupOpenDrivers = new Set();
        this.setupDrafts = new Map();
        this.notificationTimers = new WeakMap();
        this.lastDriverFeedback = new Map();
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
        toast.className = `garage-toast-v3 ${tone}`;
        toast.textContent = message;
        this.notificationsContainer.appendChild(toast);

        const toasts = this.notificationsContainer.querySelectorAll('.garage-toast-v3');
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

    handleDriverFeedback(car) {
        if (!car || !car.is_player_controlled) return;
        const msg = car.driver_feedback;
        if (!msg) return;
        const last = this.lastDriverFeedback.get(car.driver_number);
        if (last === msg) return;
        this.lastDriverFeedback.set(car.driver_number, msg);
        const name = car.driver_name || `Driver #${car.driver_number}`;
        this.pushNotification(`${name}: ${msg}`, 'info');
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

    static extractTempWindow(rawWindow) {
        if (!rawWindow) return null;
        if (Array.isArray(rawWindow) && rawWindow.length >= 2) {
            return [Number(rawWindow[0]), Number(rawWindow[1])];
        }
        if (typeof rawWindow === 'object') {
            const values = Object.values(rawWindow);
            if (values.length >= 2) {
                return [Number(values[0]), Number(values[1])];
            }
        }
        return null;
    }

    getTyreTempStatus(value, range) {
        if (typeof value !== 'number' || !range) {
            return { className: 'tt-status-na', label: 'N/A' };
        }
        if (value < range[0]) {
            return { className: 'tt-status-cold', label: 'COLD' };
        }
        if (value > range[1]) {
            return { className: 'tt-status-hot', label: 'HOT' };
        }
        return { className: 'tt-status-ok', label: 'OK' };
    }

    buildTyreTempsSection(car) {
        const temps = car.tire_temps;
        const rawWindow = car.tire_temp_window;
        const window = PlayerGarageV3.extractTempWindow(rawWindow);
        const positions = [
            { key: 'fl', label: 'FL' },
            { key: 'fr', label: 'FR' },
            { key: 'rl', label: 'RL' },
            { key: 'rr', label: 'RR' }
        ];

        const cells = positions.map(pos => {
            const val = temps ? temps[pos.key] : null;
            const status = this.getTyreTempStatus(val, window);
            const display = typeof val === 'number' ? `${Math.round(val)}°` : '--';
            return `<div class="tt-cell-v3"><span class="tt-pos-v3">${pos.label}</span><span class="tt-val-v3 ${status.className}">${display}</span></div>`;
        }).join('');

        const windowLabel = window ? `${Math.round(window[0])}–${Math.round(window[1])}°C` : '';

        return `
            <div class="tyre-temps-grid-v3">
                <span class="tt-title-v3">Tyre °C</span>
                <div class="tt-2x2-v3">
                    ${cells}
                </div>
                ${windowLabel ? `<span class="tt-window-v3">${windowLabel}</span>` : ''}
            </div>
        `;
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
        const tyreTemps = this.buildTyreTempsSection(car);
        const infoPct = car.setup_info_percent ?? 0;
        const thresholds = car.is_player_controlled
            ? { green: 67, yellow: 34 }
            : { green: 80, yellow: 40 };
        const infoChipBlink = infoPct >= 100 ? 'setup-chip-blink' : '';
        let infoChipColor = 'setup-chip-red';
        if (infoPct >= thresholds.green) infoChipColor = 'setup-chip-green';
        else if (infoPct >= thresholds.yellow) infoChipColor = 'setup-chip-yellow';

        return `
            <div class="car-card-v3" data-driver="${car.driver_number}" data-state="${currentState}">
                <header>
                    <div>
                        <div class="driver-topline-v3">
                            <div class="team-dot-v3" style="background:${car.team_color};">${car.driver_number}</div>
                            <div>
                                <div class="driver-tag-v3">${car.driver_name || 'Driver'}</div>
                                <div class="driver-status-line-v3">${driverStatus}</div>
                            </div>
                        </div>
                    </div>
                    <div class="header-pills-v3">
                        <span class="state-pill-v3">${stateDisplay}</span>
                        <span class="setup-chip-v3 ${infoChipColor} ${infoChipBlink}">DATA</span>
                    </div>
                </header>
                ${telemetry}
                <div class="controls-area-v3">
                    <div class="controls-left-v3">
                        <div class="ctrl-row-v3">
                            <div class="ctrl-cell-v3 ctrl-compound-v3">
                                <label>Tyre compound</label>
                                <div class="tyre-row-v3">
                                    <select class="select-compact-v3" data-field="tyre_compound" ${isBox ? '' : 'disabled'}>
                                        ${this.tyreOptions.map(opt => `<option value="${opt.value}" ${opt.value === tyreChoice ? 'selected' : ''}>${opt.label}</option>`).join('')}
                                    </select>
                                    <span class="wear-indicator-v3">${tireHealthPct}%</span>
                                </div>
                            </div>
                            <div class="ctrl-cell-v3 ctrl-fuel-v3">
                                <label>Fuel %</label>
                                <input class="input-compact-v3" type="number" data-field="fuel_percent" min="1" max="100" value="${fuelPercent}" ${isBox ? '' : 'disabled'}>
                            </div>
                            <div class="ctrl-cell-v3 ctrl-stint-v3">
                                <label>Stint laps (${maxStint})</label>
                                <input class="input-compact-v3" type="number" data-field="stint_target_laps" min="1" max="${maxStint}" value="${stintTarget}" ${isBox ? '' : 'disabled'}>
                            </div>
                        </div>
                        <div class="ctrl-row-v3">
                            <div class="ctrl-cell-v3 ctrl-ice-v3">
                                <label>ICE map</label>
                                <select class="select-compact-v3" data-field="ice_mode">
                                    ${this.iceOptions.map(mode => `<option value="${mode}" ${mode === iceMode ? 'selected' : ''}>${mode}</option>`).join('')}
                                </select>
                            </div>
                            <div class="ctrl-cell-v3 ctrl-ers-v3">
                                <label>ERS mode</label>
                                <select class="select-compact-v3" data-field="ers_mode">
                                    ${this.ersOptions.map(mode => `<option value="${mode}" ${mode === ersMode ? 'selected' : ''}>${mode}</option>`).join('')}
                                </select>
                            </div>
                            <div class="ctrl-cell-v3 ctrl-push-v3">
                                <label>Driver push (${paceLevel})</label>
                                <input class="compact-range" type="range" data-field="pace_level" min="1" max="10" value="${paceLevel}">
                            </div>
                        </div>
                    </div>
                    ${tyreTemps}
                </div>
                <div class="car-actions-v3 with-setup">
                    <div class="drive-actions">
                        <button class="btn-send" data-action="send" ${isBox ? '' : 'disabled'}>Send Out</button>
                        <button class="btn-box" data-action="box" ${isBox ? 'disabled' : ''}>Box</button>
                    </div>
                    <button class="btn-setup-v3" data-action="setup" ${isBox ? '' : 'disabled'}>Setup</button>
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
            return `<span class="telemetry-sector-v3 ${status}" aria-label="${key}">${current ? current.toFixed(2) : '--'}</span>`;
        }).join('');

        const tireWear = typeof car.tire_wear === 'number' ? Math.max(0, Math.min(1, car.tire_wear)) : 0;
        const tireHealthPct = Math.round((1 - tireWear) * 100);
        const fuel = Math.round(car.fuel_percent ?? car.player_config?.fuel_percent ?? 100);

        return `
            <div class="telemetry-strip-v3">
                <div class="telemetry-lap-v3" title="Lap delta">
                    <span class="telemetry-label">Lap</span>
                    <span class="telemetry-delta-v3">${deltaLabel}</span>
                </div>
                <div class="telemetry-sectors-v3">
                    ${sectors}
                </div>
                <div class="telemetry-bars-v3">
                    <div class="telemetry-bar-v3" title="Fuel ${fuel}%">
                        <span>Fuel</span>
                        <div class="bar-track"><span style="width:${fuel}%"></span></div>
                    </div>
                    <div class="telemetry-bar-v3" title="Tires ${tireHealthPct}%">
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

    sliderToPhysical(field, sliderVal) {
        const mapping = this.circuitMapping;
        if (!mapping) return sliderVal;
        const cfg = mapping[field];
        if (!cfg) return sliderVal;
        const v = sliderVal / 100;
        if (cfg.min_deg !== undefined) return +(cfg.min_deg + v * (cfg.max_deg - cfg.min_deg)).toFixed(1);
        if (cfg.min_mm !== undefined) return +(cfg.min_mm + v * (cfg.max_mm - cfg.min_mm)).toFixed(1);
        if (cfg.min_pct !== undefined) return +(cfg.min_pct + v * (cfg.max_pct - cfg.min_pct)).toFixed(1);
        if (cfg.min_open !== undefined) return Math.round(cfg.min_open * 100 + v * (cfg.max_open - cfg.min_open) * 100);
        if (cfg.rigidity) return sliderVal;
        return sliderVal;
    }

    getPhysicalRangeLabel(field) {
        const mapping = this.circuitMapping;
        if (!mapping) return '';
        const cfg = mapping[field];
        if (!cfg) return '';
        if (cfg.min_deg !== undefined) return `${cfg.min_deg}°–${cfg.max_deg}°`;
        if (cfg.min_mm !== undefined) return `${cfg.min_mm}–${cfg.max_mm} mm`;
        if (cfg.min_pct !== undefined) return `${cfg.min_pct}%–${cfg.max_pct}%`;
        if (cfg.min_open !== undefined) return `${Math.round(cfg.min_open * 100)}%–${Math.round(cfg.max_open * 100)}%`;
        if (cfg.rigidity) return 'Soft–Stiff';
        return '';
    }

    async fetchCircuitMapping() {
        try {
            const circuitId = this.state?.circuitId || 'default';
            const res = await fetch(`/api/setup/ranges/${circuitId}`);
            if (!res.ok) return;
            const data = await res.json();
            this.circuitMapping = data.mapping || {};
        } catch (err) {
            console.warn('[GarageV3] Failed to load circuit mapping:', err);
        }
    }

    async fetchValidation(driverNumber) {
        try {
            const car = this.state.getPlayerCar(driverNumber);
            if (!car) return null;
            const payload = this.buildSetupPayloadFromDraft(driverNumber, car);
            const circuitId = this.state?.circuitId || 'default';
            const res = await fetch('/api/setup/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ setup: payload, circuit_id: circuitId })
            });
            if (!res.ok) return null;
            const data = await res.json();
            this.lastValidation = data;
            return data;
        } catch (err) {
            console.warn('[GarageV3] Validation fetch failed:', err);
            return null;
        }
    }

    scheduleValidation(driverNumber) {
        if (this.validateTimer) clearTimeout(this.validateTimer);
        this.validateTimer = setTimeout(async () => {
            const result = await this.fetchValidation(driverNumber);
            if (result) this.updateOverlayFeedback(result);
        }, 400);
    }

    updateOverlayFeedback(validation) {
        if (!this.overlayContainer) return;
        const eval_ = validation.evaluation || {};
        const catData = eval_.categories || {};
        const fbRow = this.overlayContainer.querySelector('.setup-fb-row-v3');
        if (fbRow && validation.ok) {
            const scoreEl = fbRow.querySelector('.setup-fb-score-v3');
            if (scoreEl && catData.overall_score != null) {
                scoreEl.textContent = catData.overall_score.toFixed(1);
            }
            const msgEl = fbRow.querySelector('.setup-fb-msg-v3');
            if (msgEl && eval_.message) {
                msgEl.textContent = eval_.message;
            }
        }
        const catsEl = this.overlayContainer.querySelector('.setup-cats-v3');
        if (catsEl && catData.categories) {
            catsEl.innerHTML = this.buildCategoryChips(catData.categories);
        }
    }

    hideSetupFeedback() {
        if (!this.overlayContainer) return;
        const fbRow = this.overlayContainer.querySelector('.setup-fb-row-v3');
        if (fbRow) {
            fbRow.classList.add('no-feedback');
            const scoreEl = fbRow.querySelector('.setup-fb-score-v3');
            if (scoreEl) scoreEl.remove();
            const msgEl = fbRow.querySelector('.setup-fb-msg-v3');
            if (msgEl) msgEl.textContent = 'Apply and complete a hot lap to see updated feedback.';
        }
        const catsEl = this.overlayContainer.querySelector('.setup-cats-v3');
        if (catsEl) catsEl.remove();
    }

    scoreColorClass(score100) {
        if (score100 >= 95) return 'score-fuchsia';
        if (score100 >= 80) return 'score-green';
        if (score100 >= 60) return 'score-yellow';
        if (score100 >= 40) return 'score-orange';
        return 'score-red';
    }

    buildCategoryChips(categories) {
        if (!categories || typeof categories !== 'object') {
            return Object.entries(this.CAT_COLORS).map(([key, color]) => {
                const label = key.charAt(0).toUpperCase() + key.slice(1);
                return `<div class="setup-cat-chip-v3" title="${key}"><div class="setup-cat-dot-v3" style="background:${color}"></div>${label} <span class="setup-cat-val-v3">--</span></div>`;
            }).join('');
        }
        const entries = Object.entries(categories)
            .map(([key, val]) => {
                const score = typeof val === 'number' ? val : (val?.score ?? 0);
                return { key, score: score / 10 };
            })
            .sort((a, b) => b.score - a.score);
        return entries.map(({ key, score }) => {
            const color = this.CAT_COLORS[key] || '#888';
            const label = key.charAt(0).toUpperCase() + key.slice(1);
            return `<div class="setup-cat-chip-v3" title="${key} ${score.toFixed(1)}/10"><div class="setup-cat-dot-v3" style="background:${color}"></div>${label} <span class="setup-cat-val-v3">${score.toFixed(1)}</span></div>`;
        }).join('');
    }

    async buildSetupOverlay(car, isBox) {
        if (!this.overlayContainer) return;
        const driverNumber = car.driver_number;
        const driverName = car.driver_name || `Driver`;

        if (!this.circuitMapping) await this.fetchCircuitMapping();

        const setupState = this.getSetupPayload(car);
        const { values, recommendation } = setupState;
        const hasFeedback = !!car.has_setup_feedback;
        const infoPct = car.setup_info_percent ?? 0;
        const fieldFeedback = hasFeedback ? (recommendation?.fields || {}) : {};
        const catWrapper = recommendation?.categories || {};
        const categories = hasFeedback ? (catWrapper.categories || catWrapper) : {};

        const sliderCards = this.SETUP_GROUPINGS.map(group => {
            const groupLabel = `<div class="setup-grp-label-v3">${group.title}</div>`;
            const cards = group.pairs.map(cfg =>
                this.buildSetupControl(driverNumber, cfg.field, cfg.label, values[cfg.field], fieldFeedback[cfg.field])
            ).join('');
            return groupLabel + cards;
        }).join('');

        let feedbackMsg, score, fbClass, progressHtml;
        if (hasFeedback) {
            feedbackMsg = recommendation?.message || 'Setup feedback available.';
            const rawScore = catWrapper.overall_score ?? recommendation?.score;
            const score100 = typeof rawScore === 'number' ? rawScore : 0;
            score = typeof rawScore === 'number' ? (rawScore > 10 ? (rawScore / 10).toFixed(1) : rawScore.toFixed(1)) : '--';
            this._scoreColorClass = this.scoreColorClass(score100);
            fbClass = '';
            progressHtml = '';
        } else {
            const barColor = infoPct >= 67 ? '#63d59f' : infoPct >= 34 ? '#f5d56a' : '#ff6d6d';
            const pctLabel = Math.round(infoPct);
            if (infoPct <= 0) {
                feedbackMsg = 'Send the car out to collect setup data.';
            } else if (infoPct < 100) {
                feedbackMsg = `Gathering data… ${pctLabel}%`;
            } else {
                feedbackMsg = 'Data ready — box the car for engineer feedback.';
            }
            score = '';
            fbClass = 'no-feedback';
            progressHtml = `<div class="setup-progress-v3"><div class="setup-progress-bar-v3" style="width:${Math.min(pctLabel, 100)}%;background:${barColor}"></div></div>`;
        }
        const circuitLabel = this.state?.circuitId || '';

        this.overlayContainer.dataset.driver = driverNumber;
        this.overlayContainer.classList.add('is-visible');
        this.overlayContainer.classList.remove('is-hiding');
        this.overlayContainer.innerHTML = `
            <div class="setup-panel-v3">
                <div class="setup-hdr-v3">
                    <div>
                        <h4>Setup – #${driverNumber} ${driverName}</h4>
                        <span class="setup-pill-v3">${isBox ? 'In garage' : 'On track'}${circuitLabel ? ' • ' + circuitLabel : ''}</span>
                    </div>
                    <button class="setup-close-v3" data-action="close-setup" aria-label="Close setup">×</button>
                </div>
                <div class="setup-fb-row-v3 ${fbClass}">
                    ${score ? `<span class="setup-fb-score-v3 ${this._scoreColorClass || ''}">${score}</span>` : ''}
                    <span class="setup-fb-msg-v3">${feedbackMsg}</span>
                </div>
                ${progressHtml || ''}
                ${hasFeedback ? `<div class="setup-cats-v3">${this.buildCategoryChips(categories)}</div>` : ''}
                <div class="setup-slider-grid-v3">
                    ${sliderCards}
                </div>
                <div class="setup-foot-v3">
                    <button class="setup-foot-rst-v3" data-action="reset-setup">Reset</button>
                    <button class="setup-foot-apl-v3" data-action="apply-setup">Apply</button>
                </div>
            </div>
        `;
    }

    buildSetupControl(driverNumber, field, label, value, feedback = {}) {
        const physVal = this.sliderToPhysical(field, value);
        const unit = this.PHYS_UNITS[field] || '';
        const rangeLabel = this.getPhysicalRangeLabel(field) || 'No range';
        const statusClass = feedback?.status ? `status-${feedback.status}` : '';
        const deltaLabel = feedback?.delta_label || '';
        return `
            <div class="setup-control-v3 ${statusClass}" data-field="${field}" data-driver="${driverNumber}">
                <div class="setup-control-header-v3">
                    <span>${label}</span>
                    <span class="setup-range-badge-v3">${rangeLabel}</span>
                </div>
                <input type="range" min="0" max="100" value="${value}" data-setup-field="${field}" />
                <div class="setup-control-footer-v3">
                    <span><span class="setup-phys-val-v3">${physVal}</span><span class="setup-phys-unit-v3">${unit}</span></span>
                    <span class="setup-delta-v3 ${statusClass}">${deltaLabel}</span>
                </div>
            </div>
        `;
    }

    updateDataChips() {
        if (!this.cardsContainer) return;
        const cards = this.cardsContainer.querySelectorAll('.car-card-v3');
        cards.forEach(card => {
            const driverNumber = Number(card.dataset.driver);
            const car = this.state.getPlayerCar(driverNumber);
            if (!car) return;
            const chip = card.querySelector('.setup-chip-v3');
            if (!chip) return;
            const pct = car.setup_info_percent ?? 0;
            const thresholds = car.is_player_controlled
                ? { green: 67, yellow: 34 }
                : { green: 80, yellow: 40 };
            chip.classList.remove('setup-chip-red', 'setup-chip-yellow', 'setup-chip-green', 'setup-chip-blink');
            if (pct >= thresholds.green) chip.classList.add('setup-chip-green');
            else if (pct >= thresholds.yellow) chip.classList.add('setup-chip-yellow');
            else chip.classList.add('setup-chip-red');
            if (pct >= 100) chip.classList.add('setup-chip-blink');
        });
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

        const fp = cars.map(c => `${c.driver_number}:${c.state}:${c.total_laps}:${c.current_tire}:${c.tire_age}`).join('|');
        if (!force && fp === this._lastRenderFp) return;
        this._lastRenderFp = fp;

        this.cardsContainer.innerHTML = cars.map(car => this.buildCarCard(car)).join('');
        this.updateDataChips();
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
            const panel = this.overlayContainer.querySelector('.setup-panel-v3');
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
        // V3: Dock stays normal, overlay is fixed position
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
        if (!carPayload || typeof carPayload !== 'object') {
            console.warn('[GarageV3] Invalid car payload');
            return;
        }
        const existing = this.state.getPlayerCar(driverNumber) || {};
        const updated = { ...existing, ...carPayload };
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
            console.log('[GarageV3] Sending car out:', driverNumber);
            const res = await fetch(`/api/player/car/${driverNumber}/send_out`, { method: 'POST' });
            const data = await res.json();
            console.log('[GarageV3] Send out response:', data);
            if (!res.ok) throw new Error(data.error || 'Send out failed');
            this.setStatus(`Car #${driverNumber} released.`, 'success');
            if (data.car) {
                this.applyLocalCarState(driverNumber, data.car);
            } else {
                console.warn('[GarageV3] No car data in response, updating state manually');
                const car = this.state.getPlayerCar(driverNumber);
                if (car) {
                    car.state = 'OUT_LAP';
                    car.is_on_track = true;
                    this.state.setPlayerCar(car);
                }
            }
            this.render(true);
            return true;
        } catch (err) {
            console.error('[GarageV3] Send out error:', err);
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
        const card = actionBtn.closest('.car-card-v3');
        const driverNumber = Number(card?.dataset.driver);
        if (!driverNumber) {
            console.error('[GarageV3] No driver number found');
            return;
        }
        const state = card.dataset.state;
        const action = actionBtn.dataset.action;
        
        console.log('[GarageV3] Click:', action, 'driver:', driverNumber, 'state:', state);

        if (action === 'send') {
            if (state !== 'BOX') {
                this.setStatus('Car already on track. Box first to change tyres/fuel.', 'error');
                return;
            }
            // Disable button immediately to prevent double-press
            actionBtn.disabled = true;
            const payload = this.collectCardPayload(card);
            console.log('[GarageV3] Sending config:', payload);
            this.sendPlayerConfig(driverNumber, payload, state).then(configured => {
                console.log('[GarageV3] Config result:', configured);
                if (configured) {
                    console.log('[GarageV3] Calling sendPlayerCarOut for driver:', driverNumber);
                    this.sendPlayerCarOut(driverNumber).then(result => {
                        console.log('[GarageV3] Send out result:', result);
                    });
                } else {
                    actionBtn.disabled = false; // Re-enable on config failure
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
        const card = target.closest('.car-card-v3');
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
        const container = forcedContainer || event.target.closest('.car-card-v3');
        if (!container) return;
        const driverNumber = forcedDriverNumber || Number(container.dataset.driver);
        if (!driverNumber) return;
        const value = Number(event.target.value);
        const draft = this.getSetupDraft(driverNumber);
        draft[setupField] = value;
        const control = event.target.closest('.setup-control-v3');
        if (control) {
            const physEl = control.querySelector('.setup-phys-val-v3');
            if (physEl) physEl.textContent = this.sliderToPhysical(setupField, value);
            const deltaEl = control.querySelector('.setup-delta-v3');
            if (deltaEl) deltaEl.textContent = '';
            control.className = 'setup-control-v3';
        }
        this.hideSetupFeedback();
    }

    async submitSetupConfig(driverNumber, setupPayload, state) {
        if (state !== 'BOX') {
            this.setStatus('Bring the car into the garage to edit the setup.', 'error');
            return;
        }
        try {
            const res = await fetch(`/api/player/car/${driverNumber}/setup/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ setup: setupPayload })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Setup update failed');
            this.setStatus(`Setup saved for #${driverNumber}.`, 'success');
            if (data.car) {
                this.applyLocalCarState(driverNumber, data.car);
            } else {
                this.applySetupLocally(driverNumber, setupPayload);
            }
            this.resetSetupDraft(driverNumber);
            const latestCar = data.car || this.state.getPlayerCar(driverNumber);
            const currentState = latestCar ? this.getCarState(latestCar) : state;
            if (currentState === 'BOX') {
                this.toggleSetupOverlay(driverNumber, false);
            } else {
                this.buildSetupOverlay(latestCar, currentState === 'BOX');
            }
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
