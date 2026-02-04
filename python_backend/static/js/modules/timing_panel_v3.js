export class TimingPanelV3 {
    constructor({ state = null, tableContainer, timerElement }) {
        this.state = state || { sessionBests: { best_lap: null, best_sectors: {} } };
        this.tableElement = tableContainer;
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

    render(cars = []) {
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
