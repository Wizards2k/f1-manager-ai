import { AppState } from './modules/app_state.js';
import { MapModuleV3 } from './modules/map_module_v3.js';
import { TimingPanelV3 } from './modules/timing_panel_v3.js';
import { PlayerGarageV3 } from './modules/player_garage_v3.js';
import { SessionControls } from './modules/session_controls.js';
import { SocketBridge } from './modules/socket_bridge.js';

(function initDashboardV3() {
    const appState = new AppState();

    const mapModule = new MapModuleV3(appState);
    mapModule.loadCircuitGeometry().catch(err => console.error('[MapV3] Circuit load failed', err));

    const timingPanel = new TimingPanelV3({
        tableContainer: document.getElementById('timing-table'),
        timerElement: document.getElementById('session-timer')
    });

    const playerGarage = new PlayerGarageV3({
        cardsContainer: document.getElementById('player-car-cards-v3'),
        overlayContainer: document.getElementById('player-setup-overlay'),
        dockElement: document.getElementById('player-dock'),
        notificationsContainer: document.getElementById('garage-notifications')
    });

    const sessionControls = new SessionControls({
        pauseButton: document.getElementById('pause-btn'),
        speedButtons: document.querySelectorAll('.speed-btn-v3'),
        speedIndicator: null
    });

    new SocketBridge({
        state: appState,
        mapModule,
        timingPanel,
        playerGarage,
        sessionControls
    });
})();
