# Index.html Refactor Plan
This plan outlines how to decompose the monolithic index.html frontend into manageable, testable pieces while keeping the current UI functional throughout the transition.

## Current Pain Points
- Single 1.6K-line template mixes HTML, CSS, and JS, making changes risky and hard to review.
- Inline CSS prevents reuse and slows iteration on styling/themes.
- Business logic for map, garage, and timing lives in one script, limiting readability and reuse.
- No shared base template or components, so future pages would duplicate layout code.

## Refactor Principles
1. Preserve existing behavior at each step; ship small, verifiable deltas.
2. Extract reusable layout blocks using Jinja inheritance/includes.
3. Move presentation concerns (CSS) and behavior (JS) into static assets with modular structure.
4. Introduce clear namespaces (e.g., window.F1 or ES modules) for cross-module communication.
5. Add light documentation/readme per module to ease onboarding.

## Phased Plan
1. **Foundation (Template Skeleton)**
   - Create `base.html` with shared `<head>`, fonts, and container layout.
   - Split current `index.html` into blocks (`map_panel`, `timing_panel`, `player_dock`).
   - Ensure template renders identically by referencing existing inline CSS/JS for now.

2. **Static Assets Extraction**
   - Move CSS into `static/css/app.css`; keep sections commented (layout, dock, timing, map).
   - Replace inline `<style>` with `<link>` reference; verify asset pipeline is configured in Flask/FastAPI setup.
   - Extract JS into `static/js/app.js` while keeping a single module; load via `<script defer>`.

3. **Modular JavaScript**
   - Break `app.js` into modules: `map.js`, `garage.js`, `timing.js`, `sessionControls.js`, `sockets.js` (ES modules or IIFE namespaces).
   - Provide a central initializer (e.g., `app.js`) that wires modules together and exposes shared state (player car map, session bests).

4. **Component & Partial Templates**
   - Create partials for garage cards (`_car_card.html`) and timing rows (`_timing_row.html`) if server-side rendering is needed later.
   - Consider Jinja macros for repeated snippets (state badges, sector rows) to keep HTML DRY.

5. **Enhancements & Testing**
   - Add linting/formatting: Prettier (HTML/CSS/JS) and ESLint config for JS modules.
   - Document frontend structure in `python_backend/README.md` (how to add panels, where assets live).
   - Optional: introduce a lightweight build step (Vite/Rollup) if modules grow further.

6. **Future-ready Hooks**
   - Evaluate whether a frontend framework or component library is warranted for dynamic sections.
   - Add hooks for localization/multi-session support as needed once structure is modular.
