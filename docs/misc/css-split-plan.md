# CSS Split Plan for Dashboard

## Rationale
- Current `python_backend/static/css/dashboard.css` has grown beyond 800 lines, making it hard to maintain.
- Modular CSS improves readability, allows parallel work on circuit, timing, garage, and setup areas, and prepares the ground for future theme variations.
- We want a "pure CSS" split with no build step initially, leveraging multiple `<link>` tags (or `@import`) so the refactor stays lightweight.

## Target Structure
| File | Scope |
| --- | --- |
| `static/css/dashboard.base.css` | Reset, typography, shared tokens (colors, spacing, fonts), high-level layout containers (`body`, `.container`). |
| `static/css/dashboard.circuit.css` | Map canvas, circuit info, leaflet overrides. |
| `static/css/dashboard.timing.css` | Timing table, session timer, standings and mini widgets. |
| `static/css/dashboard.garage.css` | Player dock, car cards, tyre/fuel controls, actions, status banners. |
| `static/css/dashboard.setup.css` | Setup overlay panel, slider badges, feedback states (recently added). |

`base.html` will load the files in the order above using multiple `<link>` tags so the cascade remains predictable.

## Migration Steps
1. **Annotate current CSS** – mark block boundaries in the monolithic file to map sections to the new files.
2. **Extract sequentially**:
   - Copy common variables/resets into `dashboard.base.css`.
   - Move circuit/map rules to `dashboard.circuit.css`.
   - Move timing panel rules to `dashboard.timing.css`.
   - Move garage/card controls to `dashboard.garage.css`.
   - Move setup overlay rules (recent addition) to `dashboard.setup.css`.
3. **Wire up templates** – update `python_backend/templates/base.html` to include the five `<link>` tags in the correct order.
4. **Smoke test** – load `/race` locally and verify styles; because there is no bundler, the browser should fetch five CSS files automatically.
5. **Cleanup** – remove the old `dashboard.css` once parity is confirmed.

## Future Enhancements
- When ready, extend `scripts/rebuild_assets.py` (or add an npm task) to concatenate/minify these modular files into a single bundle for production.
- Consider migrating to CSS custom properties shared via `dashboard.base.css` to ease theming.
- Optionally add a lint/check to ensure new sections land in the correct file.
