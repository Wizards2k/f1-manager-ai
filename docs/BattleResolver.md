# BattleResolver 2.0 – Spec
last_updated: 2026-02-08
scope: Risoluzione lotte multi-car nel loop a due livelli (LapSimulator fisica → BattleResolver confronto coppie).

## 1. Obiettivo
Determinare l’esito delle lotte per posizione in ogni sezione, applicando side-by-side, blocchi, errori/collisioni, in modo coerente con skill pilota, stato vettura, setup e caratteristiche sezione.

## 2. Ruolo nel loop
1) LapSimulator calcola `update_section()` per ogni auto ignorando le altre.
2) BattleResolver riceve lo stato di sezione/posizione e valuta coppie/raggruppamenti nella stessa sezione.
3) Applica outcome: sorpasso riuscito, side-by-side persistente, attempt bloccato con penalty istantaneo, collisione/uscita.
4) Restituisce nuova ordering e flag eventi (HUD/telemetria) da commit nell’orchestratore.

## 3. Input principali (per auto)
- Sezione corrente e progressione nella sezione.
- Velocità, accelerazione potenziale, DRS disponibile, deploy ERS attuale.
- Grip effettivo (da TyreModel, con derating PU), drag/aero balance, brake fade/handling_penalty.
- Skill pilota: `overtaking`, `defending`/`race_craft`, `aggression`, `confidence`.
- Stato mentale/penalty: attempt_recent, warning collisione.
- Segnali da LapSimulator (§3.3 lap-physics-spec):
  - `overtake_window` (0-1) da pace_factor/delta_v e volontà pilota; se 0 il BR non innesca attempt.
  - `srs_flags`: abilità attive (DRS, Boost ERS, “late_brake_tag” da braking_efficiency_event) che danno bonus in staccata/attacco.
  - `traffic_constraints`: eventuali limiti di velocità imposti dalla fisica se si segue troppo da vicino.

## 4. Stati del confronto
- **Attempt**: attacco in corso.
- **Side-by-side**: due auto affiancate, decisione in uscita sezione.
- **Blocked**: difesa riuscita, attaccante resta dietro; applica penalty istantaneo (velocità/gap) per simulare perdita slancio.
- **Collision/Off-track**: incidente, con severità e possibili danni.

## 4bis. Scenari e tagging (Race vs Practice)
- **Tag primario** determinato da sessione e tipo sezione (priorità decrescente):
  1) Start/Restart (solo Race/Quali start): doppia fila, no sorpassi fino a linea, poi staccata T1 congesta.
  2) Blue flag/doppiaggio (Race/Practice con flag backmarker): sorpasso obbligato, difesa disattivata.
  3) Staccata heavy (sezione con heavy brake flag): decide l’ingresso curva.
  4) Curva/Switchback (curva singola o S combinata): side-by-side raro, può risolversi nella S.
  5) Uscita curva (rettilineo corto post curva): focus trazione/derating/ERS.
  6) Rettifilo (include casi con/ senza DRS): delta-v; se tutti hanno DRS → train malus.
- **Modificatori** (non esclusivi): Wet grip, Slipstream, Dirty air forte, DRS attivo solo attaccante, DRS train (≥3 auto con DRS), Train (≥3 auto senza DRS), Pit-exit merge, Yellow/Double Yellow/VSC/SC pre-restart = blocco sorpassi, **Team order** (compagni): cede posizione come blue flag salvo delta-v anomalo.
- **Practice/Quali**: niente blue flag; Start solo per Quali shootout/standing; DRS train meno frequente. Race: attiva blue flag, Safety/Restart, pit-exit merge.

## 4ter. Parametri chiave per scenario
- **Start/Restart**: reaction time, traction (tyre temp), low-speed torque/ERS, lane (inside/outside), aggression/confidence, collision risk alto; no sorpassi finché permesso, poi staccata T1 con congestione.
 - **Start/Restart**: trigger su stato sessione start/restart. Nessun sorpasso fino a start/SC line (`overtake_window=0`). Parametri: reaction time, traction (tyre temp/usura, fuel load), low-speed torque/ERS (DRS off), lane inside/outside (flag logico), aggression/confidence. Dopo la linea applica staccata heavy su T1 con congestione: collision risk ↑ con densità. Se SC/VSC/Yellow attivi → blocco; team order/blue flag dopo la linea → cede salvo delta-v anomalo.
- **Staccata heavy**: distanza alla brake zone, delta-v ingresso, brake fade, skill overtake vs defend, aggression/confidence, posizione inside/outside, wet penalty.
- **Curva/Switchback**: tipo curva (lenta/media/veloce), dirty air penalty, handling penalty, grip effettivo, skill race_craft/defend, aggression; side-by-side può proseguire nella S. In F1 l’overtake in curva è rarissimo: consentito solo se (a) blue flag, (b) delta-v/grip enorme, (c) guasto del difensore, (d) team order/volontà pilota.
- **Uscita curva**: trigger su rettilineo corto post curva; gap all’apex/uscita. Parametri: velocità apex/uscita, trazione (gomme/temp/usura), derating PU, ERS deploy, drag low/high DF, dirty air moderato, flag inside/outside se side-by-side. Decisione: se gap ~0–20 m e delta-v trazione > 2–4 km/h apre window; risoluzione sul mini-rettilineo/inizio staccata successiva. Team order/blue flag forzano il pass salvo delta-v anomalo; Yellow/VSC/SC bloccano.
- **Rettifilo (singolo DRS o train)**: distanza fra auto + delta-v (PU/drag) + scia e lunghezza rettilineo (serve spazio per completare). Gap trigger ~ [10–60 m], delta-v base > 3 km/h. Bonus se solo attaccante ha DRS; malus se tutti hanno DRS (train). Slipstream +, dirty air quasi nulla sul dritto ma penalizza nella curva successiva. Team order/blue flag forzano pass salvo delta-v anomalo; Yellow/VSC/SC bloccano.
- **Blue flag/doppiaggi**: difesa disattivata, il backmarker rallenta/sposta traiettoria per favorire il passaggio; outcome sorpasso garantito salvo casi **estremi** di delta-v anomalo (follower molto più lento per guasto/noia). In quei casi il BR non forza lo swap fino a delta-v/gap sicuro. Ritardi → warning/penalty; collisione solo per reazione tardiva.
- **Wet modifier**: riduce grip e braking, collision risk ↑ in staccata; dirty air meno rilevante.

Nota inside/outside (mono-rotaia): durante un side-by-side il BR assegna solo un flag logico “inside”/“outside” (in base al lato favorevole della curva/S e all’ordine di arrivo in frenata). Non esistono corsie multiple fisiche; il flag dà bonus/malus nella risoluzione, poi si torna a traiettoria unica.

## 5. Logica di decisione (outline)
1. Identifica coppie in zona sorpasso (distanza < soglia + delta velocità favorevole).
2. Calcola “chance” attacco basata su: delta velocità (PU/drag/DRS/ERS), grip disponibile, sezione (rettilineo vs curva), skill overtake vs defend, aggression.
3. Applica dirty air: in curva penalizza chi segue se scia attiva e alto downforce.
4. Se chance alta → side-by-side, altrimenti attempt bloccato: applica penalty istantaneo (riduzione v_eff/gap perso) per simulare perdita di slancio; nessun cooldown persistente.
5. Risolvi side-by-side: peso a sezione (rettilineo favorisce attaccante veloce, curva favorisce chi è all’interno), skill race_craft/defending, grip/tyre stato, derating PU.
6. Collision risk: cresce con aggression, bassa confidence, differenza traiettoria; se collisione, applica danni (Mechanical damage doc) e penalty tempo/posizione. Dopo collisione può essere applicato un breve lock per stabilizzare l’ordine.

## 6. Parametri da calibrare
- Soglie distanza e delta velocità per trigger attempt.
- Modulatori per sezione: rettilineo, curva lenta/media/veloce, staccata heavy.
- Peso skill: overtaking vs defending/race_craft, aggression vs confidence.
- Dirty air penalty per sezione downforce-heavy.
- Penalty istantanei su attempt bloccato, collision probability curve.
- Penalty tempo e danno associati (integrazione con Mechanical damage/Degradation doc).
- Entità penalty blocked (consigliata): perdita 0.05–0.15s o offset progressione sezione ~0.01–0.03, da calibrare per evitare ping-pong.

### 6bis. Range base e moltiplicatori (gap/delta-v, per scenario)
- **Rettifilo**: gap trigger ~ [10–60 m] secondo velocità media rettilineo; delta-v base > 3 km/h. Moltiplicatori: +DRS solo attaccante, –train DRS, +slipstream, –dirty air curva successiva, wet –.
- **Staccata heavy**: gap trigger breve ~ [5–25 m] all’ingresso frenata; delta-v ingresso > 5–8 km/h. Moltiplicatori: +late_brake_tag/+brake_quality, +skill overtake vs defend, +inside flag, –dirty air, –wet, –fade alto.
- **Curva/Switchback**: gap molto corto ~ [0–10 m]; delta-v minimo (side-by-side raro). Moltiplicatori: –dirty air, –handling penalty, +race_craft se inside, –wet.
- **Uscita curva**: gap ~ [0–20 m] all’apex/uscita; delta-v su trazione > 2–4 km/h. Moltiplicatori: +ERS deploy, +low drag, –derating PU, –dirty air moderato.
- **Start/Restart**: nessun sorpasso fino a linea; poi applica staccata heavy con congestione (collision risk ↑). Gap/delta-v pesati su reaction time e traction.
- **Blue flag**: nessuna soglia di chance; pass forzato salvo delta-v anomalo (follower molto più lento). In caso di anomalia, attende delta-v/gap sicuro.

## 7. Feedback pilota / radio (per scenario)
- I messaggi alimentano `driver_feedback_queue` (vedi `docs/ai-driver-engine-spec.md`) e l’HUD ingegnere. Trigger: appena il BR registra `attempt`, `blocked`, `side_by_side`, `success`, `collision`, `blue_flag_pass`, `team_order_pass`.
- **Rettifilo**
  - Attaccante: “Need more top speed/ERS” se blocked; “Overtake complete on the straight” se success. Se train: “Stuck in DRS train”.
  - Difensore: “He’s faster on the straight” quando perde; “Holding him with DRS” quando blocca.
- **Staccata heavy**
  - Attaccante: “Late braking worked” (success + evento `late_brake_tag`); “Couldn’t dive, brakes fading” se blocked o fade alto.
  - Difensore: “Covered inside line” se blocca; “Locked up defending” se collisione/minor damage.
- **Curva/Switchback**
  - Attaccante: “Too much dirty air, can’t stay side-by-side” salvo condizioni speciali; “Switchback worked” se sorpasso raro.
  - Difensore: “Holding the apex” quando regge; “Going wide, he might cut back” se handling penalty alto.
- **Uscita curva**
  - Attaccante: “Need more traction/ERS on exit” se blocked; “Got him on traction” se sorpasso completato.
  - Difensore: “Struggling for traction” o “Battery empty, can’t cover exit”.
- **Start/Restart**
  - Messaggi legati a reaction/traction: “Bad launch, lost a spot” / “Great launch, inside line T1”.
  - Difensore: “Got squeezed in T1” se collision risk alto; “Holding position off the line”.
- **Blue flag / Team order**
  - Backmarker/compagno: “Blue flag, letting him through” / “Team orders, switching cars”.
  - Leader/beneficiario: “He needs to move” se ritardo; “Thanks, clean pass” quando avviene.
- **Blocchi globali (Yellow/VSC/SC)**
  - Tutti: “No overtakes under yellow/VSC” con richiamo se tentano.
- **Collisione**
  - Entrambi: “Contact at [section]” + severity/damage info, integra `Mechanical damage` doc.

## 8. HUD/telemetria eventi
- `battle_attempt`, `battle_blocked`, `side_by_side`, `overtake_success`, `collision`, `cooldown_active` con durata.
- Metadati: sezione, delta vel, skill diff, stato gomme/PU/DRS/ERS, esito collisione.

## 9. QA harness
- Scenari deterministici: DRS train in rettilineo, attacco in curva lenta con top speed inferiore ma più grip, wet stint con poco grip, lotta con difensore ad alto defending, caso collisione forzata per test danni.
- Asserzioni: ordering finale, eventi emessi, cooldown aggiornati, nessun sorpasso impossibile in curva stretta con bassa chance.

## 10. Integrazioni
- Legge grip/derating/danni da LapSimulator/Degradation doc; scrive eventi per orchestratori (Practice/Race) e HUD.
- Usa mapping sezione (rettilineo/curva, heavy braking) dal telemetry/track profile.