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
- `Conduction`: `k_track * (T_surf - Track_Temp)`.

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
3. **Thermal Factor**: Usa una curva gaussiana centrata sulla Window Ottimale.
4. **Offline Data Hook**: Se non ci sono dati meteo dinamici, usa di default `Air_Temp = 25.0` e `Track_Temp = 35.0`.
