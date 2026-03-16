export class SessionControls {
    constructor({ pauseButton, speedButtons, speedIndicator, selectCircuitButton } = {}) {
        this.pauseButton = pauseButton;
        this.speedButtons = Array.from(speedButtons || []);
        this.speedIndicator = speedIndicator;
        this.selectCircuitButton = selectCircuitButton || document.getElementById('select-circuit-btn');
        this.currentSpeed = 1;
        this.isPaused = false;
        this.onSpeedChange = null;
        this.uiToServerSpeed = { 1: 1.0, 2: 5.0, 4: 15.0, 6: 30.0 };
        this.serverToUiSpeed = {
            1.0: 1,
            5.0: 2,
            15.0: 4,
            30.0: 6,
        };
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
                const uiSpeed = parseFloat(btn.dataset.speed);
                this.changeSpeed(uiSpeed);
            });
        });
        if (this.selectCircuitButton) {
            this.selectCircuitButton.addEventListener('click', () => this.returnToCircuitSelection());
        }
    }

    updateSpeedIndicator(speed) {
        if (this.speedIndicator) {
            this.speedIndicator.textContent = `Speed: ${speed}x`;
        }
        this.speedButtons.forEach(btn => {
            if (!btn.dataset.speed) return;
            btn.classList.toggle('active', parseFloat(btn.dataset.speed) === speed);
        });
    }

    updatePauseButton(isPaused) {
        if (!this.pauseButton) return;
        if (isPaused) {
            this.pauseButton.textContent = '▶';
            this.pauseButton.classList.add('paused');
            this.pauseButton.title = 'Resume';
        } else {
            this.pauseButton.textContent = '⏸';
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
            return this.isPaused;
        } catch (error) {
            console.error('Error toggling pause:', error);
            return this.isPaused;
        }
    }

    async changeSpeed(uiSpeed) {
        try {
            this.uiToServerSpeed[uiSpeed] ?? uiSpeed;
            const response = await fetch('/api/set_speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed: uiSpeed })
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            await response.json();
            this.currentSpeed = uiSpeed;
            this.updateSpeedIndicator(uiSpeed);
            this._emitSpeedChange(uiSpeed);
        } catch (error) {
            console.error('Network error setting speed:', error);
        }
    }

    applyServerState({ is_paused: isPaused, game_speed: gameSpeed } = {}) {
        if (typeof isPaused === 'boolean' && isPaused !== this.isPaused) {
            this.isPaused = isPaused;
            this.updatePauseButton(this.isPaused);
        }
        if (typeof gameSpeed === 'number' && !Number.isNaN(gameSpeed)) {
            const uiSpeed = this.serverToUiSpeed[gameSpeed] ?? this.currentSpeed;
            if (uiSpeed !== this.currentSpeed) {
                this.currentSpeed = uiSpeed;
                this.updateSpeedIndicator(this.currentSpeed);
                this._emitSpeedChange(this.currentSpeed);
            }
        }
    }

    async setPauseState(shouldPause) {
        if (typeof shouldPause !== 'boolean') {
            return this.isPaused;
        }
        if (this.isPaused === shouldPause) {
            return this.isPaused;
        }
        return this.togglePause();
    }

    async returnToCircuitSelection() {
        try {
            const response = await fetch('/api/session/reset', { method: 'POST' });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error resetting session:', error);
        } finally {
            window.location.href = '/';
        }
    }

    _emitSpeedChange(speed) {
        if (typeof this.onSpeedChange === 'function') {
            this.onSpeedChange(speed);
        }
    }
}
