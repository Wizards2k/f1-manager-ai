# UI V3 Migration Specification Document

## Objective
Create a fully autonomous V3 UI layout that does not depend on V1 CSS/JS, eliminating dynamic resize logic and fixing layout stability issues.

## Key Principle: Complete Autonomy
The V3 UI must function independently without loading or referencing any V1 styles or scripts. All styles, components, and behaviors must be self-contained in V3-specific files.

## Migration Steps (Sequential)

### Step 1: Map Module V3
**Goal**: Fixed-size map without dynamic resize logic

**Files to create/modify**:
- `python_backend/static/js/modules/map_module_v3.js` - New module
- `python_backend/static/css/dashboard-v3.css` - Map section
- `python_backend/templates/index-v3.html` - Map container

**Requirements**:
- Map height fixed via CSS grid/flex (no JS calculations)
- Remove all `invalidateSize()` calls triggered by UI changes
- No `ResizeObserver` or `window.resize` listeners for map sizing
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
