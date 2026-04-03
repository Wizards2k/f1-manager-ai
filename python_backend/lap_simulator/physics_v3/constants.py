"""
Physics Engine V3 — Costanti Fisiche F1 2025

Tutte le costanti sono calibrate dalla spec physics-engine-v3-spec.md Section 2.
Sorgenti: F1 2025 regolamento FIA, telemetria 2024/2025, dati pubblici GridStats.
"""

import math
from typing import Dict, List, Tuple

# ============================================================================
# Costanti Universali
# ============================================================================

G = 9.81                            # m/s² accelerazione gravitazionale
RHO_SEA_LEVEL = 1.225               # kg/m³ densità aria a livello mare

# ============================================================================
# F1 2025 Regolamento — Masse
# ============================================================================

MASS_DRY_KG = 798.0                 # kg massa minima FIA (monoscocca nuda)
FUEL_RACE_START_KG = 110.0          # kg benzina inizio gara
FUEL_QUALY_KG = 5.0                 # kg benzina qualifica (minimo per giro ritorno)
FUEL_DENSITY_KG_L = 0.775           # kg/L benzina Formula 1 (premium fuel)

# ============================================================================
# Power Unit — Potenza e Efficienza
# ============================================================================

ICE_PEAK_POWER_KW = 950.0           # kW motore termico picco (turbo a regime) — CALIB: +200kW calibration
ICE_BASE_POWER_KW = 950.0           # kW power unit a regime stabile
ERS_PEAK_POWER_KW = 220.0           # kW MGU-K 2025 (picco discharge) — CALIB: +60kW total deploy
PU_TOTAL_PEAK_KW = 1170.0           # kW ICE + ERS qualifying (1170 kW = 1558 hp)
DRIVETRAIN_EFFICIENCY = 0.895       # perdite meccaniche (trasmissione, differenziale, semiassi)
ROLLING_RESISTANCE_COEFF = 0.011    # Crr pneumatici Pirelli F1 (valido su asfalto)

# ============================================================================
# Aerodinamica — Range F1 2025
# ============================================================================

# Downforce coefficient area [m²] — calibrato da equilibrio v_max vs cornering
CLA_MIN = 2.80                      # Monza low-DF setup
CLA_MAX = 4.80                      # Monaco high-DF setup
CLA_NEUTRAL = 3.20                  # Setup medio

# Drag coefficient area [m²] — include telaio + aero
CDA_BASE_STRUCT = 0.0              # m² baseline telaio + ruote
CDA_MIN = 1.00                      # Monza low-DF setup
CDA_MAX = 1.40                      # Monaco high-DF setup
CDA_NEUTRAL = 1.20                  # Setup medio

# Sensitivity (aero_points → fisico) — da spec Section 3
CLA_SENSITIVITY = 0.020             # m²/punto aero  (baseline 160 pt = 3.2 m²)
CDA_SENSITIVITY = 0.0005            # m²/punto aero (realistic scaling factor)

# DRS (Drag Reduction System)
DRS_DRAG_REDUCTION_FACTOR = 0.175   # -17.5% CDA quando DRS aperto (rear flap opened)

# ============================================================================
# Grip Meccanico per Compound — Valori Base
# ============================================================================

MU_BASE = {
    "C1": 1.50,  # C1 duro
    "C2": 1.60,  # C2
    "C3": 1.70,  # C3 universale (baseline)
    "C4": 1.80,  # C4 soft
    "C5": 1.90,  # C5 morbido
    "C6": 2.00,  # C6 ultrasoft
    "INTERMEDIATE": 1.30,  # INT umido
    "WET": 0.95,  # WET bagnato
}

# Efficienza in curva — Traction circle (Kamm)
# Il grip laterale disponibile è ridotto per la ripartizione forza con frenate/accelerazioni
GRIP_CORNERING_EFFICIENCY = 0.87    # 87% di peak grip disponibile in curva pura

# Degradazione carico (Pacejka: più carico = meno μ specifico)
KAPPA_LOAD = 0.15                   # -15% mu per +100% carico (transfer load effect)

# ============================================================================
# Geometria Auto F1 2025
# ============================================================================

H_CG = 0.285                        # m altezza centro di gravità
WHEELBASE = 3.6                     # m tra gli assi (distanza asse ant - asse post)
TRACK_WIDTH = 2.0                   # m tra le ruote (circa, per load transfer)
WEIGHT_DIST_FRONT = 0.455           # 45.5% peso distribuito asse anteriore

# ============================================================================
# Sistema Frenante — Carbon-Carbon
# ============================================================================

# Mappa μ_brake in funzione temperatura (carbon-carbon discs)
BRAKE_MU_MAP: List[Tuple[float, float]] = [
    (200.0, 0.15),                  # troppo freddo: glazing, attrito quasi nullo
    (350.0, 0.32),                  # sotto finestra: bassa efficienza
    (500.0, 0.48),                  # ingresso finestra ottimale
    (700.0, 0.52),                  # picco di attrito
    (900.0, 0.50),                  # ancora ottimale
    (1100.0, 0.38),                 # inizio fade
    (1300.0, 0.18),                 # fade critico / ossidazione carbonio
]

BRAKE_TEMP_OPTIMAL_MIN_C = 500.0    # ingresso finestra termica ottimale
BRAKE_TEMP_OPTIMAL_MAX_C = 900.0    # fine finestra termica
BRAKE_TEMP_FADE_C = 1100.0          # inizio fade/ossidazione carbonio
BRAKE_MU_PEAK = 0.52                # coefficiente attrito picco (700°C)

# ============================================================================
# Limiti Dinamici Laterali e Longitudinali
# ============================================================================

MAX_LATERAL_G = 5.5                 # g laterali moderni F1 (peak cornering)
MAX_BRAKE_DECEL_G = 6.5             # g massimi in frenata (ABS limit)
BRAKE_DECEL_PEAK_G = 5.8            # g target per integrazione numerica stabile

# ============================================================================
# Modello Sospensioni
# ============================================================================

# Antiroll bar (ARB) ranges
ARB_FRONT_MIN = 0.35
ARB_FRONT_MAX = 0.85
ARB_REAR_MIN = 0.35
ARB_REAR_MAX = 0.90

# Ride height ranges [mm]
RIDE_HEIGHT_FRONT_MIN_MM = 30.0
RIDE_HEIGHT_FRONT_MAX_MM = 60.0
RIDE_HEIGHT_REAR_MIN_MM = 40.0
RIDE_HEIGHT_REAR_MAX_MM = 70.0

# Ground effect multiplier (ride height vs aero downforce)
GROUND_EFFECT_OPTIMAL_MM = 45.0     # altezza ottimale per massimo GE
GROUND_EFFECT_MAX_BONUS = 1.15      # 15% bonus DL massimo a altezza ottimale
GROUND_EFFECT_PENALTY_AT_HIGH = 0.85  # penalty se troppo alto

# ============================================================================
# Modello Gomme — Finestre Termiche (da tyre_model.py integration)
# ============================================================================

TYRE_TEMP_WINDOW_OPTIMAL_C = 115.0  # temperatura ottimale per effective_grip = 1.0
TYRE_TEMP_COLD_THRESHOLD_C = 80.0   # sotto, penalty aumenta rapidamente
TYRE_TEMP_HOT_THRESHOLD_C = 130.0   # sopra, penalty aumenta per surriscaldamento

# ============================================================================
# Integrazione Numerica — Stabilità
# ============================================================================

# 50Hz integration (dt = 0.02s) per sezioni con look-ahead
INTEGRATION_DT_HZ = 100             # frequenza integrazione cinematica — CALIB: 50 → 100 Hz (higher fidelity)
INTEGRATION_DT_S = 1.0 / INTEGRATION_DT_HZ

# V minima per sicurezza numerica (evita divisione per zero)
MIN_VELOCITY_MS = 0.1               # m/s

# Clamping su temperature (per sicurezza numerica)
TYRE_TEMP_MIN_C = 0.0
TYRE_TEMP_MAX_C = 1500.0
BRAKE_TEMP_MIN_C = 0.0
BRAKE_TEMP_MAX_C = 1500.0

# ============================================================================
# Configurazione ERS — Budget per Lap
# ============================================================================

ERS_BATTERY_CAPACITY_MJ = 4.0       # MJ capacità batteria (4 MJ per lap)
ERS_MGU_K_HARVEST_LIMIT_KW = 120.0  # kW max harvest (freno motore)
ERS_MGU_K_DEPLOY_LIMIT_KW = 160.0   # kW max discharge (power boost)
ERS_MGU_H_CONTRIBUTION_MJ = 0.5     # MJ raccolti da MGU-H per lap (circa)

# ============================================================================
# Coefficienti Aerodinamici Specifici
# ============================================================================

# Sensibilità ali a velocità (speed factor per downforce)
SPEED_FACTOR_MIN = 0.8              # 0.8 a bassa velocità
SPEED_FACTOR_MAX = 1.15             # 1.15 ad alta velocità (non lineare)
SPEED_FACTOR_REFERENCE_KPH = 200.0  # velocità di riferimento per normalizzazione

# ============================================================================
# Costanti di Validazione (da spec Section 11-16)
# ============================================================================

# Target lap times F1 2025 (qualifying, setup baseline)
TARGET_LAP_TIMES = {
    "it-1922_monza": 79.5,
    "mc-1929_monaco": 70.2,
    "jp-1962_suzuka": 87.3,
    "gb-1950_silverstone": 87.8,
    "be-1925_spa": 80.5,
    "au-1953_albert_park": 78.9,
    "us-2000_austin": 82.4,
    "br-1972_interlagos": 73.6,
    "ae-2009_yas_marina": 76.2,
    "sa-2023_jeddah": 73.8,
}

# ============================================================================
# Costanti Matematiche (per evitare import math ripetuto)
# ============================================================================

PI = math.pi
SQRT2 = math.sqrt(2)
SQRT3 = math.sqrt(3)

# ============================================================================
# Helper: Interpola una mappa temperature → coefficienti
# ============================================================================

def interpolate_brake_mu(temp_c: float) -> float:
    """
    Interpola mu_brake da BRAKE_MU_MAP in base a temperatura.
    Usa interpolazione lineare tra i punti della mappa.
    """
    if temp_c <= BRAKE_MU_MAP[0][0]:
        return BRAKE_MU_MAP[0][1]
    if temp_c >= BRAKE_MU_MAP[-1][0]:
        return BRAKE_MU_MAP[-1][1]

    for i in range(len(BRAKE_MU_MAP) - 1):
        t1, mu1 = BRAKE_MU_MAP[i]
        t2, mu2 = BRAKE_MU_MAP[i + 1]

        if t1 <= temp_c <= t2:
            # Interpolazione lineare
            frac = (temp_c - t1) / (t2 - t1)
            return mu1 + frac * (mu2 - mu1)

    return BRAKE_MU_MAP[-1][1]


# ============================================================================
# Helper: Densità aria in funzione di temperatura e altitudine
# ============================================================================

def compute_air_density(temp_c: float, altitude_m: float = 0.0) -> float:
    """
    Calcola densità aria (kg/m³) da temperatura e altitudine.
    Usa equazione barometrica semplificata.

    Args:
        temp_c: temperatura in Celsius
        altitude_m: altitudine in metri (default 0 = livello mare)

    Returns:
        Densità aria in kg/m³
    """
    temp_k = temp_c + 273.15

    # Pressione atmosferica (hectopascal) su altitudine
    pressure_pa = 101325 * (1 - altitude_m / 44330.0) ** 5.255

    # Legge dei gas ideali: ρ = P / (R * T)
    R_specific = 287.0  # J/(kg·K) costante specifica aria secca

    density = pressure_pa / (R_specific * temp_k)

    return max(density, 0.5)  # clamp minimo per sicurezza


# ============================================================================
# Test: Verifica costanti
# ============================================================================

if __name__ == "__main__":
    print(f"Physics Engine V3 Constants — Validation")
    print(f"G = {G} m/s²")
    print(f"MASS_DRY = {MASS_DRY_KG} kg")
    print(f"CLA_NEUTRAL = {CLA_NEUTRAL} m²")
    print(f"CDA_NEUTRAL = {CDA_NEUTRAL} m²")
    print(f"MAX_LATERAL_G = {MAX_LATERAL_G} g")
    print(f"BRAKE_MU_PEAK = {BRAKE_MU_PEAK}")

    # Test interpolazione
    mu_cold = interpolate_brake_mu(200)
    mu_optimal = interpolate_brake_mu(700)
    mu_fade = interpolate_brake_mu(1100)
    print(f"\nBrake µ: cold={mu_cold:.2f}, optimal={mu_optimal:.2f}, fade={mu_fade:.2f}")

    # Test densità aria
    rho_sl = compute_air_density(15.0, 0.0)
    rho_hot = compute_air_density(35.0, 0.0)
    rho_mc = compute_air_density(20.0, 100.0)  # Monaco altitudine ~100m
    print(f"Air density: SL 15°C={rho_sl:.4f}, SL 35°C={rho_hot:.4f}, Monaco={rho_mc:.4f}")
