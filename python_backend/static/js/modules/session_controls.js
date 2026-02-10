export class SessionControls {
    constructor({ pauseButton, speedButtons, speedIndicator, selectCircuitButton } = {}) {
        this.pauseButton = pauseButton;
        this.speedButtons = Array.from(speedButtons || []);
        this.speedIndicator = speedIndicator;
        this.selectCircuitButton = selectCircuitButton || document.getElementById('select-circuit-btn');
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
        if (typeof isPaused === 'boolean' && isPaused !== this.isPaused) {
            this.isPaused = isPaused;
            this.updatePauseButton(this.isPaused);
        }
        if (typeof gameSpeed === 'number' && !Number.isNaN(gameSpeed) && gameSpeed !== this.currentSpeed) {
            this.currentSpeed = gameSpeed;
            this.updateSpeedIndicator(this.currentSpeed);
        }
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
}
