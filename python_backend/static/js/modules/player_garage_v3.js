export class PlayerGarageV3 {
    constructor(state, { teamLabel, statusMsg, cardsContainer, overlayContainer, dockElement, notificationsContainer, hudContainer, sessionControls }) {
        this.state = state;
        this.teamLabel = teamLabel;
        this.statusMsg = statusMsg;
        this.cardsContainer = cardsContainer;
        this.overlayContainer = overlayContainer;
        this.dockElement = dockElement;
        this.notificationsContainer = notificationsContainer;
        this.hudContainer = hudContainer;
        this.sessionControls = sessionControls;
        this.wasPausedBeforePU = null;
        this.activePuTab = 'stats';
        this.ersEditorState = new Map();
        this.ERS_BUCKET_SETTINGS = {
            primary: {
                label: 'Primary Bucket',
                title: 'Main straights',
                min: 0,
                max: 80,
                defaultPct: 50,
                pillLabel: 'SOC focus',
            },
            secondary: {
                label: 'Secondary Bucket',
                title: 'Medium corners',
                min: 0,
                max: 70,
                defaultPct: 35,
                pillLabel: 'Clip risk',
            },
            exit: {
                label: 'Exit Bucket',
                title: 'Corner exits',
                min: 5,
                max: 60,
                defaultPct: 15,
                pillLabel: 'MGU-H assist',
            },
        };
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
            'front_wing', 'rear_wing', 'beam_wing',
            'ride_height_front', 'ride_height_rear',
            'suspension_front', 'suspension_rear',
            'antiroll_front', 'antiroll_rear',
            'brake_balance', 'brake_duct'
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
        this.hudTimers = new WeakMap();
        this.pendingSendDrivers = new Set();
        this.lastDriverFeedback = new Map();
        this.RUNTIME_FIELDS = new Set(['pace_level', 'ice_mode', 'ers_mode']);
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
                        this.handleOverlayAction(driver, actionBtn.dataset.action, actionBtn);
                    }
                }
            });
            this.overlayContainer.addEventListener('input', (event) => {
                if (event.target.dataset.setupField) {
                    const driver = Number(this.overlayContainer.dataset.driver);
                    if (driver) {
                        this.handleSetupInput(event, driver, this.overlayContainer);
                    }
                }
                if (event.target.dataset.ersBucket) {
                    this.handleErsBucketInput(event);
                }
            });
            this.overlayContainer.addEventListener('change', (event) => {
                if (event.target.dataset.ersLock) {
                    this.handleErsLockChange(event);
                } else if (event.target.dataset.ersAutoBalance) {
                    this.handleErsAutoBalanceChange(event);
                } else if (event.target.dataset.ersBucket) {
                    this.handleErsBucketInput(event, { forceRefresh: true });
                }
            });
        }
    }

    buildLapUsageChipRow({ mapName, deployLimit, harvestLimit, deployPerLap, harvestPerLap, mguhDirectBudget, current, previous, hasPrevTrace, hasPrevWarnings, hasPrevLap }) {
        const chips = [];
        if (current) {
            chips.push(this.buildLapUsageChip({
                label: 'Giro attuale',
                lapIndex: current.lapIndex,
                deploy: current.deploy,
                harvest: current.harvest,
                mguhDirect: current.mguhDirect,
                mguhHarvest: current.mguhHarvest,
                deployBudget: deployPerLap,
                harvestBudget: harvestPerLap,
                deployLimit,
                harvestLimit,
                mapName,
                mguhDirectBudget,
            }));
        }
        const showPrev = previous && (
            hasPrevLap ||
            (previous.deploy ?? 0) > 0.001 ||
            (previous.harvest ?? 0) > 0.001 ||
            hasPrevTrace ||
            hasPrevWarnings
        );
        if (showPrev) {
            chips.push(this.buildLapUsageChip({
                label: 'Giro precedente',
                lapIndex: previous.lapIndex,
                deploy: previous.deploy,
                harvest: previous.harvest,
                mguhDirect: previous.mguhDirect,
                mguhHarvest: previous.mguhHarvest,
                deployBudget: deployPerLap,
                harvestBudget: harvestPerLap,
                deployLimit,
                harvestLimit,
                mapName,
                mguhDirectBudget,
            }));
        }
        if (!chips.length) return '';
        return `<div class="pu-lap-chip-row-v3">${chips.join('')}</div>`;
    }


    formatErsWarning(message) {
        if (!message) return '';
        return message.replace(/_/g, ' ').replace(/:/, ' · ').toUpperCase();
    }

    formatPercentage(value, digits = 0) {
        if (typeof value !== 'number' || Number.isNaN(value)) return null;
        const pct = value > 1 ? value : value * 100;
        return `${pct.toFixed(digits)}%`;
    }

    resolveBudgetValue(runtimeValue, configValue, fallback = 0) {
        if (typeof runtimeValue === 'number' && !Number.isNaN(runtimeValue) && runtimeValue > 1e-5) {
            return runtimeValue;
        }
        if (typeof configValue === 'number' && !Number.isNaN(configValue)) {
            return configValue;
        }
        return fallback;
    }

    buildErsBucketCard(entry) {
        const target = typeof entry.targetTotal === 'number' ? entry.targetTotal : 0;
        const used = typeof entry.used === 'number' ? entry.used : 0;
        const usedPct = target > 1e-3 ? Math.min((used / target) * 100, 999) : 0;
        const remaining = Math.max(target - used, 0);
        const pctLabel = entry.pctLabel ? entry.pctLabel : null;
        return `
            <div class="ers-bucket-card">
                <strong>${entry.label}</strong>
                <div>${target.toFixed(2)} MJ${pctLabel ? ` • ${pctLabel}` : ''}</div>
                <div style="font-size:11px; color:#96a0b3;">${entry.description}</div>
                <div class="ers-bucket-bar"><span style="width:${Math.min(usedPct, 100)}%"></span></div>
                <div class="ers-bucket-usage">Used ${used.toFixed(2)} MJ${target > 1e-3 ? ` (${usedPct.toFixed(0)}%)` : ''} · Reserve ${remaining.toFixed(2)} MJ</div>
            </div>
        `;
    }

    handleErsBucketInput(event, { forceRefresh = false } = {}) {
        const bucketKey = event.target?.dataset?.ersBucket;
        if (!bucketKey) return;
        const driverNumber = Number(this.overlayContainer?.dataset?.driver);
        if (!driverNumber) return;
        const state = this.ersEditorState.get(driverNumber);
        if (!state) return;
        const bucket = state.buckets?.[bucketKey];
        if (!bucket) return;
        const rawValue = Number(event.target.value);
        if (!Number.isFinite(rawValue)) return;
        const car = this.state.getPlayerCar(driverNumber);
        const puStats = car?.pu_stats || {};
        bucket.pct = this.clampNumber(rawValue, bucket.min, bucket.max);
        if (state.autoBalance) {
            this.normalizeErsBuckets(state, bucketKey);
            this.enforceErsTotalConstraint(state, bucketKey);
        }
        this.syncErsBucketCards(state, puStats);
        if (forceRefresh || event.type !== 'input') {
            this.refreshErsEditorPanel(driverNumber);
        }
    }

    handleErsLockChange(event) {
        const bucketKey = event.target?.dataset?.ersLock;
        if (!bucketKey) return;
        const driverNumber = Number(this.overlayContainer?.dataset?.driver);
        if (!driverNumber) return;
        const state = this.ersEditorState.get(driverNumber);
        if (!state || !state.buckets?.[bucketKey]) return;
        state.buckets[bucketKey].locked = event.target.checked;
        if (state.autoBalance) {
            this.normalizeErsBuckets(state, bucketKey);
        }
        this.refreshErsEditorPanel(driverNumber);
    }

    handleErsAutoBalanceChange(event) {
        if (!event.target?.dataset?.ersAutoBalance) return;
        const driverNumber = Number(this.overlayContainer?.dataset?.driver);
        if (!driverNumber) return;
        const state = this.ersEditorState.get(driverNumber);
        if (!state) return;
        state.autoBalance = !!event.target.checked;
        if (state.autoBalance) {
            this.normalizeErsBuckets(state, null, true);
        }
        this.refreshErsEditorPanel(driverNumber);
    }

    initializeErsEditorState(driverNumber, puStats = {}, { force = false } = {}) {
        if (!driverNumber) return null;
        let state = this.ersEditorState.get(driverNumber);
        if (!state || force) {
            state = this.buildErsEditorDefaults(puStats);
            this.ersEditorState.set(driverNumber, state);
        }
        return state;
    }

    buildErsEditorDefaults(puStats = {}) {
        const deployLimit = puStats.deploy_limit_mj || 4.0;
        const deployBudget = this.resolveBudgetValue(puStats.deploy_budget_total_mj, puStats.deploy_mj_per_lap, deployLimit);
        const pctFromStats = (key) => {
            const statKey = `bucket_${key}_pct`;
            const direct = puStats[statKey];
            if (typeof direct === 'number' && !Number.isNaN(direct)) {
                return direct > 1 ? direct : direct * 100;
            }
            const bucketTotal = puStats[`bucket_${key}_total_mj`];
            if (typeof bucketTotal === 'number' && deployBudget > 1e-6) {
                return (bucketTotal / deployBudget) * 100;
            }
            return null;
        };

        const buckets = {};
        Object.keys(this.ERS_BUCKET_SETTINGS).forEach(key => {
            const cfg = this.ERS_BUCKET_SETTINGS[key];
            const pct = this.clampNumber(pctFromStats(key) ?? cfg.defaultPct, cfg.min, cfg.max);
            buckets[key] = {
                ...cfg,
                pct,
                locked: false,
            };
        });

        const state = {
            buckets,
            autoBalance: true,
        };
        this.normalizeErsBuckets(state, null, true);
        state.initial = {
            autoBalance: state.autoBalance,
            buckets: this.cloneErsBuckets(state.buckets),
        };
        return state;
    }

    cloneErsBuckets(buckets = {}) {
        return Object.entries(buckets).reduce((acc, [key, bucket]) => {
            acc[key] = { ...bucket };
            return acc;
        }, {});
    }

    resetErsEditorState(driverNumber, puStats = {}) {
        let state = this.ersEditorState.get(driverNumber);
        if (!state) {
            state = this.initializeErsEditorState(driverNumber, puStats, { force: true });
            return state;
        }
        const defaults = state.initial || this.buildErsEditorDefaults(puStats);
        state.autoBalance = defaults.autoBalance;
        state.buckets = this.cloneErsBuckets(defaults.buckets);
        return state;
    }

    refreshErsEditorPanel(driverNumber) {
        if (!this.overlayContainer) return;
        const ersPanel = this.overlayContainer.querySelector('section[data-panel="ers-map"]');
        if (!ersPanel) return;
        const car = this.state.getPlayerCar(driverNumber);
        if (!car) return;
        const puStats = car.pu_stats || {};
        const isBox = this.getCarState(car) === 'BOX';
        ersPanel.innerHTML = this.buildErsMapPanel(car, puStats, isBox);
    }

    syncErsBucketCards(state, puStats = {}) {
        if (!state || !this.overlayContainer) return;
        const panel = this.overlayContainer.querySelector('section[data-panel="ers-map"]');
        if (!panel) return;
        const formatMJ = (value) => (typeof value === 'number' && !Number.isNaN(value) ? `${value.toFixed(2)} MJ` : '-- MJ');
        const deployLimit = puStats.deploy_limit_mj || 4.0;
        const deployBudget = this.resolveBudgetValue(puStats.deploy_budget_total_mj, puStats.deploy_mj_per_lap, deployLimit);
        const socTarget = typeof puStats.soc_target_pct === 'number' && puStats.soc_target_pct > 0
            ? Math.round(puStats.soc_target_pct * 100)
            : (typeof puStats.target_soc_end_lap === 'number' ? Math.round(puStats.target_soc_end_lap * 100) : '--');

        Object.keys(this.ERS_BUCKET_SETTINGS).forEach(key => {
            const card = panel.querySelector(`.ers-bucket-card[data-bucket="${key}"]`);
            if (!card) return;
            const cfg = this.ERS_BUCKET_SETTINGS[key];
            const bucket = state.buckets?.[key] || cfg;
            const pctValue = this.clampNumber(bucket.pct ?? cfg.defaultPct, cfg.min, cfg.max);
            const slider = card.querySelector('.ers-bucket-slider');
            if (slider) {
                slider.value = pctValue.toFixed(0);
            }
            const chip = card.querySelector('.percent-chip');
            if (chip) {
                chip.textContent = `${pctValue.toFixed(0)}%`;
            }
            const targetDeploy = deployBudget > 0 ? (deployBudget * (pctValue / 100)) : 0;
            const runtimeDeploy = puStats[`bucket_${key}_used_mj`] ?? 0;
            const valueRow = card.querySelectorAll('.value-row span');
            if (valueRow[0]) {
                valueRow[0].textContent = `Target deploy: ${formatMJ(targetDeploy)}`;
            }
            if (valueRow[1]) {
                valueRow[1].textContent = `Realtime: ${formatMJ(runtimeDeploy)}`;
            }
            const lockInput = card.querySelector('[data-ers-lock]');
            if (lockInput) {
                lockInput.checked = !!bucket.locked;
            }
            const pill = card.querySelector('.target-pill');
            if (pill) {
                const mguhRealtime = puStats[`mguh_${key}_used_mj`];
                pill.textContent = this.resolveBucketPillLabel(key, { socTarget, mguhRealtime });
            }
        });

        const totalChip = panel.querySelector('.ers-toolbar-summary strong');
        if (totalChip) {
            totalChip.textContent = `Total ${Math.round(this.sumErsBucketPct(state))}%`;
        }
    }

    normalizeErsBuckets(state, excludeKey = null, force = false) {
        if (!state) return;
        if (!state.autoBalance && !force) return;
        for (let i = 0; i < 6; i += 1) {
            const total = this.sumErsBucketPct(state);
            const diff = total - 100;
            if (!Number.isFinite(diff) || Math.abs(diff) < 0.01) {
                break;
            }
            const adjustableEntries = Object.entries(state.buckets).filter(([key, bucket]) => key !== excludeKey && !bucket.locked);
            if (!adjustableEntries.length) break;
            const needReduce = diff > 0;
            const capacity = adjustableEntries.reduce((sum, [, bucket]) => {
                const span = needReduce ? (bucket.pct - bucket.min) : (bucket.max - bucket.pct);
                return sum + Math.max(span, 0);
            }, 0);
            if (capacity <= 0) break;
            adjustableEntries.forEach(([key, bucket]) => {
                const span = needReduce ? (bucket.pct - bucket.min) : (bucket.max - bucket.pct);
                if (span <= 0) return;
                const share = span / capacity;
                const adjustment = diff * share;
                bucket.pct = this.clampNumber(bucket.pct - adjustment, bucket.min, bucket.max);
            });
        }
    }

    sumErsBucketPct(state) {
        if (!state || !state.buckets) return 0;
        return Object.values(state.buckets).reduce((sum, bucket) => sum + (Number.isFinite(bucket.pct) ? bucket.pct : 0), 0);
    }

    enforceErsTotalConstraint(state, bucketKey, tolerance = 0.05) {
        if (!state || !state.buckets) return;
        const bucket = state.buckets[bucketKey];
        if (!bucket) return;
        const total = this.sumErsBucketPct(state);
        const diff = total - 100;
        if (Math.abs(diff) <= tolerance) return;
        const adjusted = this.clampNumber(bucket.pct - diff, bucket.min, bucket.max);
        bucket.pct = adjusted;
        const remainingDiff = this.sumErsBucketPct(state) - 100;
        if (Math.abs(remainingDiff) > tolerance) {
            this.normalizeErsBuckets(state, bucketKey, true);
        }
    }

    clampNumber(value, min = -Infinity, max = Infinity) {
        const numeric = Number(value);
        if (!Number.isFinite(numeric)) return min;
        return Math.max(min, Math.min(max, numeric));
    }

    resolveBucketPillLabel(key, { socTarget, mguhRealtime } = {}) {
        const cfg = this.ERS_BUCKET_SETTINGS[key] || {};
        const base = cfg.pillLabel || 'Bucket';
        let detail = 'Balanced';
        if (key === 'primary') {
            if (typeof socTarget === 'number' && !Number.isNaN(socTarget)) {
                if (socTarget >= 60) detail = 'Push';
                else if (socTarget >= 48) detail = 'Balanced';
                else detail = 'Save';
            }
        } else if (key === 'secondary') {
            if (typeof mguhRealtime === 'number' && mguhRealtime > 0) {
                detail = mguhRealtime > 0.6 ? 'High' : mguhRealtime > 0.25 ? 'Medium' : 'Low';
            } else {
                detail = 'Low';
            }
        } else if (key === 'exit') {
            if (typeof mguhRealtime === 'number' && mguhRealtime > 0) {
                detail = `${mguhRealtime.toFixed(2)} MJ`;
            } else {
                detail = 'Assist on';
            }
        }
        return `${base}: ${detail}`;
    }

    buildErsMapPanel(car, puStats, isBox) {
        if (!puStats || !Object.keys(puStats).length) {
            return '<div class="ers-editor-panel-empty">No ERS telemetry available yet.</div>';
        }
        const formatMJ = (value, digits = 2) => (typeof value === 'number' && !Number.isNaN(value) ? `${value.toFixed(digits)} MJ` : '-- MJ');
        const driverNumber = car?.driver_number;
        const editorState = driverNumber ? this.initializeErsEditorState(driverNumber, puStats) : null;
        if (!editorState) {
            return '<div class="ers-editor-panel-empty">ERS editor unavailable.</div>';
        }
        const bucketState = editorState.buckets || {};
        const autoBalanceEnabled = editorState.autoBalance !== false;

        const mapName = puStats.map || 'STANDARD';
        const lapDeploy = typeof puStats.lap_deploy_mj === 'number' ? puStats.lap_deploy_mj : 0;
        const deployLimit = puStats.deploy_limit_mj || 4.0;
        const deployBudget = this.resolveBudgetValue(puStats.deploy_budget_total_mj, puStats.deploy_mj_per_lap, deployLimit);
        const defenseReserve = this.resolveBudgetValue(puStats.defense_reserve_available_mj, puStats.defense_reserve_mj_config, 0);
        const lastAllocation = typeof puStats.last_bucket_allocated_mj === 'number' ? puStats.last_bucket_allocated_mj : 0;
        const defenseReservePct = deployBudget > 1e-6 ? `${Math.round((defenseReserve / deployBudget) * 100)}%` : '--';
        const socFloor = typeof puStats.soc_floor_dynamic_pct === 'number' && puStats.soc_floor_dynamic_pct > 0 ? Math.round(puStats.soc_floor_dynamic_pct * 100) : '--';
        const socTarget = typeof puStats.soc_target_pct === 'number' && puStats.soc_target_pct > 0
            ? Math.round(puStats.soc_target_pct * 100)
            : (typeof puStats.target_soc_end_lap === 'number' ? Math.round(puStats.target_soc_end_lap * 100) : '--');
        const totalPct = Math.round(this.sumErsBucketPct(editorState));
        const playerErsMode = car?.player_config?.ers_mode || car?.ers_mode || 'Neutral';
        const driverName = car?.driver_name || `Driver #${driverNumber || '—'}`;
        const autoBalanceLabel = autoBalanceEnabled ? 'Auto-balance unlocked buckets' : 'Manual balance';

        const bucketCards = Object.keys(this.ERS_BUCKET_SETTINGS).map(key => {
            const cfg = this.ERS_BUCKET_SETTINGS[key];
            const bucket = bucketState[key] || cfg;
            const pctValue = this.clampNumber(bucket.pct ?? cfg.defaultPct, cfg.min, cfg.max);
            const targetDeploy = deployBudget > 0 ? (deployBudget * (pctValue / 100)) : 0;
            const runtimeDeploy = puStats[`bucket_${key}_used_mj`] ?? 0;
            const mguhRealtime = puStats[`mguh_${key}_used_mj`];
            const pillText = this.resolveBucketPillLabel(key, { socTarget, mguhRealtime });
            return `
                <div class="ers-bucket-card" data-bucket="${key}">
                    <div class="ers-bucket-header-row">
                        <div>
                            <div class="sublabel">${cfg.label}</div>
                            <div class="bucket-title">${cfg.title}</div>
                        </div>
                        <div class="percent-chip">${pctValue.toFixed(0)}%</div>
                    </div>
                    <input type="range" class="ers-bucket-slider" value="${pctValue.toFixed(0)}" min="${cfg.min}" max="${cfg.max}" data-ers-bucket="${key}" step="1">
                    <div class="value-row">
                        <span>Target deploy: ${formatMJ(targetDeploy)}</span>
                        <span>Realtime: ${formatMJ(runtimeDeploy)}</span>
                    </div>
                    <div class="lock-row">
                        <label><input type="checkbox" data-ers-lock="${key}" ${bucket.locked ? 'checked' : ''}>Lock percentage</label>
                        <span class="target-pill">${pillText}</span>
                    </div>
                </div>
            `;
        }).join('');

        const toolbarHtml = `
            <section class="ers-controls-tile">
                <h3>Totals & Actions</h3>
                <div class="ers-bucket-toolbar">
                    <div class="ers-toolbar-summary">
                        <strong>Total ${totalPct}%</strong>
                        <label><input type="checkbox" data-ers-auto-balance="true" ${autoBalanceEnabled ? 'checked' : ''}>${autoBalanceLabel}</label>
                    </div>
                    <div class="ers-toolbar-actions">
                        <button class="ghost-btn" type="button" data-action="ers-reset">Reset preset</button>
                        <button class="primary-btn" type="button" disabled title="Custom saves coming soon">Save custom map</button>
                    </div>
                </div>
            </section>
        `;

        return `
            <div class="ers-editor-panel">
                <div class="ers-editor-grid-shell">
                    <div class="ers-sidebar-stack">
                        <section class="ers-budget-tile">
                            <h3>Budget & Split</h3>
                            <div class="ers-budget-list">
                                <div class="ers-budget-row"><span>Deploy budget</span><strong>${formatMJ(deployBudget)}</strong></div>
                                <div class="ers-budget-row"><span>Deploy on track</span><strong>${formatMJ(lapDeploy)}</strong></div>
                                <div class="ers-budget-row"><span>Defense reserve</span><strong>${formatMJ(defenseReserve)} (${defenseReservePct})</strong></div>
                                <div class="ers-budget-row"><span>Last allocation</span><strong>${formatMJ(lastAllocation)}</strong></div>
                            </div>
                            <div class="ers-budget-row ers-metrics">
                                <div>
                                    <div class="label">SOC floor</div>
                                    <strong>${socFloor === '--' ? '--' : `${socFloor}%`}</strong>
                                </div>
                                <div>
                                    <div class="label">Target lap end</div>
                                    <strong>${socTarget === '--' ? '--' : `${socTarget}%`}</strong>
                                </div>
                            </div>
                            <div class="ers-note-bar">
                                <span>Preset: ${mapName} · ${playerErsMode}</span>
                                <span>Total deploy ${formatMJ(deployBudget)}</span>
                                <span>Sum must equal 100% (currently ${totalPct}%)</span>
                            </div>
                        </section>
                        ${toolbarHtml}
                    </div>
                    <section class="ers-bucket-editor">
                        <div class="ers-bucket-header">
                            <div>
                                <div class="sublabel">ERS MAP</div>
                                <div class="ers-map-title">${mapName} · ${playerErsMode}</div>
                                <div class="ers-map-subtitle">${driverName} · ${isBox ? 'In garage' : 'On track'}</div>
                            </div>
                            <div class="ers-bucket-tabs">
                                <div class="map-pill active">Preset</div>
                                <div class="map-pill">Custom</div>
                                <div class="map-pill">Import</div>
                            </div>
                        </div>
                        <div class="ers-editor-grid">
                            ${bucketCards}
                        </div>
                    </section>
                </div>
            </div>
        `;
    }

    buildLapUsageChip({ label, lapIndex, deploy, harvest, deployBudget, harvestBudget, deployLimit, harvestLimit, mapName, mguhDirect, mguhDirectBudget, mguhHarvest }) {
        if (deploy == null && harvest == null) return '';
        const lapLabel = this.formatLapLabel(lapIndex);
        const deployText = deploy != null ? `${deploy.toFixed(2)} MJ` : '—';
        const harvestText = harvest != null ? `${harvest.toFixed(2)} MJ` : '—';
        const deployRatio = deployBudget ? Math.min((deploy || 0) / deployBudget, 1) : 0;
        const harvestRatio = harvestBudget ? Math.min((harvest || 0) / harvestBudget, 1) : 0;
        const formatTargetPct = (ratio, budget) => `${Math.round(ratio * 100)}% of ${budget.toFixed(2)} MJ`;
        const deployPctLabel = deployBudget ? formatTargetPct(deployRatio, deployBudget) : (deploy ? '—' : '0%');
        const harvestPctLabel = harvestBudget ? formatTargetPct(harvestRatio, harvestBudget) : (harvest ? '—' : '0%');
        const mguhValue = typeof mguhDirect === 'number' ? mguhDirect : 0;
        const hasMguhBudget = typeof mguhDirectBudget === 'number' && mguhDirectBudget > 1e-4;
        const mguhRatio = hasMguhBudget ? Math.min(mguhValue / mguhDirectBudget, 1) : 0;
        const showMguh = hasMguhBudget;
        const mguhPctLabel = showMguh ? formatTargetPct(mguhRatio, mguhDirectBudget) : '';
        const mguhText = `${mguhValue.toFixed(2)} MJ`;
        const mguhHarvestValue = typeof mguhHarvest === 'number' ? mguhHarvest : 0;
        const hasHarvestBudget = harvestBudget > 1e-5;
        const mguhHarvestRatio = hasHarvestBudget ? Math.min(mguhHarvestValue / harvestBudget, 1) : 0;
        const showMguhHarvest = hasHarvestBudget && mguhHarvestValue > 1e-4;
        const mguhHarvestPctLabel = showMguhHarvest ? formatTargetPct(mguhHarvestRatio, harvestBudget) : '';
        const mguhHarvestText = `${mguhHarvestValue.toFixed(2)} MJ`;
        const combinedDeployRatio = deployRatio + (showMguh ? mguhRatio : 0);
        const combinedScale = combinedDeployRatio > 1 ? (1 / combinedDeployRatio) : 1;
        const deployCombinedPct = deployRatio * combinedScale * 100;
        const mguhCombinedPct = showMguh ? mguhRatio * combinedScale * 100 : 0;
        const combinedHarvestRatio = harvestRatio + (showMguhHarvest ? mguhHarvestRatio : 0);
        const harvestScale = combinedHarvestRatio > 1 ? (1 / combinedHarvestRatio) : 1;
        const harvestCombinedPct = harvestRatio * harvestScale * 100;
        const mguhHarvestCombinedPct = showMguhHarvest ? mguhHarvestRatio * harvestScale * 100 : 0;
        const mguhLegend = showMguh
            ? `<div class="pu-chip-submetric">MGU-H Direct ${mguhText} <span class="pu-chip-percent">${mguhPctLabel}</span></div>`
            : '';
        const mguhHarvestLegend = showMguhHarvest
            ? `<div class="pu-chip-submetric">MGU-H → ES ${mguhHarvestText} <span class="pu-chip-percent">${mguhHarvestPctLabel}</span></div>`
            : '';
        return `
            <div class="pu-lap-chip-v3">
                <div class="pu-chip-header">
                    <span class="pu-chip-label">${label}</span>
                    <span class="pu-chip-lap">${lapLabel}</span>
                </div>
                <div class="pu-chip-body">
                    <div class="pu-chip-metric">
                        <div class="pu-chip-metric-label">Deploy</div>
                        <div class="pu-chip-metric-value">${deployText} <span class="pu-chip-percent">${deployPctLabel}</span></div>
                        <div class="pu-chip-progress combined">
                            <div class="pu-chip-progress-bar deploy" style="width:${deployCombinedPct}%"></div>
                            ${showMguh ? `<div class="pu-chip-progress-bar mguh" style="width:${mguhCombinedPct}%; left:${deployCombinedPct}%"></div>` : ''}
                        </div>
                        ${mguhLegend}
                    </div>
                    <div class="pu-chip-metric">
                        <div class="pu-chip-metric-label">Harvest</div>
                        <div class="pu-chip-metric-value">${harvestText} <span class="pu-chip-percent">${harvestPctLabel}</span></div>
                        <div class="pu-chip-progress combined harvest">
                            <div class="pu-chip-progress-bar harvest" style="width:${harvestCombinedPct}%"></div>
                            ${showMguhHarvest ? `<div class="pu-chip-progress-bar mguh-harvest" style="width:${mguhHarvestCombinedPct}%; left:${harvestCombinedPct}%"></div>` : ''}
                        </div>
                        ${mguhHarvestLegend}
                    </div>
                </div>
                <div class="pu-chip-footer">
                    <span>Map ${mapName}</span>
                    <span>Deploy limit ${deployLimit.toFixed(1)} · Harvest ${harvestLimit.toFixed(1)} MJ</span>
                </div>
            </div>
        `;
    }

    buildWarningSection({ currentWarnings = [], previousWarnings = [], currentLapIndex, previousLapIndex }) {
        const currentBadges = this.buildWarningBadges(currentWarnings, currentLapIndex, 'Giro attuale');
        const previousBadges = this.buildWarningBadges(previousWarnings, previousLapIndex, 'Giro precedente');
        if (!currentBadges && !previousBadges) {
            return '<div class="pu-warning-row-v3"><div class="pu-warning-empty">No runtime warnings</div></div>';
        }
        return `<div class="pu-warning-row-v3">${currentBadges || ''}${previousBadges || ''}</div>`;
    }

    buildWarningBadges(warnings, lapIndex, label) {
        if (!warnings || !warnings.length) return '';
        const lapText = this.formatLapLabel(lapIndex, true);
        const unique = [...new Set(warnings)];
        return unique.map(w => {
            const isDeploy = w.includes('deploy');
            const tone = isDeploy ? 'deploy' : 'harvest';
            return `
                <div class="pu-warning-badge-v3 ${tone}">
                    <div class="pu-warning-badge-label">${label}${lapText ? ` · ${lapText}` : ''}</div>
                    <div class="pu-warning-badge-title">${w}</div>
                </div>
            `;
        }).join('');
    }

    formatEnergyCell(value, mode = 'neutral', unit = 'MJ') {
        const magnitude = Math.abs(value);
        let level = 'neutral';
        if (magnitude > 0.01) {
            if (mode === 'spend') {
                if (magnitude > 0.8) level = 'spend-high';
                else if (magnitude > 0.3) level = 'spend-mid';
                else level = 'spend-low';
            } else if (mode === 'recovery') {
                if (magnitude > 0.8) level = 'recovery-high';
                else if (magnitude > 0.3) level = 'recovery-mid';
                else level = 'recovery-low';
            }
        }
        const formatted = `${value.toFixed(2)}${unit ? ` ${unit}` : ''}`;
        return `<span class="pu-energy-cell ${level}">${formatted}</span>`;
    }

    buildPUTableRows(currentTrace = [], prevTrace = [], lapIdCurrent, lapIdPrev) {
        const rows = [];
        const pushRows = (entries, lapId, tone) => {
            if (!entries || !entries.length) return;
            entries.slice(-20).forEach(entry => {
                rows.push({
                    lapLabel: this.formatLapLabel(lapId) || (tone === 'prev' ? 'Lap prev' : 'Lap'),
                    section: entry.section_id || '--',
                    deploy: entry.deploy_mj ?? 0,
                    harvest: entry.harvest_mj ?? 0,
                    hydraulic: entry.hydraulic_mj ?? 0,
                    regen: entry.regen_vs_hydraulic ?? 0,
                    mguhDirect: entry.mguh_direct_mj ?? 0,
                    mguhHarvest: entry.mguh_es_mj ?? 0,
                });
            });
        };
        pushRows(currentTrace, lapIdCurrent, 'current');
        pushRows(prevTrace, lapIdPrev, 'prev');
        if (!rows.length) {
            return '<tr><td colspan="8" style="text-align:center;color:#888;">No trace data</td></tr>';
        }
        return rows.map(row => `
            <tr>
                <td>${row.lapLabel}</td>
                <td>${row.section}</td>
                <td>${this.formatEnergyCell(row.deploy, 'spend')}</td>
                <td>${this.formatEnergyCell(row.harvest, 'recovery')}</td>
                <td>${this.formatEnergyCell(row.hydraulic, 'spend')}</td>
                <td>${row.regen.toFixed(2)}</td>
                <td>${this.formatEnergyCell(row.mguhDirect, 'spend')}</td>
                <td>${this.formatEnergyCell(row.mguhHarvest, 'recovery')}</td>
            </tr>
        `).join('');
    }

    resolveLapIndexes({ car, lapIdCurrent, lapIdPrev }) {
        const completedLapCount = Array.isArray(car.lap_times) ? car.lap_times.length : null;
        const normalizeLapId = (value) => {
            if (typeof value !== 'number' || Number.isNaN(value) || value < 0) return null;
            return value;
        };

        let currentLapIndex = normalizeLapId(lapIdCurrent);
        let previousLapIndex = normalizeLapId(lapIdPrev);

        if (currentLapIndex === null && completedLapCount !== null) {
            currentLapIndex = Math.max(completedLapCount, 0);
        }
        if (previousLapIndex === null && completedLapCount !== null) {
            previousLapIndex = completedLapCount > 0 ? completedLapCount - 1 : null;
        }
        if (previousLapIndex === null && currentLapIndex !== null && currentLapIndex > 0) {
            previousLapIndex = currentLapIndex - 1;
        }
        if (currentLapIndex === null) {
            currentLapIndex = 0;
        }

        return {
            currentLapIndex,
            previousLapIndex,
            completedLapCount,
        };
    }

    formatLapLabel(lapIndex, allowEmpty = false) {
        if (typeof lapIndex !== 'number' || Number.isNaN(lapIndex) || lapIndex < 0) {
            return allowEmpty ? '' : 'Lap —';
        }
        return `Lap ${lapIndex}`;
    }

    puStatsSignature(puStats) {
        if (!puStats) return 'pu:none';
        const fields = [
            puStats.soc_mj,
            puStats.soc_pct,
            puStats.lap_deploy_mj,
            puStats.lap_harvest_mj,
            puStats.lap_mguh_direct_mj,
            puStats.lap_mguh_harvest_mj,
            puStats.lap_id_current,
            puStats.lap_id_prev,
        ].map(val => (typeof val === 'number' ? val.toFixed(3) : 'null'));
        return `pu:${fields.join(':')}`;
    }

    brakeCoolingSignature(brakeCooling) {
        if (!brakeCooling || (!brakeCooling.front && !brakeCooling.rear)) {
            return 'bc:none';
        }
        const axes = ['front', 'rear'].map(axis => {
            const data = brakeCooling[axis];
            if (!data) return `${axis}:na`;
            const vals = [
                typeof data.current_open === 'number' ? data.current_open.toFixed(3) : 'null',
                data.status || 'na',
                typeof data.blink_until === 'number' ? data.blink_until.toFixed(2) : 'null'
            ];
            return `${axis}:${vals.join(':')}`;
        });
        return `bc:${axes.join('|')}`;
    }

    brakeThermalSignature(brakeThermal) {
        if (!brakeThermal || (!('front' in brakeThermal) && !('rear' in brakeThermal))) {
            return 'bt:none';
        }
        const thresholds = brakeThermal.thresholds || {};
        const axes = ['front', 'rear'].map(axis => {
            const value = brakeThermal[axis];
            const fade = axis === 'front' ? thresholds.front_c : thresholds.rear_c;
            return `${axis}:${typeof value === 'number' ? value.toFixed(1) : 'na'}:${typeof fade === 'number' ? fade.toFixed(0) : 'na'}`;
        });
        return `bt:${axes.join('|')}`;
    }

    computeLapTotals(trace = [], fallbackDeploy = 0, fallbackHarvest = 0, fallbackMguhDirect = 0, fallbackMguhHarvest = 0) {
        const hasTrace = Array.isArray(trace) && trace.length > 0;
        const totals = trace.reduce((acc, entry) => {
            const deploy = typeof entry.deploy_mj === 'number' ? entry.deploy_mj : 0;
            const harvest = typeof entry.harvest_mj === 'number' ? entry.harvest_mj : 0;
            const mguhDirect = typeof entry.mguh_direct_mj === 'number' ? entry.mguh_direct_mj : 0;
            const mguhHarvest = typeof entry.mguh_es_mj === 'number' ? entry.mguh_es_mj : 0;
            return {
                deploy: acc.deploy + deploy,
                harvest: acc.harvest + harvest,
                mguhDirect: acc.mguhDirect + mguhDirect,
                mguhHarvest: acc.mguhHarvest + mguhHarvest,
            };
        }, { deploy: 0, harvest: 0, mguhDirect: 0, mguhHarvest: 0 });
        const resolveValue = (traceValue, fallbackValue) => {
            const fallbackValid = typeof fallbackValue === 'number';
            if (!hasTrace) return fallbackValid ? fallbackValue : traceValue;
            if (fallbackValid && fallbackValue > traceValue + 1e-4) {
                return fallbackValue;
            }
            return traceValue;
        };

        const deploy = resolveValue(totals.deploy, fallbackDeploy);
        const harvest = resolveValue(totals.harvest, fallbackHarvest);
        const mguhDirect = resolveValue(totals.mguhDirect, fallbackMguhDirect);
        const mguhHarvest = resolveValue(totals.mguhHarvest, fallbackMguhHarvest);
        const hasData = hasTrace || deploy > 0.0005 || harvest > 0.0005 || mguhDirect > 0.0005 || mguhHarvest > 0.0005;
        return { deploy, harvest, mguhDirect, mguhHarvest, hasData, hasTrace };
    }

    setStatus(message, tone = 'info') {
        if (!this.statusMsg) return;
        this.statusMsg.textContent = message || '';
        const baseClass = 'garage-status-line';
        this.statusMsg.className = `${baseClass}${tone ? ' ' + tone : ''}`;
    }

    pushNotification(message, tone = 'info') {
        if (!this.notificationsContainer || !message) return;
        const toast = document.createElement('div');
        toast.className = `garage-toast-v3 ${tone}`;
        toast.textContent = message;
        this.notificationsContainer.appendChild(toast);

        const toasts = this.notificationsContainer.querySelectorAll('.garage-toast-v3');
        const overflow = toasts.length - 2;
        if (overflow > 0) {
            for (let i = 0; i < overflow; i += 1) {
                this.dismissToast(toasts[i], true);
            }
        }

        // Auto-resize toast if text is too long
        const lineHeight = 18;
        const maxLines = 4;
        const maxHeight = lineHeight * maxLines;
        if (toast.scrollHeight > maxHeight) {
            toast.style.maxHeight = `${maxHeight}px`;
            toast.style.overflowY = 'auto';
        }

        const timer = setTimeout(() => this.dismissToast(toast), 4500);
        this.notificationTimers.set(toast, timer);
    }

    dismissToast(toast, immediate = false) {
        if (!toast) return;
        const timer = this.notificationTimers.get(toast);
        if (timer) {
            clearTimeout(timer);
            this.notificationTimers.delete(toast);
        }
        if (immediate) {
            toast.remove();
            return;
        }
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 220);
    }

    pushHudBanner({ title = 'EVENT', body, tone = 'info', duration = 4000 } = {}) {
        if (!this.hudContainer || !body) return;
        const banner = document.createElement('div');
        banner.className = `hud-banner ${tone}`;
        banner.innerHTML = `
            <span class="hud-banner-title">${title}</span>
            <span class="hud-banner-body">${body}</span>
        `;
        this.hudContainer.appendChild(banner);

        const banners = this.hudContainer.querySelectorAll('.hud-banner');
        const overflow = banners.length - 2;
        if (overflow > 0) {
            for (let i = 0; i < overflow; i += 1) {
                this.dismissHudBanner(banners[i], true);
            }
        }

        const timer = setTimeout(() => this.dismissHudBanner(banner), duration);
        this.hudTimers.set(banner, timer);
    }

    dismissHudBanner(banner, immediate = false) {
        if (!banner) return;
        const timer = this.hudTimers.get(banner);
        if (timer) {
            clearTimeout(timer);
            this.hudTimers.delete(banner);
        }
        if (immediate) {
            banner.remove();
            return;
        }
        if (!banner.classList.contains('hide')) {
            banner.classList.add('hide');
            setTimeout(() => banner.remove(), 250);
        }
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

    buildBrakeChipPreview(car) {
        const thermal = car.brake_thermal || {};
        const nowSeconds = Date.now() / 1000;
        const axes = ['front', 'rear'];
        const chips = axes
            .map(axis => this.buildBrakeChip(
                axis,
                this.resolveBrakeAxisData(car, axis, thermal),
                nowSeconds,
            ))
            .join('');
        return `<div class="brake-chip-preview">${chips}</div>`;
    }

    buildBrakeChip(axis, axisData, nowSeconds = Date.now() / 1000) {
        const axisLabel = axis === 'front' ? 'Front' : 'Rear';
        const state = this.getBrakeChipState(axisData, nowSeconds);
        const classes = ['brake-chip-mini', state.statusClass];
        if (state.shouldBlink) classes.push('brake-chip-blink');
        return `
            <span class="${classes.join(' ')}" data-bc-axis="${axis}">
                <span class="bc-axis">${axisLabel}</span>
                <span class="bc-value">${state.valueText}</span>
            </span>
        `;
    }

    resolveBrakeAxisData(car, axis, thermalOverride = null) {
        const thermal = thermalOverride || car.brake_thermal || {};
        const axisValue = thermal[axis];
        if (typeof axisValue !== 'number') return null;

        const thresholds = thermal.thresholds || {};
        const fadeFront = thresholds.front_c;
        const fadeRear = thresholds.rear_c;
        const fadeThreshold = axis === 'front' ? fadeFront : fadeRear;
        const target = this.getBrakeTempTarget(car, axis, fadeThreshold);

        return {
            value_c: axisValue,
            thresholds: {
                fade_c: fadeThreshold,
                target,
            },
        };
    }

    getBrakeTempTarget(car, axis, fadeThreshold) {
        const profileTargets = car.brake_diagnostics?.cooling_targets || {};
        const delta = axis === 'front'
            ? profileTargets.front_delta
            : profileTargets.rear_delta;
        const baseCenter = typeof fadeThreshold === 'number'
            ? fadeThreshold - 80
            : axis === 'front' ? 620 : 520;
        const offset = typeof delta === 'number' ? delta * 100 : 0;
        const center = baseCenter + offset;
        const tolerance = 40;
        return [center - tolerance, center + tolerance];
    }

    getBrakeChipState(axisData, nowSeconds = Date.now() / 1000) {
        if (!axisData) {
            return {
                statusClass: 'brake-chip-na',
                valueText: '--°C',
                shouldBlink: false,
            };
        }

        const value = axisData.value_c;
        const fadeLimit = axisData.thresholds?.fade_c;
        const target = axisData.thresholds?.target;
        const statusClass = this.mapBrakeTempToClass(value, target, fadeLimit);
        const valueText = this.formatTemp(value);
        return {
            statusClass,
            valueText,
            shouldBlink: false,
        };
    }

    mapBrakeTempToClass(value, target, fadeLimit) {
        if (typeof value !== 'number') return 'brake-chip-na';
        if (Array.isArray(target) && target.length >= 2) {
            const [min, max] = target;
            const coldThreshold = min - 40;
            const lowWarnThreshold = min - 20;
            const highWarnThreshold = max + 10;

            if (value < coldThreshold) return 'brake-chip-cold';
            if (value < lowWarnThreshold) return 'brake-chip-warn';
            if (value >= min && value <= max) return 'brake-chip-ok';
            if (value > highWarnThreshold) {
                if (typeof fadeLimit === 'number' && value >= fadeLimit) {
                    return 'brake-chip-bad';
                }
                return 'brake-chip-warn';
            }
        }
        if (typeof fadeLimit === 'number' && value >= fadeLimit) {
            return 'brake-chip-bad';
        }
        if (Array.isArray(target) && target.length >= 2) {
            const [, max] = target;
            if (typeof max === 'number' && value > max) return 'brake-chip-warn';
            const [min] = target;
            if (typeof min === 'number' && value < min) return 'brake-chip-cold';
        }
        return 'brake-chip-warn';
    }

    formatTemp(value) {
        if (typeof value !== 'number' || Number.isNaN(value)) return '--°C';
        return `${Math.round(value)}°C`;
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
        const brakeChipPreview = this.buildBrakeChipPreview(car);
        const infoPct = car.setup_info_percent ?? 0;
        const thresholds = car.is_player_controlled
            ? { green: 67, yellow: 34 }
            : { green: 80, yellow: 40 };
        const infoChipBlink = infoPct >= 100 ? 'setup-chip-blink' : '';
        let infoChipColor = 'setup-chip-red';
        if (infoPct >= thresholds.green) infoChipColor = 'setup-chip-green';
        else if (infoPct >= thresholds.yellow) infoChipColor = 'setup-chip-yellow';

        const isPendingSend = this.pendingSendDrivers.has(car.driver_number);
        const sendDisabled = !isBox || isPendingSend;
        const sendLabel = 'Send Out';
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
                            <div class="ctrl-cell-v3 ctrl-brake-inline">
                                <label>Brake ducts</label>
                                ${brakeChipPreview}
                            </div>
                        </div>
                    </div>
                    ${tyreTemps}
                </div>
                ${this.buildPUInlineBar(car)}
                <div class="car-actions-v3 with-setup">
                    <div class="drive-actions">
                        <button class="btn-send${isPendingSend ? ' pending' : ''}" data-action="send" ${sendDisabled ? 'disabled' : ''}>${sendLabel}</button>
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

    buildPUInlineBar(car) {
        const puStats = car.pu_stats || {};
        const socMj = puStats.soc_mj ?? 0;
        const socPct = puStats.soc_pct ?? 0;
        const lapDeploy = puStats.lap_deploy_mj ?? 0;
        const deployLimit = puStats.deploy_mj_per_lap ?? 4.0;
        const deployPct = deployLimit > 0 ? Math.min((lapDeploy / deployLimit) * 100, 100) : 0;
        const socClass = socPct >= 60 ? 'pu-soc-good' : socPct >= 30 ? 'pu-soc-warn' : 'pu-soc-low';
        
        return `
            <div class="pu-inline-bar-v3">
                <div class="pu-metric-v3">
                    <span class="pu-label-v3">ERS SOC</span>
                    <span class="pu-value-v3 ${socClass}">${socMj.toFixed(1)} MJ (${Math.round(socPct)}%)</span>
                </div>
                <div class="pu-metric-v3">
                    <span class="pu-label-v3">Deploy</span>
                    <span class="pu-value-v3">${lapDeploy.toFixed(1)} / ${deployLimit.toFixed(1)} MJ</span>
                </div>
                <div class="pu-budget-bar-v3">
                    <span class="pu-label-v3">Lap Budget</span>
                    <div class="pu-bar-track-v3">
                        <div class="pu-bar-fill-v3" style="width:${deployPct}%"></div>
                    </div>
                </div>
                <button class="pu-details-btn-v3" data-action="pu-details">⚡ Details</button>
            </div>
        `;
    }

    buildPUModal(car) {
        if (!this.overlayContainer) return;
        const puStats = car.pu_stats || {};
        const brakeDiag = car.brake_diagnostics || {};
        const driverName = car.driver_name || `Driver #${car.driver_number}`;
        const carState = this.getCarState(car);
        const isBox = carState === 'BOX';
        this.overlayContainer.style.zIndex = '1500';
        const socMj = puStats.soc_mj ?? 0;
        const socPct = puStats.soc_pct ?? 0;
        const capacityMj = puStats.capacity_mj ?? 4.0;
        const deployLimit = puStats.deploy_limit_mj ?? 4.0;
        const harvestLimit = puStats.harvest_limit_mj ?? 2.0;
        const lapDeploy = puStats.lap_deploy_mj ?? 0;
        const lapHarvest = puStats.lap_harvest_mj ?? 0;
        const deployPerLap = puStats.deploy_mj_per_lap ?? 4.0;
        const harvestPerLap = puStats.harvest_mj_per_lap ?? 2.0;
        const lapMguhDirectPrev = puStats.lap_mguh_direct_prev_mj ?? null;
        const lapMguhHarvestPrev = puStats.lap_mguh_harvest_prev_mj ?? null;
        const lapMguhDirectCurrent = puStats.lap_mguh_direct_mj ?? 0;
        const lapMguhHarvestCurrent = puStats.lap_mguh_harvest_mj ?? 0;
        const lapMguhDirect = lapMguhDirectPrev != null ? lapMguhDirectPrev : lapMguhDirectCurrent;
        const lapMguhHarvest = lapMguhHarvestPrev != null ? lapMguhHarvestPrev : lapMguhHarvestCurrent;
        const mguhDirectBudget = this.resolveBudgetValue(puStats.mguh_direct_total_mj, puStats.mguh_direct_config_total_mj, 0);
        const deployPct = deployPerLap > 0 ? Math.min((lapDeploy / deployPerLap) * 100, 100) : 0;
        const harvestPct = harvestPerLap > 0 ? Math.min((lapHarvest / harvestPerLap) * 100, 100) : 0;
        const energyBalance = lapHarvest - lapDeploy;
        const warnings = puStats.warnings_runtime || [];
        const warningsActive = warnings.length > 0;
        const regenClampActive = !!puStats.regen_clamp_active;
        const warningsPrev = puStats.warnings_runtime_prev || [];
        const trace = puStats.energy_trace || [];
        const tracePrev = puStats.energy_trace_prev || [];
        const lapDeployPrev = puStats.lap_deploy_prev_mj ?? null;
        const lapHarvestPrev = puStats.lap_harvest_prev_mj ?? null;
        const lapIdCurrent = puStats.lap_id_current ?? null;
        const lapIdPrev = puStats.lap_id_prev ?? null;
        const mapName = puStats.map || 'STANDARD';
        const socClass = socPct >= 60 ? 'pu-soc-good' : socPct >= 30 ? 'pu-soc-warn' : 'pu-soc-low';
        
        const { currentLapIndex, previousLapIndex, completedLapCount } = this.resolveLapIndexes({
            car,
            lapIdCurrent,
            lapIdPrev,
        });

        const currentTotals = this.computeLapTotals(trace, lapDeploy, lapHarvest, lapMguhDirectCurrent, lapMguhHarvestCurrent);
        const previousTotals = this.computeLapTotals(tracePrev, lapDeployPrev, lapHarvestPrev, lapMguhDirectPrev, lapMguhHarvestPrev);

        const hasPrevWarnings = Array.isArray(warningsPrev) && warningsPrev.length > 0;
        const hasPrevLap = previousLapIndex !== null || (completedLapCount !== null && completedLapCount > 0);

        const lapChipRow = this.buildLapUsageChipRow({
            mapName,
            deployLimit,
            harvestLimit,
            deployPerLap,
            harvestPerLap,
            mguhDirectBudget,
            current: currentTotals.hasData ? {
                lapIndex: currentLapIndex,
                deploy: currentTotals.deploy,
                harvest: currentTotals.harvest,
                mguhDirect: currentTotals.mguhDirect,
                mguhHarvest: currentTotals.mguhHarvest,
            } : null,
            previous: (previousLapIndex !== null || previousTotals.hasData || previousTotals.hasTrace) ? {
                lapIndex: previousLapIndex,
                deploy: previousTotals.deploy,
                harvest: previousTotals.harvest,
                mguhDirect: previousTotals.mguhDirect,
                mguhHarvest: previousTotals.mguhHarvest,
            } : null,
            hasPrevTrace: previousTotals.hasTrace,
            hasPrevWarnings,
            hasPrevLap,
        });

        const traceRows = this.buildPUTableRows(trace, tracePrev, currentLapIndex, previousLapIndex);
        
        const brakeTile = this.buildBrakeRegenTile(puStats, brakeDiag, regenClampActive);

        const puStatsPanel = `
            <div class="pu-stats-grid-v3" style="margin-bottom: 12px;">
                <div class="pu-stats-metrics-grid">
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">Battery SOC</div>
                        <div class="pu-stat-value-v3 ${socClass}" style="font-size: 18px; margin: 3px 0;">${socMj.toFixed(1)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">${Math.round(socPct)}% charge</div>
                    </div>
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">Battery Capacity</div>
                        <div class="pu-stat-value-v3" style="font-size: 18px; margin: 3px 0;">${capacityMj.toFixed(1)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">Total</div>
                    </div>
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">Deploy Limit</div>
                        <div class="pu-stat-value-v3" style="font-size: 18px; margin: 3px 0;">${deployLimit.toFixed(1)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">Per lap</div>
                    </div>
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">Harvest Limit</div>
                        <div class="pu-stat-value-v3" style="font-size: 18px; margin: 3px 0;">${harvestLimit.toFixed(1)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">Per lap</div>
                    </div>
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">MGU-H Direct Drive</div>
                        <div class="pu-stat-value-v3" style="font-size: 18px; margin: 3px 0;">${lapMguhDirect.toFixed(2)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">Last lap</div>
                    </div>
                    <div class="pu-stat-card-v3" style="padding: 10px;">
                        <div class="pu-stat-label-v3" style="font-size: 10px;">MGU-H → ES</div>
                        <div class="pu-stat-value-v3" style="font-size: 18px; margin: 3px 0;">${lapMguhHarvest.toFixed(2)} MJ</div>
                        <div class="pu-stat-sub-v3" style="font-size: 9px;">Last lap</div>
                    </div>
                </div>
                ${brakeTile}
            </div>
            ${lapChipRow}
            <div class="pu-trace-container-v3" style="max-height: 280px; overflow-y: auto;">
                <table class="pu-trace-table-v3">
                    <thead>
                        <tr><th>Lap</th><th>Section</th><th>Deploy</th><th>Harvest</th><th>Hydraulic</th><th>Regen Ratio</th><th>MGU-H Direct Drive</th><th>MGU-H → ES</th></tr>
                    </thead>
                    <tbody>
                        ${traceRows || '<tr><td colspan="8" style="text-align:center;color:#888;">No trace data</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;
        const ersPanel = this.buildErsMapPanel(car, puStats, isBox);
        const tabBaseStyle = 'flex:1;border:1px solid rgba(255,255,255,0.14);border-radius:999px;padding:6px 12px;font-size:12px;font-weight:600;background:rgba(255,255,255,0.04);color:#d7def1;cursor:pointer;';
        const inactiveStyle = `${tabBaseStyle}`;
        const activeStyle = `${tabBaseStyle}background:#ffd24c;color:#10141b;border-color:#ffd24c;`;
        const statsBtnStyle = this.activePuTab === 'stats' ? activeStyle : inactiveStyle;
        const ersBtnStyle = this.activePuTab === 'ers-map' ? activeStyle : inactiveStyle;

        this.overlayContainer.dataset.driver = car.driver_number;
        this.overlayContainer.classList.add('is-visible', 'pu-modal-active');
        this.overlayContainer.classList.remove('is-hiding');
        this.overlayContainer.innerHTML = `
            <div class="pu-modal-v3">
                <div class="pu-modal-header-v3">
                    <div class="pu-modal-title-v3">⚡ PU Manager — ${driverName}</div>
                    <button class="pu-modal-close-v3" data-action="close-pu">×</button>
                </div>
                <div class="pu-modal-tabs-v3" style="display:flex; gap:8px; margin-bottom:14px;">
                    <button class="pu-tab-btn" style="${statsBtnStyle}" data-action="switch-pu-tab" data-tab="stats">Telemetry</button>
                    <button class="pu-tab-btn" style="${ersBtnStyle}" data-action="switch-pu-tab" data-tab="ers-map">ERS Map</button>
                </div>
                <div class="pu-modal-body-v3">
                    <section data-panel="stats" style="${this.activePuTab === 'stats' ? '' : 'display:none;'}">
                        ${puStatsPanel}
                    </section>
                    <section data-panel="ers-map" style="${this.activePuTab === 'ers-map' ? '' : 'display:none;'}">
                        ${ersPanel}
                    </section>
                </div>
            </div>
        `;
        this.setPauseForPU(true);
    }

    buildBrakeRegenTile(puStats, brakeDiag, regenClampActive) {
        const regenSplit = this.formatBrakeSplit(puStats, brakeDiag);
        const biasLabel = this.formatBrakeBias(brakeDiag);
        const ductLabel = this.formatBrakeDuct(brakeDiag);
        const coolingLabel = this.formatBrakeCooling(brakeDiag);
        const statusClass = regenClampActive ? 'status-pill status-pill--amber pu-brake-chip' : 'status-pill status-pill--green pu-brake-chip';
        const statusLabel = regenClampActive ? 'Clamp active' : 'Migration active';
        if (!regenSplit && !biasLabel && !ductLabel && !coolingLabel) {
            return '<div class="pu-brake-band pu-brake-band--empty">No brake data</div>';
        }

        const metrics = [
            regenSplit ? `<div class="pu-brake-band-metric"><span>Split</span><strong>${regenSplit}</strong></div>` : null,
            biasLabel ? `<div class="pu-brake-band-metric"><span>Bias</span><strong>${biasLabel}</strong></div>` : null,
            ductLabel ? `<div class="pu-brake-band-metric"><span>Duct target</span><strong>${ductLabel}</strong></div>` : null,
            coolingLabel ? `<div class="pu-brake-band-metric"><span>Cooling target</span><strong>${coolingLabel}</strong></div>` : null,
        ].filter(Boolean).join('');

        return `
            <div class="pu-brake-band">
                <div class="pu-brake-band-left">
                    <div class="pu-brake-band-header">
                        <span class="pu-brake-band-label">Brake Regen</span>
                        <span class="${statusClass}">${statusLabel}</span>
                    </div>
                    <div class="pu-brake-band-metrics">${metrics}</div>
                </div>
            </div>
        `;
    }

    formatBrakeSplit(puStats, brakeDiag) {
        const buildLabel = (regenPct, hydraulicPct) => `${regenPct}% regen / ${hydraulicPct}% hydraulic`;
        const ratio = Array.isArray(puStats.energy_trace) && puStats.energy_trace.length
            ? puStats.energy_trace[puStats.energy_trace.length - 1].regen_vs_hydraulic
            : null;
        if (typeof ratio === 'number' && ratio > 1e-3) {
            const hydraulicShare = ratio / (1 + ratio);
            const regenShare = 1 - hydraulicShare;
            return buildLabel(Math.round(regenShare * 100), Math.round(hydraulicShare * 100));
        }
        const base = brakeDiag?.regen_brake_base;
        if (typeof base === 'number') {
            const regenPct = Math.round(base * 100);
            const hydraulicPct = Math.max(0, 100 - regenPct);
            return buildLabel(regenPct, hydraulicPct);
        }
        return null;
    }

    formatBrakeBias(brakeDiag) {
        const bias = brakeDiag?.regen_migration_bias;
        if (typeof bias === 'number' && !Number.isNaN(bias)) {
            const direction = bias >= 0 ? 'rear' : 'front';
            return `${Math.abs(bias).toFixed(2)} (${direction})`;
        }
        return null;
    }

    formatBrakeDuct(brakeDiag) {
        const duct = brakeDiag?.duct_recommendation;
        if (duct && typeof duct.min_open === 'number' && typeof duct.max_open === 'number') {
            const formatPct = (value) => `${Math.round(value * 100)}%`;
            return `${formatPct(duct.min_open)} – ${formatPct(duct.max_open)}`;
        }
        return null;
    }

    formatBrakeCooling(brakeDiag) {
        const cooling = brakeDiag?.cooling_targets;
        const formatDelta = (value) => {
            if (typeof value !== 'number' || Number.isNaN(value)) return '--';
            return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;
        };
        if (!cooling) return null;
        const front = `front ${formatDelta(cooling?.front_delta)}`;
        const rear = `rear ${formatDelta(cooling?.rear_delta)}`;
        return `${front} · ${rear}`;
    }

    togglePUModal(driverNumber, open = true) {
        if (!this.overlayContainer) return;
        if (open) {
            const car = this.state.getPlayerCar(driverNumber);
            if (car) {
                this.buildPUModal(car);
            }
        } else {
            this.overlayContainer.classList.remove('is-visible', 'pu-modal-active');
            this.overlayContainer.classList.add('is-hiding');
            setTimeout(() => {
                this.overlayContainer.classList.remove('is-hiding');
                this.overlayContainer.removeAttribute('data-driver');
                this.overlayContainer.innerHTML = '';
                this.overlayContainer.style.zIndex = '';
                this.setPauseForPU(false);
                this.activePuTab = 'stats';
            }, 200);
        }
    }

    async setPauseForPU(active) {
        if (!this.sessionControls) return;
        if (active) {
            if (this.wasPausedBeforePU === null) {
                this.wasPausedBeforePU = this.sessionControls.isPaused;
            }
            if (!this.sessionControls.isPaused) {
                await this.sessionControls.setPauseState(true);
            }
        } else {
            if (this.wasPausedBeforePU === false) {
                await this.sessionControls.setPauseState(false);
            }
            this.wasPausedBeforePU = null;
        }
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
                const brakeWarnings = this.buildBrakeWarningsFromFeedback(validation);
                const fullMessage = brakeWarnings ? `${eval_.message}\n${brakeWarnings}` : eval_.message;
                msgEl.textContent = fullMessage;
                
                // Auto-resize feedback message if too long
                const lineHeight = 18;
                const maxLines = 3;
                const maxHeight = lineHeight * maxLines;
                if (msgEl.scrollHeight > maxHeight) {
                    msgEl.style.maxHeight = `${maxHeight}px`;
                    msgEl.style.overflowY = 'auto';
                }
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

    buildBrakeWarningsFromFeedback(validation) {
        const car = this.state.getPlayerCar?.();
        if (!car) return null;
        
        const warnings = [];
        const brakeCooling = car.brake_cooling || {};
        const brakeThermal = car.brake_thermal || {};
        
        // Check brake duct warnings
        ['front', 'rear'].forEach(axis => {
            const cooling = brakeCooling[axis];
            if (cooling?.status === 'low') {
                warnings.push(`${axis === 'front' ? 'Front' : 'Rear'} brake ducts too closed`);
            } else if (cooling?.status === 'high') {
                warnings.push(`${axis === 'front' ? 'Front' : 'Rear'} brake ducts too open`);
            }
        });
        
        // Check brake temperature warnings
        ['front', 'rear'].forEach(axis => {
            const temp = brakeThermal[axis];
            const thresholds = brakeThermal.thresholds || {};
            const fadeThreshold = axis === 'front' ? thresholds.front_c : thresholds.rear_c;
            
            if (typeof temp === 'number' && typeof fadeThreshold === 'number') {
                if (temp >= fadeThreshold - 10) {
                    warnings.push(`${axis === 'front' ? 'Front' : 'Rear'} brakes near critical temperature`);
                }
            }
        });
        
        return warnings.length > 0 ? warnings.join('. ') : null;
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
            if (chip) {
                const pct = car.setup_info_percent ?? 0;
                const thresholds = car.is_player_controlled
                    ? { green: 67, yellow: 34 }
                    : { green: 80, yellow: 40 };
                chip.classList.remove('setup-chip-red', 'setup-chip-yellow', 'setup-chip-green', 'setup-chip-blink');
                if (pct >= thresholds.green) chip.classList.add('setup-chip-green');
                else if (pct >= thresholds.yellow) chip.classList.add('setup-chip-yellow');
                else chip.classList.add('setup-chip-red');
                if (pct >= 100) chip.classList.add('setup-chip-blink');
            }

            const thermal = car.brake_thermal;
            const nowSeconds = Date.now() / 1000;
            card.querySelectorAll('.brake-chip-mini').forEach(chipEl => {
                const axis = chipEl.dataset.bcAxis;
                const axisData = this.resolveBrakeAxisData(car, axis, thermal);
                const blinkUntil = this.resolveBrakeBlink(car, axis);
                this.applyBrakeChipState(chipEl, axisData, nowSeconds, blinkUntil);
            });
        });
    }

    resolveBrakeBlink(car, axis) {
        if (!car?.brake_cooling) return null;
        const data = car.brake_cooling[axis];
        return typeof data?.blink_until === 'number' ? data.blink_until : null;
    }

    applyBrakeChipState(chipEl, axisData, nowSeconds, blinkUntil) {
        if (!chipEl) return;
        const state = this.getBrakeChipState(axisData, nowSeconds);
        chipEl.classList.remove('brake-chip-ok', 'brake-chip-warn', 'brake-chip-bad', 'brake-chip-na', 'brake-chip-blink');
        chipEl.classList.add(state.statusClass);
        if (state.shouldBlink || (typeof blinkUntil === 'number' && nowSeconds < blinkUntil)) {
            chipEl.classList.add('brake-chip-blink');
        }
        const valueEl = chipEl.querySelector('.bc-value');
        if (valueEl) valueEl.textContent = state.valueText;
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

        const fp = cars.map(c => `${c.driver_number}:${c.state}:${c.total_laps}:${c.current_tire}:${c.tire_age}:${this.puStatsSignature(c.pu_stats)}:${this.brakeCoolingSignature(c.brake_cooling)}:${this.brakeThermalSignature(c.brake_thermal)}`).join('|');
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
            payload[field] = draft[field]
                ?? car.player_config?.setup?.[field]
                ?? car.player_config?.[field]
                ?? car[field]
                ?? this.setupDefaults[field];
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

    applyLocalCarState(driverNumber, carPayload, options = {}) {
        if (!carPayload || typeof carPayload !== 'object') {
            console.warn('[GarageV3] Invalid car payload');
            return;
        }
        const preservePending = options.preservePending === true;
        const existing = this.state.getPlayerCar(driverNumber) || {};
        const updated = { ...existing, ...carPayload };
        updated.state = this.getCarState(updated);
        // pendingSendDrivers is managed only in handleCardClick and when car returns to BOX after stint
        this.state.setPlayerCar(updated);
    }

    async sendPlayerConfig(driverNumber, payload, state, options = {}) {
        const allowedPayload = { ...payload };
        const card = this.cardsContainer?.querySelector(`[data-driver="${driverNumber}"]`);
        const car = this.state.getPlayerCar(driverNumber);

        const clampNumericField = (field, min, max, round = true) => {
            if (typeof allowedPayload[field] !== 'number' || Number.isNaN(allowedPayload[field])) return;
            const raw = round ? Math.round(allowedPayload[field]) : allowedPayload[field];
            const clamped = Math.max(min, Math.min(max, raw));
            if (clamped !== allowedPayload[field]) {
                allowedPayload[field] = clamped;
                if (card) {
                    const input = card.querySelector(`[data-field="${field}"]`);
                    if (input) input.value = clamped;
                }
            } else if (round && raw !== allowedPayload[field]) {
                allowedPayload[field] = raw;
            }
        };

        const maxStint = car?.max_stint_laps ?? car?.stint_target_laps ?? 12;
        clampNumericField('stint_target_laps', 1, maxStint);
        clampNumericField('fuel_percent', 1, 100);
        clampNumericField('pace_level', 1, 10);

        if (typeof allowedPayload.tyre_compound === 'string') {
            const normalized = allowedPayload.tyre_compound.toLowerCase();
            if (normalized !== allowedPayload.tyre_compound) {
                allowedPayload.tyre_compound = normalized;
                if (card) {
                    const select = card.querySelector('[data-field="tyre_compound"]');
                    if (select) select.value = normalized;
                }
            }
        }

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
            const touchedFields = Object.keys(allowedPayload);
            const runtimeOnly = touchedFields.every(field => this.RUNTIME_FIELDS.has(field));
            if (!runtimeOnly && !options.suppressStatus) {
                this.setStatus(`Setup stored for #${driverNumber}.`, 'success');
            }
            this.applyLocalPlayerUpdates(driverNumber, allowedPayload);
            if (!options.skipRender) {
                this.render(true);
            }
            return true;
        } catch (err) {
            console.error(err);
            this.setStatus(err.message || 'Configuration failed', 'error');
            return false;
        }
    }

    handleOverlayAction(driverNumber, action, target = null) {
        if (action === 'close-setup') {
            this.toggleSetupOverlay(driverNumber, false);
        } else if (action === 'close-pu') {
            this.togglePUModal(driverNumber, false);
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
        } else if (action === 'switch-pu-tab') {
            const tab = target?.dataset?.tab || 'stats';
            const carData = this.state.getPlayerCar(driverNumber);
            this.activePuTab = tab;
            if (carData) {
                this.buildPUModal(carData);
            }
        } else if (action === 'ers-reset') {
            const carData = this.state.getPlayerCar(driverNumber);
            if (carData) {
                const puStats = carData.pu_stats || {};
                this.resetErsEditorState(driverNumber, puStats);
                this.refreshErsEditorPanel(driverNumber);
            }
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
            if (this.pushHudBanner) {
                this.pushHudBanner({
                    title: `Driver #${driverNumber}`,
                    body: 'Car released to track',
                    tone: 'success',
                    duration: 3500,
                });
            }
            if (data.car) {
                const shouldPreservePending = this.getCarState(data.car) === 'BOX';
                this.applyLocalCarState(driverNumber, data.car, { preservePending: shouldPreservePending });
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

    async handleCardClick(event) {
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
        
        if (action === 'send') {
            if (state !== 'BOX') {
                this.setStatus('Car already on track. Box first to change tyres/fuel.', 'error');
                return;
            }
            actionBtn.disabled = true;
            this.pendingSendDrivers.add(driverNumber);
            this.applyLocalCarState(driverNumber, { state: 'OUT_LAP', is_on_track: true });
            this.render(true);
            const sent = await this.sendPlayerCarOut(driverNumber);
            if (!sent) {
                this.pendingSendDrivers.delete(driverNumber);
                this.applyLocalCarState(driverNumber, { state: 'BOX', is_on_track: false });
                this.render(true);
            }
        } else if (action === 'box') {
            if (state === 'BOX') {
                this.setStatus('Car already in the garage.', 'error');
                return;
            }
            this.requestPlayerBox(driverNumber);
        } else if (action === 'setup') {
            this.toggleSetupOverlay(driverNumber, true);
        } else if (action === 'pu-details') {
            this.togglePUModal(driverNumber, true);
        } else if (action === 'close-pu') {
            this.togglePUModal(driverNumber, false);
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
            // Apply any pending tyres/fuel changes
            const card = this.cardsContainer.querySelector(`[data-driver="${driverNumber}"]`);
            if (card) {
                const configPayload = this.collectCardPayload(card);
                await this.sendPlayerConfig(driverNumber, configPayload, currentState, { skipRender: true });
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
