---
title: Motore fisico lap time – v0.1 (Auto/Aerodinamica)
version: 0.1
last_updated: 2026-02-06
scope: "Definizione del modello fisico per il contributo Auto (aerodinamica) al tempo sul giro"
---

## 1. Obiettivo
Stabilire le regole del motore fisico per calcolare il tempo sul giro utilizzando componenti realistici dell’auto (solo sezione aerodinamica al momento). Il documento descrive come mappare i valori 1–100 delle parti dell’auto in downforce (DF) e drag, e come questi incidono sui segmenti del tracciato senza impostazioni manuali per curva.

## 2. Dati disponibili
- **Telemetria 2025** (`*_2025_Q.json`): velocità e distanza lungo il giro, usate per calcolare velocità di riferimento per ogni sezione.
- **Mapping circuito** (`*_mapping.json`): lista `sections[]` con tipo (`Straight`, `SlowCorner`, `FastCorner`, ecc.), start/end metri e attributi legacy.
- **RaceCar attuale**: possiede hook per gomme, pilota, setup; verrà estesa con il nuovo profilo aerodinamico.

## 3. Componenti Auto (valori 1–100)
| Componente        | Parametri                          | Note |
|-------------------|------------------------------------|------|
| Ala anteriore     | `downforce`, `drag`, `angle`       | L’angolo modifica direttamente DF/drag.
| Ala posteriore    | `downforce`, `drag`, `angle`       | Drag naturalmente più alto.
| Sidepods          | `downforce`, `drag`, `cooling`     | Contribuisce a entrambi gli assi (50/50) e fornisce raffreddamento.
| Fondo anteriore   | `downforce`, `drag`                | DF concentrato sull’anteriore.
| Fondo posteriore  | `downforce`, `drag`                | DF per il posteriore.
| Cofano motore     | `downforce`, `drag`, `cooling`     | Influenza aerodinamica del retrotreno e il raffreddamento.
| B-Wing            | `downforce`, `drag`                | Mini ala posteriore aggiuntiva.
| Sospensione ant.  | `efficiency`, `df_bonus`, `rigidity` | Efficienza gestisce bump/kerb, `df_bonus` aggiunge grip meccanico, rigidità controlla trasferimento carico.
| Sospensione post. | `efficiency`, `df_bonus`, `rigidity` | Stessa logica per l’asse posteriore.
| Ride height ant.  | `height_value` (1-100)              | Valore alto = assetto più alto (protezione bump), basso = più carico ma rischio bottoming.
| Ride height post. | `height_value` (1-100)              | Come sopra per retrotreno.
| Antiroll bar ant. | `skill`, `rigidity` (1-100)         | `skill` rappresenta qualità dell’elemento, `rigidity` regola morbidezza 1 (soft) → 100 (hard).
| Antiroll bar post.| `skill`, `rigidity` (1-100)         | Stessa logica per l’asse posteriore (stabilità uscita curva / sovrasterzo).
| Mechanical grip   | `grip_base` (1-100)                 | Grip meccanico di riferimento che scala tutte le curve lente.

## 4. Aggregati aerodinamici
Calcolati ogni tick o quando cambia il setup:
- `df_front = front_wing.df + front_floor.df + sidepods.df * 0.5`
- `df_rear = rear_wing.df + rear_floor.df + engine_cover.df + b_wing.df + sidepods.df * 0.5`
- `df_total = df_front + df_rear`
- `drag_total = somma drag componenti`
- `aero_balance = df_front / df_total` (target 0.50 ± epsilon)
- Le sospensioni forniscono moltiplicatori `susp_front_mult`, `susp_rear_mult` (es. 0.85–1.15) basati su `efficiency` e `rigidity`, oltre a un bonus additivo `df_bonus` (convertito in punti DF).
- Raffreddamento disponibile: `cooling_capacity = sidepods.cooling + engine_cover.cooling`; usato per valutare se le mappe motore richieste rientrano nella finestra termica.
- Ride height target per circuito: ogni pista definisce `ride_height_optimal_front/rear`; scostamenti riducono il `df_bonus` e aumentano `bump_penalty` se sotto la soglia o drag se troppo alti.
- Antiroll multipliers: `antiroll_front_mult`, `antiroll_rear_mult` (0.9–1.1) applicati rispettivamente a curve veloci (front) e curve lente/uscita (rear) per modulare `v_section` e usura gomme sull’asse esterno.
- Grip meccanico effettivo: `grip_mech_eff = grip_base * f(ride_height, antiroll, tyre_state)` utilizzato nei segmenti `SlowCorner`/`Traction`.
- Formula proposta per asse anteriore (simile per posteriore):
  - `susp_front_mult = 0.85 + 0.3 * (efficiency_front - 50)/50`
  - `df_front_effective = (df_front + df_bonus_front) * clamp(susp_front_mult, 0.8, 1.2)`
  - `rigidity_front` modula il trade-off: valori alti migliorano curve veloci ma aumentano `bump_penalty` su sezioni sconnesse; valori bassi proteggono i bump ma riducono precisione e quindi `df_bonus`.

## 5. Regola di calcolo velocità per sezione
Invece di definire manualmente la velocità per ogni curva:
1. **Velocità base** (`v_base(section)`) = media telemetria 2025 per quella sezione.
2. **Coefficiente curva** (`curve_factor`) derivato automaticamente dal tipo sezione:
   - Straight → 0.0
   - SlowCorner → 0.4
   - MediumCorner → 0.7
   - FastCorner → 1.0
3. **Downforce effettivo**:
   - Sezione con curvatura positiva (curva a destra) → usa `df_front` per l’avantreno dominante.
   - Curvatura negativa → usa `df_rear`.
   - DF effettivo = `df_axis * suspension_axis_mult` normalizzato rispetto a `df_ref` (valore medio 70).
4. **Velocità finale curva**:
   ```
   v_section = v_base * (1 + curve_factor * k_df * (df_eff - df_ref) / df_ref)
   v_section = v_section * (1 - handling_penalty)
   ```
   - `k_df` coefficiente globale (es. 0.15).
   - `handling_penalty` dipende da `|aero_balance - target|` (sottosterzo/sovrasterzo penalizza curve relative all’asse carente).
5. **Rettifili**: usano `drag_total` e la potenza motore (placeholder) per applicare `delta_drag`:
   ```
   v_section = min(v_base + delta_power - k_drag * (drag_total - drag_ref), v_cap)
   ```

Questo schema scala automaticamente per tutte le curve/rettifili, senza editing manuale. DF alto → curve più veloci; drag alto → top speed ridotta.

## 6. Collegamento al modello 60/30/10
- L’output delle formule di sezione sostituisce la parte “Auto 60%” della vecchia formula. Aggregando i tempi dei segmenti otteniamo il contributo reale dell’auto.
- Le gomme (30%) limitano il DF sfruttabile: se grip < soglia, `df_eff` viene ridotto.
- Il pilota (10%) può compensare piccoli squilibri (riduce `handling_penalty` o sfrutta meglio il DF disponibile).

## 7. Componenti auto future

### 7.1 Motore / Power Unit (v0.2)
Suddiviso in due macro blocchi:

#### 7.1.1 ICE (Internal Combustion Engine)
- Parametri:
  - `power_rating` (1-100) → cavalli disponibili.
  - `reliability` (1-100) → consumo per km e possibilità di usare mappature spinte.
  - `fuel_efficiency` (1-100) → quanto consuma per unità di potenza; valori alti riducono il burn rate.
  - `max_km` (km teorici) e `km_used` → tracking usura season-based.
  - `available_maps`: lista di mappature definite come `% potenza` rispetto al rating base.
    - Range consentito 50%–110%; mappa >100% richiede `reliability` elevata.
- Mappature ICE (esempio iniziale):
  | Nome      | % Potenza | Consumo km | Note |
  |-----------|-----------|------------|------|
  | Economy   | 70%       | basso      | Uso in fuel saving.
  | Race      | 95%       | medio      | Default gara.
  | Qualy     | 105%      | alto       | Disponibile se `reliability >= 70`.
- Effetto sul calcolo rettilinei:
  - `delta_power = k_power * (power_rating * map_multiplier - power_ref)`.
  - `fuel_burn_rate = base_consumption * map_multiplier / clamp(fuel_efficiency, 1, 100)`.
  - Penalità se `km_used / max_km` supera soglia (potenza limitata o rischio failure).

#### 7.1.2 ERS / Sistema elettrico (MGU-K/H)
- Parametri:
  - `power_rating_kw` (1-100) mappato sui limiti FIA (~120 kW max).
  - `reliability` (1-100) e contatore `max_km`/`km_used` analoghi all’ICE.
  - Mappature predefinite (statiche):
    1. **Gara** – output equilibrato, neutral.
    2. **Qualifica** – erogazione massima per un giro.
    3. **Sorpasso** – boost breve ad alto consumo.
    4. **Recupero** – priorità a ricarica (output ridotto).
    5. **Safety Car** – output minimo, efficienza alta.
- Per ciascuna mappa definiamo: `% output`, `% recupero`, `consumo_batteria`, `limiti durata`.
- L’utente seleziona la mappa, il sistema calcola l’energia disponibile/giro e aggiorna la batteria.
- Il contributo ERS entra nel delta rettilineo insieme all’ICE:
  - `delta_power = delta_power_ice + k_ers * (ers_output - ers_ref)`.
  - Se la mappa ERS supera il limite FIA (es. >120 kW), si clampa e segnala.
- Stato batteria (SoC) da tracciare per vincolare l’uso di mappe Sorpasso/Qualy: `ers_energy` in MJ con limiti per giro (es. 4 MJ deploy / 2 MJ recovery).
- Temperature ERS: se l’output alto persiste oltre soglia, attivare derating temporaneo o passaggio forzato a modalità Recupero.

#### 7.1.3 Interfaccia dati proposta
```
@dataclass
class EngineMap:
    name: str
    power_percent: float  # 0.5 - 1.1
    consumption_rate: float
    duration_laps: Optional[int]

@dataclass
class ICEUnit:
    power_rating: int  # 1-100
    reliability: int  # 1-100
    max_km: float
    km_used: float
    maps: Dict[str, EngineMap]
    active_map: str

@dataclass
class ERSMode:
    name: str
    output_kw: int   # limitato ~120 kW
    recovery_rate: float
    consumption_rate: float

@dataclass
class ERSUnit:
    power_rating_kw: int
    reliability: int
    max_km: float
    km_used: float
    modes: Dict[str, ERSMode]
    active_mode: str

@dataclass
class PowerUnit:
    ice: ICEUnit
    ers: ERSUnit
```

#### 7.1.4 Impatto nel modello
- Top speed rettilineo = funzione di `ICE power`, `ERS output`, `drag_total`, `rear_wing angle`.
- `delta_power` calcolato per sezione rettilinea e applicato in `v_section` (vedi §5 punto 5).
- `reliability` e `km_used` determinano rischio di failure o limitazione potenza (es. `power_cap = power_rating * (1 - wear_coeff)`).
- `fuel_tank`: tenere un contatore di kg carburante; il `fuel_burn_rate` delle mappe ICE scala il consumo e impone strategie di fuel saving (se il livello scende sotto soglie predefinite si forzano mappe Economy).
- Temperature ICE/raffreddamento: introdurre `cooling_efficiency = cooling_capacity / cooling_ref` che, se insufficiente rispetto alla mappa attiva, riduce progressivamente il `power_rating` o costringe a mappe meno spinte.

### 7.2 Grip meccanico / Telaio (v0.3)
- Valori da gestire: `ride_height_front/rear`, `antiroll_front/rear`, `mechanical_grip` base (che assorbe la parte “rigidity” delle sospensioni quando serve).
- Impatto: moltiplicatori su `df_eff` alle basse velocità e controllo sui bump/kerb (sinergia con sospensioni).
- Penalità previste se troppo basso/rigido: aumento usura gomme, probabilità errori.

### 7.3 Gomme (v0.4)
- Evoluzione della classe `Gomma`: aggiungere temperatura, finestra operativa, delta grip per compound.
- Il DF effettivo verrà limitato da `grip_available = f(temperatura, vita, compound)`.
- Output richiesto: `tire_grip_multiplier` e `wear_rate` da applicare ai segmenti.

### 7.4 Pilota (v0.4)
- Riuso skill esistenti (`velocita`, `qualifica`, `gara`, `costanza`, `stile_sottosterzo/sovrasterzo`).
- Effetti:
  - Riduzione `handling_penalty` (pilota bravo sfrutta meglio bilanciamento non ideale).
  - Varianza minore nei tempi settore → maggiore consistenza.
  - Bonus situazionale (qualifica vs gara) selezionando skill appropriate.

## 8. Roadmap versioni
- **v0.1** (questo documento): auto – aerodinamica + regola DF/drag.
- **v0.2**: aggiungere motore/power unit nel calcolo (rettilinei, ERS, drag dinamico).
- **v0.3**: introdurre grip meccanico (ride height, antiroll, sospensioni avanzate) e collegarlo a gomme/degrado.
- **v0.4**: integrare completamente gomme (modello termico/degrado) e pilota (skill dinamiche).
- Versioni successive: meteo, track evolution, errori pilota, DRS/ERS dinamico.

## 9. Prossimi passi immediati
1. Implementare le classi `AeroPart`, `Suspension`, `CarAeroProfile` e integrarle in `RaceCar`.
2. Generare i coefficienti `v_base` e `curve_factor` per ogni sezione dai dataset esistenti (script helper).
3. Aggiornare il motore di simulazione per usare `v_section` in luogo dei bonus statici Auto.
4. Stendere gli scheletri dati per motore, grip meccanico, gomme e pilota (anche se non ancora implementati) per mantenere coerenza.
5. Validare su un circuito pilota confrontando i delta tra auto “high DF” e “low DF”.
