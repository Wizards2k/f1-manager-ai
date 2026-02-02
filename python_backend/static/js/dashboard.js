import { AppState } from './modules/app_state.js';
import { MapModule } from './modules/map_module.js';
import { TimingPanel } from './modules/timing_panel.js';
import { PlayerGarage } from './modules/player_garage.js';
import { SessionControls } from './modules/session_controls.js';
import { SocketBridge } from './modules/socket_bridge.js';

(function initDashboard() {
    const appState = new AppState();

    const mapModule = new MapModule(appState);
    mapModule.loadCircuitGeometry().catch(err => console.error('Circuit geometry load failed', err));

    const timingPanel = new TimingPanel(
        appState,
        document.getElementById('timing-table'),
        document.getElementById('session-timer')
    );

    const playerGarage = new PlayerGarage(appState, {
        teamLabel: document.getElementById('player-team-label'),
        statusMsg: document.getElementById('player-status-msg'),
        cardsContainer: document.getElementById('player-car-cards'),
        overlayContainer: document.getElementById('player-setup-overlay'),
        dockElement: document.getElementById('player-dock'),
        notificationsContainer: document.getElementById('garage-notifications')
    });

    const sessionControls = new SessionControls({
        pauseButton: document.getElementById('pause-btn'),
        speedButtons: document.querySelectorAll('.speed-btn'),
        speedIndicator: document.getElementById('current-speed')
    });

    new SocketBridge({
        state: appState,
        mapModule,
        timingPanel,
        playerGarage,
        sessionControls
    });
})();
