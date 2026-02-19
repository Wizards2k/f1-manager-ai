# UI V3 Migration Specification Document

## Objective
Create a fully autonomous V3 UI layout that does not depend on V1 CSS/JS, eliminating dynamic resize logic and fixing layout stability issues.

## Key Principle: Complete Autonomy
The V3 UI must function independently without loading or referencing any V1 styles or scripts. All styles, components, and behaviors must be self-contained in V3-specific files.

## Migration Steps (Sequential)

### Recap (Feb 4)

**What we changed today**
- `dashboard-v3.js` is now the single entrypoint that instantiates a shared `AppState` and wires Map, Timing Panel, Garage, Session Controls, and Socket Bridge exactly like V1.
- Socket-driven updates are restored (no polling); `SocketBridge` pushes session + car data into `AppState`, and UI modules render off the shared state.
- Timing panel regained purple/green sector coloring via session-best wiring, and the session controls now use V1 button classes, active states, and pause iconography.
- Player dock layout remains scoped to V3 CSS with fixed notifications overlay and fullscreen setup modal, matching the legacy visual treatment without loading V1 assets.

**Backend-facing differences vs V1 (still under review)**
- Session bootstrap currently replays the last-known cache; we need an explicit reset/clear so stale driver data is not shown when a new session starts.
- Setup overlay drafts are not persisted when the driver returns to box (state reset or missing apply hook) and need to mirror V1 behavior.
- Driver feedback colors/sliders now render, but we still have to validate the notification pipeline after the setup persistence fix.

**Todo (parity blockers)**
1. Add a session-reset hook to `AppState`/`SocketBridge` so cached car + session values clear before new data arrives.
2. Persist setup overlay adjustments (drafts + applied values) across send-out/box cycles using the shared state store.
3. Verify driver feedback events (notifications + slider statuses) once setup persistence is fixed.

### Current Status

- Map V3: ✅ migrated, fixed layout
- Dock V3: ✅ visually aligned with V1, notifications capped, modal overlay full screen
- Timing V3: 🚧 basic table visible with V3 modules (map_module_v3.js, player_garage_v3.js, timing_panel_v3.js)
- Timing V3 polling: 🚨 currently uses new fetch/setInterval logic; backend expects socket bridge (V1 logic). Need to revert to V1 methods (state-driven updates, no additional polling) to avoid API overload.

## Remaining Gaps

1. **Timing table parity**
- `python_backend/templates/index-v3.html` - Map container

**Requirements**:
- Map height fixed via CSS grid/flex (no JS calculations)
   - Remove temporary `console.log` debug statements once layout confirmed.
   - TODO (blocking): revert `TimingPanelV3` methods to match `TimingPanel` (V1) behavior exactly (no custom polling) and ensure backend socket bridge (or equivalent) feeds data, as current implementation causes backend issues.

2. **Send Out button**
   - Verify `PlayerGarageV3` handles `/send_out` response, applies state updates, and UI reflects car leaving pit.
- Map fills its container via CSS only

**Layout approach**:
```
.game-area {
  display: grid;
  grid-template-rows: 1fr 260px; /* Map | Dock */
}
.map-area {
  position: relative;
  overflow: hidden;
}
#circuit-map {
  width: 100%;
  height: 100%;
}
```

---

### Step 2: Dock/Garage V3  
**Goal**: Fixed dock with proper control layout

**Files to create/modify**:
- `python_backend/static/js/modules/player_garage_v3.js` - New module
- `python_backend/static/css/dashboard-v3.css` - Dock & car cards section
- `python_backend/templates/index-v3.html` - Dock container

**Requirements**:
- Dock height fixed at 260px (no expansion)
- Setup opens as modal overlay, NOT dock expansion
- All control styles self-contained in V3 CSS
- No dependency on V1 `.player-dock`, `.control-grid` classes

**Control layout (3 rows)**:
```
Row 1: [Tyre Compound + %] [Fuel %] [Stint Laps]
Row 2: [ICE Map] [ERS Mode] [Driver Push (50% width)]
Row 3: [Send Out] [Box] [Setup]
```

**CSS Strategy**:
- Use CSS Grid or Flexbox with explicit row classes
- No negative margins (`offset-left`, etc.) - use grid placement
- All input/select/range styles defined in V3
- Button styles (Send/Box/Setup) defined in V3

---

### Step 3: Timing Panel V3
**Goal**: Fully visible timing panel without overlay issues

**Files to create/modify**:
- `python_backend/static/css/dashboard-v3.css` - Timing section
- `python_backend/templates/index-v3.html` - Timing container

**Requirements**:
- Fixed width (420px suggested)
- Isolated stacking context (no z-index conflicts)
- All timing styles self-contained
- State indicator and lap count visible

**Layout**:
- Driver row: Grid with explicit columns
- All timing colors (session best, personal best, etc.) in V3 CSS
- No dependency on V1 `.timing-container` styles

### Feb 5 Updates – Setup Feedback & Apply Flow

**Summary**

- Restored V1 behavior where setup feedback is generated only after a completed hot lap followed by box entry, and ensured Apply simply stores slider values without triggering feedback.
- Added per-car hot-lap tracking and backend logging so both player cars remain independent and debuggable.

**Backend Changes**

1. `RaceCar` now exposes `_generate_setup_feedback(trigger)` and calls it automatically in `enter_box()` whenever a player-controlled car with `has_completed_hot_lap` returns to the garage. This mirrors the real-world workflow (feedback arrives when telemetry from the stint is available) and removes any UI coupling.
2. Introduced `/api/player/car/<driver>/setup/save` which only validates + persists `player_config.setup` while the car is in BOX. The response returns the serialized car so the frontend can refresh its state. Legacy `/setup` remains the telemetry-driven feedback endpoint, triggered internally.
3. Added structured debug logs (`setup_saved`, `setup_feedback_generated`, etc.) into `/tmp/f1_setup_debug.log` to trace each phase (Apply, hot lap, box entry) per driver.

**Frontend Changes (`player_garage_v3.js`)**

1. The Apply button now invokes `/setup/save` and overlays update by applying the car payload returned by the server, preventing race-update events from overwriting drafts.
2. Setup sliders display the actual stored values (from `player_config.setup`) instead of overwriting them with `setup_feedback.value`. Feedback still colors the control and can optionally show a "Recommended X" badge for clarity.
3. After saving, the overlay either closes (if the car stays in BOX) or re-renders using the refreshed car state, so both cars keep their independent drafts/feedback.

**Testing Notes**

1. Perform a full stint: out-lap → 3× hot lap → in-lap → box entry. Upon reopening Setup, sliders remain at the saved values while the feedback colors reflect the latest telemetry.
2. Modify sliders, press Apply, reopen immediately (without send-out): values persist thanks to `/setup/save` response syncing the local AppState.
3. Repeat with both drivers to confirm `has_completed_hot_lap` and feedback storage are scoped per car.

---

## Architecture Rules

### CSS Isolation
1. All V3 selectors prefixed or nested under V3 containers
2. No global element selectors that might conflict with V1
3. Reset/normalize styles self-contained in V3 scope

### JavaScript Isolation  
1. V3 modules import/export independently
2. No shared state with V1 modules
3. Event listeners attached to V3 elements only

### HTML Structure
```html
<div class="dashboard-v3">
  <div class="game-area">
    <div class="map-area">
      <div id="circuit-map"></div>
      <div class="overlay-layer-v3">...</div>
    </div>
    <div class="player-dock-v3">...</div>
  </div>
  <div class="timing-panel-v3">...</div>
</div>
<div id="player-setup-overlay" class="setup-modal-v3"></div>
```

## Critical Success Criteria
- [ ] No dynamic resize calculations in JavaScript
- [ ] Map size controlled purely by CSS
- [ ] Setup modal opens without affecting map size
- [ ] Timing panel never obscured by overlays
- [ ] All V3 components work with V1 CSS commented out in base.html
- [ ] Dock controls layout matches specification exactly

## Lessons from Failed Attempt
1. **Don't copy V1 CSS structure blindly** - adapt layout logic for fixed sizing
2. **Don't use negative margins for layout** - use proper grid/flex placement  
3. **Test each component in isolation** before combining
4. **Verify V1 CSS is NOT being applied** when testing V3

## Testing Protocol
1. Comment out V1 CSS in base.html temporarily
2. Verify each component renders correctly standalone
3. Re-enable V1 CSS only after V3 is fully autonomous
4. Final test: V3 works identically with or without V1 CSS loaded
