export class TimingPanelV3 {
    constructor({ state = null, tableContainer, timerElement, headerElement = null }) {
        this.state = state || { sessionBests: { best_lap: null, best_sectors: {} } };
        this.tableElement = tableContainer;
        this.timerElement = timerElement;
        this.headerElement = headerElement || document.querySelector('.timing-header');
        this._currentFlag = 'green';
        this._rowMap = new Map();          // driver_number → DOM element
        this._lastSectors = new Map();     // driver_number → {sector1, sector2, sector3}
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
                <div class="data-chip ${dataChipClass}">DATA</div>
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
