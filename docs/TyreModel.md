# SPECIFICATION: Tyre Physics Engine v0.2 (Thermal & Dynamic)
# Project: F1 Manager AI
# Date: 2026-02-06

## 1. Obiettivo
Implementare un modello termico multi-strato per le gomme che risponda alla segmentazione del circuito (da `italy_mapping.json`) e ai fattori ambientali (Air/Track Temp).

## 2. Core Physics: Two-Layer Thermal Model
Ogni gomma deve tracciare due temperature distinte:
1. **Surface Temperature (T_surf)**: Alta reattività. Influenzata da attrito, frenata e raffreddamento dell'aria.
2. **Core Temperature (T_core)**: Alta inerzia. Influenzata dal calore trasferito dalla superficie e dalla deformazione della carcassa.

### Equazione del Bilancio Termico:
`dT/dt = (Heat_Gen - Heat_Loss) / Thermal_Mass`
- **Heat_Gen (Generazione)**:
- `Friction_Heat`: Alta nelle curve (`SlowCorner`, `FastCorner`), proporzionale a `Lateral_G` e `Slip_Angle`.
- `Braking_Heat`: Applicato alle gomme anteriori durante la decelerazione.
- **Heat_Loss (Dissipazione)**:
- `Convection`: `k_air * Air_Speed * (T_surf - Air_Temp)`.
- `Conduction` verso pista: `k_track * (T_surf - Track_Temp)`.
- **Scambio Surface ↔ Core**: `core_exchange = (T_surf - T_core) * conduction_coeff`; T_core ha maggiore massa termica → risposta più lenta.

## 3. Matrice Mescole Pirelli (C1-C5)
Implementa le seguenti costanti per grip e finestre termiche:

| Mescola | Window Ottimale | Grip Multiplier | Degradation Rate |
| :--- | :--- | :--- | :--- |
| **C1** | 110°C - 140°C | 0.92 | 0.6x (Base) |
| **C2** | 110°C - 135°C | 0.95 | 0.8x |
| **C3** | 105°C - 135°C | 1.00 | 1.0x |
| **C4** | 90°C - 120°C | 1.06 | 1.3x |
| **C5** | 85°C - 115°C | 1.12 | 1.6x |

## 4. Integrazione con `italy_mapping.json`
Il `TyreModel` deve "leggere" la `circuit_section` attuale:
- **Se `type == "Straight"`**:
- Massimizza `Convection_Loss` (Raffreddamento).
- `Friction_Heat` minimo.
- **Se `type == "SlowCorner"`**:
- Massimizza `Friction_Heat` (Picco di temperatura superficiale).
- `Convection_Loss` ridotto (velocità minore).

## 5. Step di Implementazione per Windsurf
1. **Classe `TyreModel`**: Crea un metodo `update(delta_time, car_state, environment)`.
2. **Calcolo Grip**: `Effective_Grip = Base_Grip * Thermal_Factor(T_core) * Wear_Factor`.
3. **Thermal Factor**: Usa una curva gaussiana centrata sulla Window Ottimale: `gaussian(temp, window) = exp(-(temp - temp_opt)^2 / (2*sigma^2))` con sigma ≈ 6–8°C surface, 5–7°C core.
4. **Offline Data Hook**: Se non ci sono dati meteo dinamici (solo dev/test), usa `Air_Temp = 25.0` e `Track_Temp = 35.0`; in produzione le temperature arrivano da weather API/session state.

## 6. Reference Table per Mescola (per singola ruota)

| Compound | Surface Window (°C) | Core Window (°C) | Base Wear Rate (%/km) | Heat Capacity (kJ/°C) | Slip Sensitivity | Note |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **C1** | 110‑140 | 90‑115 | 0.09 | 1.25 | 0.75 | Hard, lenta a scaldarsi, degrado minimo |
| **C2** | 110‑135 | 88‑110 | 0.11 | 1.18 | 0.80 | Hard bilanciata |
| **C3** | 105‑135 | 85‑108 | 0.13 | 1.10 | 1.00 | Baseline (media) |
| **C4** | 90‑120 | 80‑100 | 0.16 | 0.98 | 1.15 | Soft, rapida a scaldarsi |
| **C5** | 85‑115 | 75‑95 | 0.19 | 0.90 | 1.30 | Ultra-soft, degrado elevato |
| **C6** | 80‑105 | 70‑90 | 0.22 | 0.82 | 1.45 | Hyper-soft (Imola/Monaco), soglia blistering bassa |

Le temperature vengono valutate per ruota; i fattori di usura sono percentuali di gomma consumata per chilometro prima di applicare gli scaler circuito/mescola.

### Heat/Cool factor per tipo di sezione

| Section kind | Heat factor | Cool factor |
| :-- | :-- | :-- |
| Straight | 0.2 | 1.2 |
| MediumStraight | 0.4 | 1.0 |
| SlowCorner | 1.4 | 0.4 |
| MediumCorner | 1.1 | 0.6 |
| FastCorner | 0.9 | 0.7 |

I valori vengono moltiplicati per `avg_speed`, durata della sezione e `downforce_importance` per calcolare l'energia che alimenta `ΔT_surface` e il consumo sezione.

## 7. Mapping dai Pirelli Hints

- `wear_rate_base` → scaler numerico: `Minimo/Basso = 0.8`, `Medio = 1.0`, `Medio-Alto = 1.15`, `Elevato/Critico = 1.35`.
- `lap_time_delta_hint` → penalità grip: il valore in secondi viene convertito in `grip_drop_per_wear = lap_time_delta_hint / stint_laps_attesi`.
- Le `notes` attivano flag: parole chiave "graining" aumentano la probabilità di graining quando le temperature sono sotto finestra; "abrasivo" incrementa `wear_rate`; "raffredda" riduce `heat_factor`.

## 8. TyreState (per ciascuna ruota)

```python
class TyreState(BaseModel):
    compound: str
    surface_temp: float
    core_temp: float
    wear_pct: float
    graining: bool
    blistering: bool

    def to_user_status(self) -> dict:
        return {
            "surface_temp": round(self.surface_temp, 1),
            "core_temp": round(self.core_temp, 1),
            "wear_pct": round(self.wear_pct, 1),
            "surface_window": window_label(self.surface_temp, compound_surface_window),
            "core_window": window_label(self.core_temp, compound_core_window),
            "graining": self.graining,
            "blistering": self.blistering,
        }
```

- Ogni vettura mantiene quattro TyreState (LF/LR/RF/RR) aggiornati per sezione.
- Il layer di presentazione mostra solo `surface_temp`, `core_temp`, `wear_pct` e i flag (più lo stato "IN/COLD/HOT" per ciascuna temperatura).
- Trigger ingegnerizzati: graining se `surface_temp` < finestra e `slip > soglia` per N secondi; blistering se `surface_temp` o `core_temp` > finestra alta per N secondi con `heat_factor` elevato.
