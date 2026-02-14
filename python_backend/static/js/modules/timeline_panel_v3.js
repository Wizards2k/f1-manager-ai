export class TimelinePanelV3 {
    constructor({
        state,
        panelElement,
        listElement,
        emptyElement,
        toggleButton,
        toggleButtons = [],
        clearButton,
        closeButton,
        sessionControls,
    } = {}) {
        this.state = state;
        this.panelElement = panelElement;
        this.listElement = listElement;
        this.emptyElement = emptyElement;
        const toggles = [...(toggleButtons || [])];
        if (toggleButton) toggles.push(toggleButton);
        this.toggleButtons = toggles.filter(Boolean);
        this.clearButton = clearButton;
        this.closeButton = closeButton;
        this.sessionControls = sessionControls;
        this.isOpen = false;
        this.wasPausedBeforeOpen = null;
        console.log('[TimelinePanel] Constructor - panelElement:', this.panelElement);
        this.bindEvents();
        this.render();
    }

    bindEvents() {
        this.toggleButtons.forEach(btn => {
            btn.addEventListener('click', () => this.toggle());
        });
        if (this.closeButton) {
            this.closeButton.addEventListener('click', () => this.close());
        }
        if (this.clearButton) {
            this.clearButton.addEventListener('click', () => this.clear());
        }
    }

    toggle() {
        this.setOpen(!this.isOpen);
    }

    close() {
        this.setOpen(false);
    }

    setOpen(nextState) {
        if (typeof nextState !== 'boolean' || nextState === this.isOpen) {
            return;
        }
        this.isOpen = nextState;
        this.syncPanelState();
        this.handleAutoPause();
    }

    syncPanelState() {
        if (this.panelElement) {
            this.panelElement.classList.toggle('is-open', this.isOpen);
            this.panelElement.setAttribute('aria-hidden', this.isOpen ? 'false' : 'true');
        }
        this.toggleButtons.forEach(btn => {
            btn.setAttribute('aria-expanded', this.isOpen ? 'true' : 'false');
        });
    }

    async handleAutoPause() {
        if (!this.sessionControls?.setPauseState) return;
        if (this.isOpen) {
            this.wasPausedBeforeOpen = this.sessionControls.isPaused;
            await this.sessionControls.setPauseState(true);
        } else {
            if (this.wasPausedBeforeOpen === false) {
                await this.sessionControls.setPauseState(false);
            }
            this.wasPausedBeforeOpen = null;
        }
    }

    clear() {
        if (this.state?.clearTimelineEvents) {
            this.state.clearTimelineEvents();
        }
        this.render();
    }

    render() {
        if (!this.listElement || !this.state?.getTimelineEvents) return;
        const events = this.state.getTimelineEvents();
        if (!events.length) {
            if (this.emptyElement) this.emptyElement.style.display = 'block';
            this.listElement.innerHTML = '';
            return;
        }
        if (this.emptyElement) this.emptyElement.style.display = 'none';
        this.listElement.innerHTML = events
            .slice()
            .reverse()
            .map((event) => this.renderEvent(event))
            .join('');
    }

    renderEvent(event) {
        const tone = this.getTone(event.event_type);
        const timestamp = this.formatTimestamp(event.timestamp);
        const title = this.getEventTitle(event);
        const body = this.getEventBody(event);
        const driver = event.driver_name || event.team_name || `Car ${event.car_id}`;
        return `
            <article class="timeline-event ${tone}">
                <div class="event-meta">
                    <span>${timestamp}</span>
                    <span>${driver}</span>
                </div>
                <div class="event-title">${title}</div>
                <div class="event-body">${body || ''}</div>
                <div class="event-tags">
                    <span class="timeline-tag ${tone}">${tone}</span>
                    <span class="timeline-tag">${event.event_type}</span>
                </div>
            </article>
        `;
    }

    getEventTitle(event) {
        const base = event.payload?.message;
        if (base) return base;
        switch (event.event_type) {
            case 'ai_run_started':
                return `${event.driver_name || 'Driver'}: Run iniziato`;
            case 'ai_run_completed':
                return `${event.driver_name || 'Driver'}: Run completato`;
            case 'ai_setup_adjustment':
                return `${event.driver_name || 'Driver'}: Setup aggiornato`;
            case 'ai_setup_converged':
                return `${event.driver_name || 'Driver'}: Setup OK`;
            default:
                if (event.event_type?.startsWith('battle_')) {
                    return 'Evento battaglia';
                }
                return 'Evento';
        }
    }

    getEventBody(event) {
        const payload = event.payload || {};
        if (event.event_type === 'ai_run_completed') {
            const lap = payload.best_lap_s ? this.formatLapTime(payload.best_lap_s) : '--:--.---';
            return `Best ${lap} · Laps ${payload.laps_done ?? '--'}`;
        }
        if (event.event_type === 'ai_run_started') {
            return `${payload.program || 'Program'} · ${payload.laps_planned || '?'} giri`;
        }
        if (event.event_type === 'ai_setup_adjustment' && payload.changes) {
            const keys = Object.entries(payload.changes)
                .slice(0, 3)
                .map(([key, value]) => `${key}: ${value}`);
            return keys.join(', ');
        }
        if (event.event_type === 'ai_setup_converged') {
            return `Score ${payload.final_score?.toFixed?.(2) ?? '--'} / ${payload.threshold ?? '--'}`;
        }
        if (event.event_type?.startsWith('battle_')) {
            const attacker = payload.attacker_name || payload.attacker_id || 'Car A';
            const defender = payload.defender_name || payload.defender_id || 'Car B';
            const section = payload.section || 'track';
            const outcome = payload.outcome ? payload.outcome.replace(/_/g, ' ') : 'battle';
            return `${attacker} vs ${defender} – ${outcome} (${section})`;
        }
        return '';
    }

    getTone(eventType = '') {
        if (eventType === 'battle_collision') return 'error';
        if (eventType === 'battle_blocked' || eventType === 'battle_side_by_side') return 'warning';
        if (eventType === 'ai_setup_converged') return 'success';
        return 'info';
    }

    formatTimestamp(ts) {
        if (!ts) return '--:--';
        const date = new Date(ts);
        if (Number.isNaN(date.getTime())) return '--:--';
        return date.toLocaleTimeString('it-IT', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
        });
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
