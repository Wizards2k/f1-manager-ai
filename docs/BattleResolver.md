# BattleResolver 2.0 – Spec
last_updated: 2026-02-08
scope: Risoluzione lotte multi-car nel loop a due livelli (LapSimulator fisica → BattleResolver confronto coppie).

## 1. Obiettivo
Determinare l’esito delle lotte per posizione in ogni sezione, applicando side-by-side, blocchi, errori/collisioni, in modo coerente con skill pilota, stato vettura, setup e caratteristiche sezione.

## 2. Ruolo nel loop
1) LapSimulator calcola `update_section()` per ogni auto ignorando le altre.
2) BattleResolver riceve lo stato di sezione/posizione e valuta coppie/raggruppamenti nella stessa sezione.
3) Applica outcome: sorpasso riuscito, side-by-side persistente, attempt bloccato, collisione/uscita, cooldown.
4) Restituisce nuova ordering e flag eventi (HUD/telemetria) da commit nell’orchestratore.

## 3. Input principali (per auto)
- Sezione corrente e progressione nella sezione.
- Velocità, accelerazione potenziale, DRS disponibile, deploy ERS attuale.
- Grip effettivo (da TyreModel, con derating PU), drag/aero balance, brake fade/handling_penalty.
- Skill pilota: `overtaking`, `defending`/`race_craft`, `aggression`, `confidence`.
- Stato mentale/penalty: cooldown attivo, attempt_recent, warning collisione.

## 4. Stati del confronto
- **Attempt**: attacco in corso.
- **Side-by-side**: due auto affiancate, decisione in uscita sezione.
- **Blocked**: difesa riuscita, attaccante resta dietro.
- **Cooldown**: tempo minimo prima di un nuovo tentativo (più lungo dopo collisione).
- **Collision/Off-track**: incidente, con severità e possibili danni.

## 5. Logica di decisione (outline)
1. Identifica coppie in zona sorpasso (distanza < soglia + delta velocità favorevole).
2. Calcola “chance” attacco basata su: delta velocità (PU/drag/DRS/ERS), grip disponibile, sezione (rettilineo vs curva), skill overtake vs defend, aggression.
3. Applica dirty air: in curva penalizza chi segue se scia attiva e alto downforce.
4. Se chance alta → side-by-side, altrimenti attempt bloccato (entra cooldown breve).
5. Risolvi side-by-side: peso a sezione (rettilineo favorisce attaccante veloce, curva favorisce chi è all’interno), skill race_craft/defending, grip/tyre stato, derating PU.
6. Collision risk: cresce con aggression, bassa confidence, differenza traiettoria; se collisione, applica danni (Mechanical damage doc) e penalty tempo/posizione.
7. Aggiorna cooldown: lungo se collisione, medio se blocked, breve se side-by-side riuscito.

## 6. Parametri da calibrare
- Soglie distanza e delta velocità per trigger attempt.
- Modulatori per sezione: rettilineo, curva lenta/media/veloce, staccata heavy.
- Peso skill: overtaking vs defending/race_craft, aggression vs confidence.
- Dirty air penalty per sezione downforce-heavy.
- Cooldown (blocked, side-by-side, collision) e collision probability curve.
- Penalty tempo e danno associati (integrazione con Mechanical damage/Degradation doc).

## 7. HUD/telemetria eventi
- `battle_attempt`, `battle_blocked`, `side_by_side`, `overtake_success`, `collision`, `cooldown_active` con durata.
- Metadati: sezione, delta vel, skill diff, stato gomme/PU/DRS/ERS, esito collisione.

## 8. QA harness
- Scenari deterministici: DRS train in rettilineo, attacco in curva lenta con top speed inferiore ma più grip, wet stint con poco grip, lotta con difensore ad alto defending, caso collisione forzata per test danni.
- Asserzioni: ordering finale, eventi emessi, cooldown aggiornati, nessun sorpasso impossibile in curva stretta con bassa chance.

## 9. Integrazioni
- Legge grip/derating/danni da LapSimulator/Degradation doc; scrive eventi per orchestratori (Practice/Race) e HUD.
- Usa mapping sezione (rettilineo/curva, heavy braking) dal telemetry/track profile.