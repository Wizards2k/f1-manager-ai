export class TimingPanelV3 {
    constructor({ state = null, tableContainer, timerElement, headerElement = null }) {
        this.state = state || { sessionBests: { best_lap: null, best_sectors: {} } };
        this.timerElement = timerElement;
        this.headerElement = headerElement;
        this.tableElement = tableContainer; // tableContainer is already an element, not an ID
        this._rowMap = new Map();           // driver_number → row element
        this._lastSectors = new Map();     // driver_number → {sector1, sector2, sector3}
        this._activeTooltip = null;        // Currently open AI debug tooltip
        this._carDataMap = new Map();      // driver_number → latest car data for tooltip
        this._boundDocumentClick = this._handleDocumentClick.bind(this);
        this._boundTableClick = this._handleTableClick.bind(this);
        
        document.addEventListener('pointerdown', this._boundDocumentClick);
        // Single click delegate on the table container for AI debug tooltip
        if (this.tableElement) {
            this.tableElement.addEventListener('pointerdown', this._boundTableClick, true);
        } else {
            console.error('[TimingPanelV3] Table element NOT found:', tableContainer);
        }

        
        // Esponi funzione globale per handler inline onclick
        window.showAiDebugTooltip = (chipElement) => {
            const row = chipElement.closest('.driver-row');
            if (!row) return;
            const dn = row.dataset.driverNumber;
            const car = this._carDataMap.get(String(dn));
            if (!car || car.is_player_controlled) return;
            this._showAiDebugTooltip(car, chipElement);
        };
    }

    destroy() {
        document.removeEventListener('pointerdown', this._boundDocumentClick);
        if (this.tableElement && this._boundTableClick) {
            this.tableElement.removeEventListener('pointerdown', this._boundTableClick, true);
        }
        this._closeActiveTooltip();
        // Rimuovi funzione globale
        if (window.showAiDebugTooltip) {
            delete window.showAiDebugTooltip;
        }
    }

    /**
     * Find the DATA chip in the event path using composedPath for robustness.
     * @param {Event} e - Click event
     * @returns {HTMLElement|null} The DATA chip element or null
     */
    _findDataChipFromEvent(e) {
        const path = e.composedPath();
        for (const el of path) {
            if (el.classList && (el.classList.contains('data-chip') || el.classList.contains('data-chip-ready'))) {
                return el;
            }
        }
        return null;
    }

    _handleTableClick(e) {
        const chip = this._findDataChipFromEvent(e);
        if (!chip) return;

        const row = chip.closest('.driver-row');
        if (!row) return;

        const dn = row.dataset.driverNumber;
        const car = this._carDataMap.get(String(dn));
        if (!car || car.is_player_controlled) return;

        e.stopPropagation();
        this._showAiDebugTooltip(car, chip);
    }

    _handleDocumentClick(e) {
        // Close tooltip when clicking outside
        const path = typeof e.composedPath === 'function' ? e.composedPath() : [];
        const clickedInsideTooltip = this._activeTooltip && path.includes(this._activeTooltip);
        if (this._activeTooltip && !clickedInsideTooltip) {
            const chip = this._findDataChipFromEvent(e);
            if (!chip) {
                this._closeActiveTooltip();
            }
        }
    }

    _closeActiveTooltip() {
        if (this._activeTooltip) {
            this._activeTooltip.remove();
            this._activeTooltip = null;
        }
    }

    _buildAiDebugTooltip(car) {
        const setupScore = car.ai_setup_score != null ? car.ai_setup_score.toFixed(2) : '--';
        const setupThreshold = car.ai_setup_threshold != null ? car.ai_setup_threshold.toFixed(2) : '--';
        const runsDone = car.ai_total_runs ?? 0;
        const runsRequired = car.ai_min_runs_required ?? '--';
        const setupStatus = car.ai_setup_complete ? 'Complete' : 'Collecting';
        const setupPct = car.setup_info_percent?.toFixed(0) ?? '0';

        const tyreSetId = car.ai_tyre_set_id ?? '--';
        const tyreCondition = car.ai_tyre_condition != null ? `${car.ai_tyre_condition.toFixed(0)}%` : '--';
        const tyreHeatCycles = car.ai_tyre_heat_cycles ?? '--';
        const currentTire = car.current_tire?.toUpperCase() ?? '--';
        const aiProgram = car.ai_program ?? '--';

        const tooltip = document.createElement('div');
        tooltip.className = 'ai-debug-tooltip';
        tooltip.innerHTML = `
            <div class="ai-debug-header">
                <span class="ai-debug-driver">${car.driver_name || 'Driver'}</span>
                <button class="ai-debug-close" aria-label="Close">×</button>
            </div>
            <div class="ai-debug-section">
                <div class="ai-debug-title">Setup Search</div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Score:</span>
                    <span class="ai-debug-value">${setupScore}/${setupThreshold}</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Runs:</span>
                    <span class="ai-debug-value">${runsDone}/${runsRequired}</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Progress:</span>
                    <span class="ai-debug-value">${setupPct}%</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Status:</span>
                    <span class="ai-debug-value ai-debug-status-${car.ai_setup_complete ? 'complete' : 'collecting'}">${setupStatus}</span>
                </div>
            </div>
            <div class="ai-debug-section">
                <div class="ai-debug-title">Tyre Set</div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Compound:</span>
                    <span class="ai-debug-value">${currentTire}</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Set ID:</span>
                    <span class="ai-debug-value">${tyreSetId}</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Condition:</span>
                    <span class="ai-debug-value">${tyreCondition}</span>
                </div>
                <div class="ai-debug-row">
                    <span class="ai-debug-label">Heat Cycles:</span>
                    <span class="ai-debug-value">${tyreHeatCycles}</span>
                </div>
            </div>
            <div class="ai-debug-section">
                <div class="ai-debug-title">Current Program</div>
                <div class="ai-debug-row">
                    <span class="ai-debug-value ai-debug-program">${aiProgram}</span>
                </div>
            </div>
        `;

        tooltip.querySelector('.ai-debug-close').addEventListener('pointerdown', (e) => {
            e.stopPropagation();
            this._closeActiveTooltip();
        });

        return tooltip;
    }

    _showAiDebugTooltip(car, chipElement) {
        this._closeActiveTooltip();

        const tooltip = this._buildAiDebugTooltip(car);
        document.body.appendChild(tooltip);
        this._activeTooltip = tooltip;

        // Position tooltip near the chip
        const rect = chipElement.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();

        let top = rect.bottom + 8;
        let left = rect.left;

        // Prevent overflow on right edge
        if (left + tooltipRect.width > window.innerWidth - 16) {
            left = window.innerWidth - tooltipRect.width - 16;
        }

        // Prevent overflow on bottom - flip to top if needed
        if (top + tooltipRect.height > window.innerHeight - 16) {
            top = rect.top - tooltipRect.height - 8;
        }

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
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

    static resolveDataChipClass(car) {
        const pct = car.setup_info_percent ?? 0;
        const isPlayer = !!car.is_player_controlled;
        const thresholds = isPlayer
            ? { green: 67, yellow: 34 }
            : { green: 80, yellow: 40 };

        if (pct >= 100) return 'data-chip-ready';
        if (pct >= thresholds.green) return 'data-chip-green';
        if (pct >= thresholds.yellow) return 'data-chip-yellow';
        return 'data-chip-red';
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

    _resolveDisplaySectors(car) {
        const dn = car.driver_number;
        const live = car.current_lap_sectors || {};
        const last = car.last_sector_times || {};
        const cached = this._lastSectors.get(dn) || {};

        const hasS1 = live.sector1 != null;
        const hasS2 = live.sector2 != null;
        const hasS3 = live.sector3 != null;

        const display = {};

        if (hasS1 || hasS2 || hasS3) {
            // New lap in progress: show live sectors, keep previous for unset ones
            display.sector1 = live.sector1 ?? null;
            // When S1 arrives, clear S2/S3 (TV-style: only show completed sectors)
            display.sector2 = hasS1 ? (live.sector2 ?? null) : null;
            display.sector3 = (hasS1 && hasS2) ? (live.sector3 ?? null) : null;
            this._lastSectors.set(dn, { ...display });
        } else if (last.sector1 != null) {
            // Lap just completed: backend cleared current_lap_sectors but last_sector_times has the data
            display.sector1 = last.sector1 ?? null;
            display.sector2 = last.sector2 ?? null;
            display.sector3 = last.sector3 ?? null;
            this._lastSectors.set(dn, { ...display });
        } else if (cached.sector1 != null) {
            // Use client-side cache as last resort
            display.sector1 = cached.sector1;
            display.sector2 = cached.sector2 ?? null;
            display.sector3 = cached.sector3 ?? null;
        } else {
            display.sector1 = null;
            display.sector2 = null;
            display.sector3 = null;
        }

        return display;
    }

    _createRow(car, index) {
        const row = document.createElement('div');
        row.className = 'driver-row';
        row.dataset.driverNumber = car.driver_number;
        row.innerHTML = this._rowInnerHTML(car, index);
        return row;
    }

    _rowInnerHTML(car, index) {
        const isInBox = car.state === 'BOX';
        const stateClass = car.state ? car.state.toLowerCase().replace('_', '-') : 'box';
        const sectorKeys = ['sector1', 'sector2', 'sector3'];
        const displaySectors = this._resolveDisplaySectors(car);

        const sectorHtml = sectorKeys.map((key, idx) => {
            const current = displaySectors[key];
            const reference = car.best_lap_sectors?.[key];
            const delta = TimingPanelV3.formatDelta(current, reference);
            const deltaClass = delta ? ((current - reference) >= 0 ? 'positive' : 'negative') : '';
            return `
                <div class="sector-row">
                    <span>S${idx + 1}:</span>
                    <span class="sector-time ${this.sectorClass(current, car.best_sectors?.[key], key)}">${current ? TimingPanelV3.formatSectorTime(current) : '--:--'}</span>
                    ${delta ? `<span class="sector-delta ${deltaClass}">(${delta})</span>` : '<span class="sector-delta"></span>'}
                </div>
            `;
        }).join('');

        const dataChipClass = TimingPanelV3.resolveDataChipClass(car);

        return `
            <div class="position">${index + 1}</div>
            <div class="driver-number-wrapper">
                <div class="driver-number" style="background: ${car.team_color}">
                    ${car.driver_number}
                </div>
                <div class="blue-flag-bar ${car.blue_flag ? 'active' : ''}"></div>
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
                    ${car.best_lap_time ? TimingPanelV3.formatLapTime(car.best_lap_time) : '--:--.---'}
                    <small>BEST</small>
                </div>
                <div class="sector-times">${sectorHtml}</div>
                <div class="last-lap ${this.lapClass(car.last_lap_time, car.best_lap_time)}">
                    ${car.last_lap_time ? TimingPanelV3.formatLapTime(car.last_lap_time) : '--:--.---'}
                    <small>LAST</small>
                    ${car.last_lap_type && car.last_lap_type !== 'HOT_LAP' ? `<small style="color:#888;">(${car.last_lap_type})</small>` : ''}
                </div>
            </div>
            <div class="lap-count">${car.total_laps ?? 0}</div>
            <div class="state-data-col">
                <div class="state-indicator ${stateClass}">
                    ${car.state || 'BOX'}
                </div>
                ${!car.is_player_controlled ? `<div class="data-chip ${dataChipClass}" data-ai="true" style="pointer-events: auto; cursor: pointer; z-index: 10;" title="AI Debug Data" onpointerdown="window.showAiDebugTooltip && window.showAiDebugTooltip(this); event.stopPropagation();">DATA</div>` : ''}
                ${car.is_player_controlled ? `<div class="data-chip ${dataChipClass}" title="Player controlled">DATA</div>` : ''}
            </div>
        `;
    }

    render(cars = []) {
        if (!this.tableElement) return;
        const sorted = [...cars].sort((a, b) => {
            if (!a.best_lap_time) return 1;
            if (!b.best_lap_time) return -1;
            return a.best_lap_time - b.best_lap_time;
        });

        const desiredOrder = sorted.map(c => String(c.driver_number));
        const existingKeys = new Set(this._rowMap.keys());
        const newKeys = new Set(desiredOrder);

        // Remove rows for drivers no longer present
        for (const key of existingKeys) {
            if (!newKeys.has(key)) {
                const el = this._rowMap.get(key);
                if (el && el.parentNode) el.parentNode.removeChild(el);
                this._rowMap.delete(key);
                this._lastSectors.delete(key);
            }
        }

        // Create or update each row
        sorted.forEach((car, index) => {
            const dn = String(car.driver_number);
            const isInBox = car.state === 'BOX';
            let row = this._rowMap.get(dn);

            if (!row) {
                row = this._createRow(car, index);
                this._rowMap.set(dn, row);
            } else {
                row.innerHTML = this._rowInnerHTML(car, index);
            }

            row.className = `driver-row ${isInBox ? 'in-box' : 'on-track'}`;
            row.style.borderLeftColor = car.team_color;

            // Store latest car data for AI debug tooltip
            this._carDataMap.set(dn, car);
        });

        // Reorder DOM nodes to match sorted order (only moves if needed)
        for (let i = 0; i < desiredOrder.length; i++) {
            const dn = desiredOrder[i];
            const row = this._rowMap.get(dn);
            if (!row) continue;

            const currentChild = this.tableElement.children[i];
            if (currentChild !== row) {
                if (currentChild) {
                    this.tableElement.insertBefore(row, currentChild);
                } else {
                    this.tableElement.appendChild(row);
                }
            }
        }
    }

    updateFlag(flag) {
        if (!this.headerElement || flag === this._currentFlag) return;
        this._currentFlag = flag;
        this.headerElement.classList.remove('flag-green', 'flag-yellow', 'flag-red');
        this.headerElement.classList.add(`flag-${flag}`);

        let labelEl = this.headerElement.querySelector('.flag-label');
        if (!labelEl) {
            labelEl = document.createElement('span');
            labelEl.className = 'flag-label';
            const titleEl = this.headerElement.querySelector('.session-title');
            if (titleEl) titleEl.parentNode.insertBefore(labelEl, titleEl.nextSibling);
        }

        const labels = {
            green: '',
            yellow: '\u26A0 YELLOW FLAG',
            red: '\uD83D\uDD34 RED FLAG \u2014 SUSPENDED',
        };
        labelEl.textContent = labels[flag] || '';
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
