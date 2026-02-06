# F1 Manager AI

Simulatore manageriale F1 totalmente offline, basato su telemetria FastF1 e motore fisico modulare. Il progetto combina un backend Python per simulazione e generazione dati, un frontend React per UI gara e documentazione tecnica dettagliata per garantire coerenza tra fisica e contenuti.

## Stato attuale

- **Telemetria 2025 completa**: tutti i 24 circuiti generati/validati via `scripts/generate_circuit_config.py` e `scripts/validate_circuit_config.py` usando mapping FastF1.
- **Spec motore fisico v0.1** (`docs/lap-physics-spec-v0.1.md`): copre Auto (aerodinamica, cooling, sospensioni, ride height, antiroll, grip meccanico) e roadmap per Motore/Gomme/Pilota.
- **Pipeline layout FastF1** (`docs/fastf1-circuit-layout-plan.md`): definisce come trasformare posizioni live in GeoJSON statici.
- **Physics roadmap** aggiornata: regola “100% offline” ribadita e percorsi futuri.
- **Branch attivo**: `physics-engine`.

## Visione

1. **Auto (60%)** – dettagliata per componenti 1–100 (ali, floor, sidepods, B-wing, cooling, sospensioni, ride height, antiroll, power unit ICE/ERS).
2. **Gomme (30%)** – evoluzione prevista con temperatura, finestra operativa, degrado per compound.
3. **Pilota (10%)** – skill dinamiche per compensare squilibri e definire consistenza.
4. **Condizioni pista** – meteo, evoluzione grip, safety car (step successivo).

## Prossimi passi

1. **Spec gomme (v0.2)**: modello termico, finestra ottimale, degrado dinamico.
2. **Spec pilota (v0.2)**: collegare skill esistenti a penalità/bonus nel motore fisico.
3. **Integrazione script**: collegare `CarAeroProfile`, `PowerUnit`, `MechanicalGrip` a `RaceCar` e al loop di simulazione.
4. **UI/UX**: aggiornare frontend per mostrare nuovi stati (setup, temp motore, mappe ICE/ERS).
5. **Batch layout**: generare GeoJSON FastF1 per tutti i circuiti e sostituire i file legacy.

## Struttura

- `python_backend/` – Flask backend + motore simulazione.
- `scripts/` – utility per generare/validare dati (telemetria, DRS, config).
- `docs/` – specifiche (lap physics, roadmap, layout FastF1, gameplay, ecc.).
- `dashboard/` – frontend React (mappe, driver list, race view).

## Come contribuire

1. Creare branch feature/bugfix dedicato (`feature/<descrizione>`).
2. Seguire le spec in `docs/` prima di implementare.
3. Usare `scripts/*.py` per generazione/validazione.
4. Aggiornare il README e la documentazione quando si aggiungono moduli significativi.

## License

MIT
