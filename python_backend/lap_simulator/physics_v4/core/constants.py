"""
Costanti fisiche F1 2025 per Physics Engine V4.

Tutte le costanti sono basate su:
- Regolamento FIA F1 2025
- Dati tecnici Pirelli
- Misure aerodinamiche reali
- Calibrazione su telemetria ufficiale

Queste costanti sono USATE DIRETTAMENTE nelle equazioni fisiche.
NON sono parametri empirici da aggiustare.
"""

# ============================================================================
# COSTANTI UNIVERSALI
# ============================================================================

G = 9.80665  # m/s² accelerazione gravitazionale (standard)
RHO_SEA_LEVEL = 1.225  # kg/m³ densità aria a livello mare (ISA)

# ============================================================================
# F1 2025 REGOLAMENTO - MASSE
# ============================================================================

MASS_DRY_KG = 798.0  # kg massa minima FIA (auto senza pilota e carburante)
MASS_DRIVER_KG = 80.0  # kg pilota (media F1)
MASS_BALLAST_KG = 0.0  # kg zavorra pilota (se necessaria per 80kg totali)

FUEL_RACE_START_KG = 110.0  # kg benzina inizio gara (max 110kg)
FUEL_QUALY_KG = 5.0  # kg benzina qualifica (minimo necessario)
FUEL_LAP_CONSUMPTION_KG = 2.5  # kg consumo medio per giro (Monza ~2.2, Monaco ~2.8)

# Massa totale qualifica
MASS_TOTAL_QUALY_KG = MASS_DRY_KG + MASS_DRIVER_KG + FUEL_QUALY_KG  # ~883 kg

# ============================================================================
# POWER UNIT F1 2025
# ============================================================================

# Motore termico (ICE)
ICE_PEAK_POWER_KW = 750.0  # kW (~1000 hp) a 12500 RPM
ICE_MAX_RPM = 12500  # RPM massimi regolamentari
ICE_IDLE_RPM = 5000  # RPM minimi

# ERS (Energy Recovery System)
ERS_PEAK_POWER_KW = 160.0  # kW MGU-K (regolamento 2025)
ERS_MAX_DEPLOY_PER_LAP_MJ = 4.0  # MJ energia massima deploy per giro
ERS_BATTERY_CAPACITY_MJ = 20.0  # MJ capacità batteria
ERS_BATTERY_MIN_SOC = 0.10  # 10% stato di carica minimo
ERS_BATTERY_MAX_SOC = 1.00  # 100% stato di carica massimo

# Power Unit totale
PU_TOTAL_PEAK_KW = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW  # 910 kW (~1220 hp)
DRIVETRAIN_EFFICIENCY = 0.895  # 89.5% efficienza trasmissione (10.5% perdite)

# ============================================================================
# RESISTENZE AL MOTO
# ============================================================================

ROLLING_RESISTANCE_COEFF = 0.011  # Crr pneumatici Pirelli F1 (1.1%)

# ============================================================================
# AERODINAMICA F1 2025
# ============================================================================

# Coefficienti di portanza (CLA = Lift Coefficient × Area)
CLA_MIN = 2.80  # m² assetto scarico (Monza, ala 4°)
CLA_NEUTRAL = 3.20  # m² assetto medio (Silverstone)
CLA_MAX = 4.80  # m² assetto carico (Monaco, ala 30°)

# Coefficienti di resistenza (CDA = Drag Coefficient × Area)
CDA_MIN = 0.85  # m² assetto scarico (Monza)
CDA_NEUTRAL = 1.10  # m² assetto medio
CDA_MAX = 1.60  # m² assetto carico (Monaco)

# DRS (Drag Reduction System)
DRS_DRAG_REDUCTION_FACTOR = 0.175  # 17.5% riduzione CDA con DRS aperto
DRS_ACTIVATION_SPEED_KPH = 100.0  # km/h velocità minima attivazione DRS

# Efficienza aerodinamica (Lift-to-Drag ratio)
AERO_EFFICIENCY_MIN = 3.5  # assetto molto carico
AERO_EFFICIENCY_MAX = 4.2  # assetto scarico efficiente

# ============================================================================
# GOMME PIRELLI F1 2025
# ============================================================================

# Coefficiente di attrito base per compound (a temperatura ottimale)
# Valori realistici per F1 2025 - grip meccanico puro (da test Pirelli + curb effect)
MU_BASE = {
    "C1": 1.65,  # Mescola dura (durata, meno grip)   [era 1.78]
    "C2": 1.74,  #                                     [era 1.84]
    "C3": 1.82,  # Mescola media (bilanciata)          [era 1.92]
    "C4": 1.95,  #                                     [era 2.00]
    "C5": 2.10,  # Mescola morbida (grip) - Qualifica  [INVARIATO, calibrato]
    "C6": 2.16,  # Nuova mescola 2025 (più morbida)    [INVARIATO]
    "INTERMEDIATE": 1.35,  # Pioggia leggera
    "WET": 1.05,  # Pioggia piena
}
# Spread C3→C5: +15.4% grip (era +9.4%). C5 invariato per non rompere calibrazione.

# Load sensitivity per pneumatici F1
# Formula: Grip = Mu * Fz * (1 - K * Fz)
# K è il coefficiente di decadimento lineare del grip
# A 300 km/h, il guadagno di grip dovrebbe essere ~20% in meno rispetto al calcolo teorico
# Calcolato: K ≈ 0.005 per F1 2025
TYRE_LOAD_SENSITIVITY_K = 0.005  # Coefficiente di decadimento lineare
TYRE_LOAD_REF_KN = 10.0  # kN carico di riferimento per grip base

# Efficienza grip in curva (traction circle)
# Il grip laterale disponibile è ~87% del grip longitudinale massimo
GRIP_CORNERING_EFFICIENCY = 0.87

# Degradazione grip con carico verticale (effetto Pacejka)
# Più carico = meno μ specifico (legge di rendimenti decrescenti)
KAPPA_LOAD = 0.15  # -15% μ per +100% carico verticale

# Temperature ottimali gomme (finestra di lavoro)
TYRE_TEMP_WINDOW_C = {
    "C1": (95, 115),  # Mescola dura: finestra alta
    "C2": (90, 110),
    "C3": (85, 105),  # Mescola media
    "C4": (80, 100),
    "C5": (75, 95),   # Mescola morbida: finestra bassa
    "C6": (70, 90),
    "INTERMEDIATE": (60, 80),
    "WET": (50, 70),
}

# Grip multiplier in base alla temperatura
# 1.0 = temperatura ottimale, <1.0 = troppo freddo/caldo
TYRE_GRIP_TEMP_MULTIPLIER = {
    "cold_40C": 0.65,      # 40°C: grip 65%
    "warm_70C": 0.85,      # 70°C: grip 85%
    "optimal_90C": 1.00,   # 90°C: grip 100%
    "hot_120C": 0.90,      # 120°C: grip 90%
    "overheated_140C": 0.70,  # 140°C: grip 70%
}

# ============================================================================
# GEOMETRIA AUTO F1 2025
# ============================================================================

H_CG = 0.285  # m altezza centro di gravità (da terra)
WHEELBASE = 3.600  # m passo tra assi (regolamento)
TRACK_WIDTH = 2.000  # m carreggiata (max 2000mm regolamento)

# Distribuzione massa anteriore (statica, senza trasferimento di carico)
WEIGHT_DIST_FRONT = 0.455  # 45.5% peso anteriore (regolamento 46% max)
WEIGHT_DIST_REAR = 1.0 - WEIGHT_DIST_FRONT  # 54.5% posteriore

# ============================================================================
# IMPIANTO FRENANTE
# ============================================================================

# Freni carbon-carbon
BRAKE_TEMP_OPTIMAL_MIN_C = 500.0  # °C inizio finestra ottimale
BRAKE_TEMP_OPTIMAL_MAX_C = 900.0  # °C fine finestra ottimale
BRAKE_TEMP_FADE_C = 1100.0  # °C inizio fade (ossidazione carbonio)
BRAKE_MU_PEAK = 0.52  # coefficiente attrito picco (carbon-carbon)

# Mappa attrito freni vs temperatura
BRAKE_MU_MAP = [
    (200, 0.15),   #troppo freddo: glazing, attrito quasi nullo
    (350, 0.32),   # sotto finestra: bassa efficienza
    (500, 0.48),   # ingresso finestra ottimale
    (700, 0.52),   # picco di attrito
    (900, 0.50),   # ancora ottimale
    (1100, 0.38),  # inizio fade
    (1300, 0.18),  # fade critico / ossidazione
]

# ============================================================================
# LIMITI ACCELERAZIONE
# ============================================================================

MAX_LATERAL_G = 5.5  # g laterali massimi (F1 moderne: 5-6g)
MAX_BRAKE_DECEL_G = 6.0  # g frenata massimi (F1 2025: 6.0g con nuovi freni)
BRAKE_DECEL_PEAK_G = 5.5  # g target per integrazione stabile

# ============================================================================
# SOSPENSIONI
# ============================================================================

# Antiroll bars (rigidità)
ARB_FRONT_MIN = 0.35  # minimo setting
ARB_FRONT_MAX = 0.85  # massimo setting
ARB_REAR_MIN = 0.35
ARB_REAR_MAX = 0.90

# Ride height (altezza da suolo)
RIDE_HEIGHT_FRONT_OPTIMAL_MM = 40.0  # mm ottimale anteriore
RIDE_HEIGHT_REAR_OPTIMAL_MM = 50.0  # mm ottimale posteriore
RIDE_HEIGHT_MIN_MM = 25.0  # mm minimo (plank wear limit)
RIDE_HEIGHT_MAX_MM = 70.0  # mm massimo

# Ground effect sensitivity
GROUND_EFFECT_SENSITIVITY = 0.010  # +1% CLA per mm sotto ottimale

# ============================================================================
# SETUP AERODINAMICO
# ============================================================================

# Ali anteriori e posteriori (gradi inclinazione)
FRONT_WING_MIN_DEG = 12.0  # gradi minimi
FRONT_WING_MAX_DEG = 28.0  # gradi massimi
REAR_WING_MIN_DEG = 10.0
REAR_WING_MAX_DEG = 32.0

# Mapping gradi → coefficienti aero
# Monza (FW 14°, RW 12°): CLA ~2.8, CDA ~0.85
# Monaco (FW 26°, RW 30°): CLA ~4.8, CDA ~1.6

# ============================================================================
# CIRCUITI DI RIFERIMENTO PER CALIBRAZIONE
# ============================================================================

CIRCUIT_TARGETS = {
    "it-1922_monza": {
        "lap_time_qualy_s": 79.5,  # s tempo qualifica target
        "v_max_kph": 365.0,  # km/h velocità massima
        "setup_type": "low_downforce",
    },
    "mc-1929_monaco": {
        "lap_time_qualy_s": 70.2,
        "v_max_kph": 290.0,
        "setup_type": "high_downforce",
    },
    "jp-1962_suzuka": {
        "lap_time_qualy_s": 88.5,
        "v_max_kph": 320.0,
        "setup_type": "balanced",
    },
}

# ============================================================================
# DEBUG E LOGGING
# ============================================================================

DEBUG_ENABLE = False  # Abilita log dettagliato
DEBUG_LOG_FILE = "logs/physics_v4_debug.log"

# ============================================================================
# VERSIONE E METADATI
# ============================================================================

PHYSICS_V4_VERSION = "4.0.0"
PHYSICS_V4_STATUS = "DEVELOPMENT"
PHYSICS_V4_DATE = "2026-04-04"
