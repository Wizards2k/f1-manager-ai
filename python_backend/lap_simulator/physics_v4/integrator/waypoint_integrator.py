"""
Waypoint Integrator - Integrazione fisica su HD waypoints.

Questo è il cuore del Physics Engine V4.
Per ogni waypoint (5m passo), risolve le equazioni del moto:

  F = m × a
  v_new = v_old + a × dt
  pos_new = pos_old + v × dt

Le forze considerate sono:
- F_engine: potenza motore (ICE + ERS)
- F_drag: resistenza aerodinamica
- F_downforce: carico verticale (grip)
- F_gravity: pendenza/salita
- F_centripetal: forza in curva

Il tempo sul giro EMERGE dall'integrazione, non è un riferimento.
"""

import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import diretti dalle costanti
import sys
from pathlib import Path

# Aggiungi parent al path per import
current_dir = Path(__file__).parent.parent
sys.path.insert(0, str(current_dir))

from core.constants import (
    G,
    RHO_SEA_LEVEL,
    MASS_TOTAL_QUALY_KG,
    DRIVETRAIN_EFFICIENCY,
    PU_TOTAL_PEAK_KW,
    ICE_PEAK_POWER_KW,
    ERS_PEAK_POWER_KW,
    ICE_IDLE_RPM,
    ICE_MAX_RPM,
    ROLLING_RESISTANCE_COEFF,
    MAX_LATERAL_G,
    MAX_BRAKE_DECEL_G,
    MU_BASE,
    TYRE_LOAD_SENSITIVITY_K,
    TYRE_LOAD_REF_KN,
)

from aero.aero_assembly import AeroAssembly, AeroForces
from calibration.aero_calibration import get_aero_calibration
from calibration.circuit_calibration import get_circuit_calibration
from calibration.pu_lookup import load_pu_lookup, PULookupInterpolator
from calibration.telemetry_bridge import TelemetryBridge
from integrator.pu_stateful_v2 import (
    PU_Context,
    init_pu_context,
    compute_f_engine_v54,
    get_optimal_gear,
    get_gear_ratio_from_n_gear,
    update_thermal_state,
    compute_thermal_eta,
    R_WHEEL,
    FINAL_DRIVE,
    DRIVETRAIN_EFFICIENCY as PU_DRIVETRAIN_EFFICIENCY,
    GEAR_RATIOS,
    BATTERY_CAPACITY_MJ,
)


@dataclass
class PhysicsState:
    """Stato fisico dell'auto durante l'integrazione."""
    
    # Cinematica
    distance_m: float = 0.0  # distanza percorsa [m]
    velocity_ms: float = 0.0  # velocità [m/s]
    acceleration_ms2: float = 0.0  # accelerazione [m/s²]
    time_s: float = 0.0  # tempo trascorso [s]
    
    # Forze
    f_engine: float = 0.0  # N forza motrice
    f_drag: float = 0.0  # N forza drag
    f_downforce: float = 0.0  # N forza downforce
    f_gravity: float = 0.0  # N forza gravità (pendenza)
    f_centripetal: float = 0.0  # N forza centripeta
    
    # Stati
    is_braking: bool = False
    is_throttle: bool = False
    is_drs_active: bool = False

    # V5.5: Brake state commitment (anti-chatter hysteresis)
    # Quando il lookahead decide di frenare, salva la velocità target.
    # La frenata resta attiva finché velocity_ms <= brake_target_v_ms + EPS,
    # ignorando le decisioni per-step. Eliminato il chatter brake/throttle
    # vicino alla velocità target (Monaco: 174 → ~12 transizioni).
    brake_target_v_ms: Optional[float] = None

    # Telemetria
    telemetry_points: List[Dict] = None
    
    def __post_init__(self):
        if self.telemetry_points is None:
            self.telemetry_points = []


def load_hd_waypoints(circuit_id: str) -> List[Dict]:
    """
    Carica waypoints HD per un circuito.
    
    I file sono in: python_backend/data/circuits/2025/{circuit_id}_HD.json
    
    Returns:
      Lista di waypoints con: dist_m, v_ref_kph, radius_m, slope_deg, etc.
    
    FIX V5.1: Deduplicate boundary waypoints. The HD data contains duplicate
    entries at section boundaries (same dist_m, different macro_sector_id).
    The boundary waypoint from the incoming section often carries the apex
    minimum radius (e.g. 40.6m) instead of the actual radius at that track
    position (e.g. ~1260m at corner entry). This causes catastrophic speed
    drops when the integrator uses the apex radius at a point where the car
    is still on the straight. We keep the waypoint with the LARGER radius,
    which corresponds to the outgoing/entry side of the boundary.
    """
    from pathlib import Path
    import json
    
    # Resolve circuits directory relative to this file (cross-platform)
    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    hd_file = circuits_dir / f"{circuit_id}_HD.json"
    
    if not hd_file.exists():
        raise FileNotFoundError(f"HD file non trovato: {hd_file}")
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw_waypoints = data.get("waypoints", [])
    
    # FIX V5.2-offset: Handle duplicate waypoints at section boundaries.
    # At section boundaries, two waypoints exist at the same dist_m:
    #   - One from the outgoing section (e.g. large radius at corner exit)
    #   - One from the incoming section (e.g. small radius at corner entry)
    #
    # The incoming section's first point carries the APEX minimum radius
    # of that section (e.g. 45m for Monaco hairpin), NOT the actual radius
    # at the boundary point. The actual radius at the boundary is the
    # outgoing section's last point (e.g. 3842m at corner entry).
    #
    # V5.2-offset: Keep BOTH waypoints with a tiny distance offset (0.01m).
    # This preserves the full track profile including apex radii.
    # The integrator handles the boundary speed transition via a per-step
    # deceleration limit (see V5.4.3 in integrate_waypoint).
    if len(raw_waypoints) > 1:
        deduped = [raw_waypoints[0]]
        for wp in raw_waypoints[1:]:
            prev_dist = deduped[-1].get('dist_m', -999)
            wp_dist = wp.get('dist_m', -998)
            if abs(wp_dist - prev_dist) < 0.01:
                # Duplicate distance: keep BOTH waypoints with tiny offset
                wp_copy = dict(wp)
                wp_copy['dist_m'] = prev_dist + 0.01  # Tiny offset
                deduped.append(wp_copy)
            else:
                deduped.append(wp)
        raw_waypoints = deduped
    
    return raw_waypoints


def _load_reference_sections(circuit_id: str) -> Dict[str, Dict[str, Any]]:
    """Carica le sezioni di riferimento della telemetria per il circuito."""
    from pathlib import Path
    import json

    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    telemetry_file = circuits_dir / f"{circuit_id}_Telemetry.json"

    if not telemetry_file.exists():
        return {}

    with open(telemetry_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = (((data or {}).get("geometry") or {}).get("sections") or [])
    return {
        str(section.get("id")): section
        for section in sections
        if section.get("id")
    }


def _find_section_id_by_distance(reference_sections: Dict[str, Dict[str, Any]], distance_m: float) -> str:
    """Trova la sezione telemetria che contiene una data distanza.

    Usa i confini start_m/end_m dalla telemetria invece di fidarsi dei
    macro_sector_id dei waypoint HD, che possono essere disallineati
    (es. Silverstone: HD sec_02 a 340m vs Tel sec_02 a 785m).
    """
    for sid, section in reference_sections.items():
        start = section.get('start_m', 0.0)
        end = section.get('end_m', 0.0)
        if start <= distance_m < end:
            return sid
    return ''


def _load_soft_compound(circuit_id: str) -> str:
    """Carica la mescola SOFT dal file Telemetry del circuito.
    
    La telemetria di qualifica usa sempre la gomma SOFT, che varia per circuito
    (es. C3 a Sakhir, C4 a Spa, C5 a Monza, C6 a Monaco).
    Questo è il compound di riferimento per la calibrazione mu_mechanical.
    
    Returns:
      Compound ID (es. "C5") oppure "C3" come fallback.
    """
    from pathlib import Path
    import json
    
    circuits_dir = Path(__file__).resolve().parents[3] / "data" / "circuits" / "2025"
    telemetry_file = circuits_dir / f"{circuit_id}_Telemetry.json"
    
    if not telemetry_file.exists():
        return "C3"  # Fallback
    
    try:
        with open(telemetry_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Percorso 1: tyres.pirelli_package.nomination.soft (la maggior parte dei circuiti)
        nomination = (((data or {}).get("tyres") or {}).get("pirelli_package") or {}).get("nomination") or {}
        soft = nomination.get("soft")
        if soft:
            return soft
        
        # Percorso 2: tyre_allocation.dry_compounds.soft (es. Silverstone)
        dry_compounds = (((data or {}).get("tyre_allocation") or {}).get("dry_compounds") or {})
        soft = dry_compounds.get("soft")
        if soft:
            return soft
        
        return "C3"  # Fallback
    except (json.JSONDecodeError, KeyError, TypeError):
        return "C3"  # Fallback


def _apply_aero_calibration(aero_forces: AeroForces, aero_calibration: Optional[Dict[str, Any]]) -> AeroForces:
    """Applica un profilo aero calibrato ai coefficienti calcolati dal modello fisico.
    
    V5.0: Supporta sia il formato legacy (drag_index, downforce_index, aero_balance_target)
    sia il formato V5 (mu_mechanical, k_wing_coupling, mu_by_speed).
    I parametri mu_mechanical e k_wing_coupling NON sono applicati qui:
    - mu_mechanical è applicato nel grip calculation (integrate_waypoint)
    - k_wing_coupling è applicato nell'AeroAssembly (set_k_wing_coupling)
    """
    if not aero_calibration:
        return aero_forces

    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # V5.0: Nel nuovo formato, drag_index e downforce_index potrebbero non esserci
    # In tal caso, non applicare scaling aero (usa il modello fisico puro)
    drag_scale = _as_float(aero_calibration.get("drag_index"), 1.0) or 1.0
    downforce_scale = _as_float(aero_calibration.get("downforce_index"), 1.0) or 1.0
    balance_target = aero_calibration.get("aero_balance_target")

    # Se il formato è V5 e non ha drag_index/downforce_index, salta lo scaling aero
    if aero_calibration.get("format") == "v5" and "drag_index" not in aero_calibration:
        # V5: Il modello fisico è già calibrato, non serve scaling
        return aero_forces

    front_share = aero_forces.aero_balance
    if balance_target is not None:
        front_share = max(0.35, min(0.65, 0.5 + _as_float(balance_target, 0.0)))

    total_cla = aero_forces.cla_total * downforce_scale
    total_cda = aero_forces.cda_total * drag_scale
    total_downforce = aero_forces.f_downforce * downforce_scale
    total_drag = aero_forces.f_drag * drag_scale

    aero_forces.cla_total = total_cla
    aero_forces.cda_total = total_cda
    aero_forces.cla_front = total_cla * front_share
    aero_forces.cla_rear = total_cla * (1.0 - front_share)
    aero_forces.f_downforce = total_downforce
    aero_forces.f_downforce_front = total_downforce * front_share
    aero_forces.f_downforce_rear = total_downforce * (1.0 - front_share)
    aero_forces.f_drag = total_drag
    aero_forces.aero_balance = front_share

    return aero_forces


def _compute_suspension_effects(suspension_setup: Optional[Dict]) -> Dict[str, float]:
    """
    Calcola effetti sospensioni sulla performance usando valori fisici reali.

    P5 FIX: Usa valori reali (N/mm, Nm/deg) invece di slider.
    La conversione slider→reale avviene qui tramite slider_to_real().
    
    Le sospensioni influenzano:
    1. Grip meccanico (contatto gomma-asfalto) - da spring rate
    2. Load transfer laterale (rollio in curva) - da ARB
    3. Stabilità in frenata - da bilanciamento molle ant/post
    4. Effetto ride height su downforce - da altezza da suolo

    Args:
        suspension_setup: dict con valori slider (spring_front 1-50, arb_front 1-30,
                         ride_height_front 1-30) + valori reali convertiti
                         (spring_front_Nmm, arb_front_Nmdeg, ride_height_front_mm)

    Returns:
        Dict con fattori moltiplicativi per grip/stabilità
    """
    if not suspension_setup:
        return {
            'mechanical_grip_factor': 1.0,
            'corner_grip_penalty': 0.0,
            'braking_stability_factor': 1.0,
            'ride_height_aero_factor': 1.0,
            'ride_height_front_m': 0.040,  # default 40mm
            'ride_height_rear_m': 0.050,   # default 50mm
        }

    # ── Valori reali F1 (da slider_to_real) ──────────────────────────────
    # Se i valori reali sono già nel dict (da get_setup_dict), usali.
    # Altrimenti converti da slider (backward compatibility con range 1-50/1-30).
    # Nuovo range: spring 1-50, ARB 1-30, RH 1-30
    spring_front_Nmm = float(suspension_setup.get('spring_front_Nmm',
        suspension_setup.get('spring_front', 25.0) * 12.0 + 100.0))
    spring_rear_Nmm = float(suspension_setup.get('spring_rear_Nmm',
        suspension_setup.get('spring_rear', 33.0) * 14.0 + 100.0))
    arb_front_Nmdeg = float(suspension_setup.get('arb_front_Nmdeg',
        suspension_setup.get('arb_front', 11.0) * 15.0 + 35.0))
    arb_rear_Nmdeg = float(suspension_setup.get('arb_rear_Nmdeg',
        suspension_setup.get('arb_rear', 18.0) * 15.0 + 35.0))
    ride_height_front_mm = float(suspension_setup.get('ride_height_front_mm',
        suspension_setup.get('ride_height_front', 7.0) * 1.0 + 19.0))
    ride_height_rear_mm = float(suspension_setup.get('ride_height_rear_mm',
        suspension_setup.get('ride_height_rear', 14.0) * 1.2 + 28.8))

    # ── Valori ottimali F1 ───────────────────────────────────────────────
    # Spring: ~400 N/mm front, ~562 N/mm rear (slider 25/33)
    SPRING_FRONT_OPT_NMM = 400.0   # N/mm
    SPRING_REAR_OPT_NMM = 562.0    # N/mm
    # ARB: ~200 Nm/deg front, ~305 Nm/deg rear (slider 11/18)
    ARB_FRONT_OPT_NMDEG = 200.0    # Nm/deg
    ARB_REAR_OPT_NMDEG = 305.0     # Nm/deg
    # Ride height: ~26 mm front, ~46 mm rear (slider 7/14)
    RH_FRONT_OPT_MM = 26.0         # mm
    RH_REAR_OPT_MM = 45.6          # mm

    # ── Spring rate → grip meccanico ─────────────────────────────────────
    # Deviazione normalizzata rispetto all'ottimale F1.
    # Range: 120-700 N/mm front, 173-840 N/mm rear.
    # Troppo morbido → rollio, imprecisione. Troppo rigido → rimbalzo, perdita contatto.
    spring_dev_f = abs(spring_front_Nmm - SPRING_FRONT_OPT_NMM) / SPRING_FRONT_OPT_NMM
    spring_dev_r = abs(spring_rear_Nmm - SPRING_REAR_OPT_NMM) / SPRING_REAR_OPT_NMM
    spring_dev_avg = (spring_dev_f + spring_dev_r) / 2.0

    # Penalità progressiva: fino a ~7% grip loss agli estremi
    mechanical_grip_factor = 1.0 - 0.07 * (spring_dev_avg ** 1.5)
    mechanical_grip_factor = max(0.93, min(1.0, mechanical_grip_factor))

    # ── ARB → load transfer in curva ─────────────────────────────────────
    # Deviazione normalizzata rispetto all'ottimale F1.
    # Range: 50-500 Nm/deg.
    # Troppo rigido → eccesso load transfer → meno grip ruota interna
    # Troppo morbido → troppo rollio → meno reattività (penalità minore)
    arb_dev_f = abs(arb_front_Nmdeg - ARB_FRONT_OPT_NMDEG) / ARB_FRONT_OPT_NMDEG
    arb_dev_r = abs(arb_rear_Nmdeg - ARB_REAR_OPT_NMDEG) / ARB_REAR_OPT_NMDEG

    # Asimmetria: troppo rigido penalizza di più
    if arb_front_Nmdeg > ARB_FRONT_OPT_NMDEG:
        arb_dev_f *= 1.3
    if arb_rear_Nmdeg > ARB_REAR_OPT_NMDEG:
        arb_dev_r *= 1.3

    arb_dev_avg = (arb_dev_f + arb_dev_r) / 2.0
    # Fino a ~8% penalità laterale agli estremi
    corner_grip_penalty = 0.08 * (arb_dev_avg ** 1.3)
    corner_grip_penalty = min(0.10, corner_grip_penalty)

    # ── Bilanciamento molle → stabilità frenata ──────────────────────────
    # Se le molle sono sbilanciate (es. molto rigido davanti, morbido dietro)
    # la frenata diventa instabile (bloccaggio ruote)
    ratio_front = spring_front_Nmm / SPRING_FRONT_OPT_NMM
    ratio_rear = spring_rear_Nmm / SPRING_REAR_OPT_NMM
    spring_imbalance = abs(ratio_front - ratio_rear)
    braking_stability_factor = 1.0 - 0.05 * min(1.0, spring_imbalance)
    braking_stability_factor = max(0.95, min(1.0, braking_stability_factor))

    # ── Ride height → effetto aero ───────────────────────────────────────
    # P6: Ride height influenza la downforce del fondo.
    # Ottimale: ~26mm front, ~46mm rear (più basso = più ground effect).
    # Penalità per altezza eccessiva (troppo alto = meno downforce dal fondo).
    # Range: 20-47mm front, 30-66mm rear.
    # Il fattore è moltiplicativo sulla downforce del fondo (già calcolata in aero).
    rh_front_dev = (ride_height_front_mm - RH_FRONT_OPT_MM) / RH_FRONT_OPT_MM
    rh_rear_dev = (ride_height_rear_mm - RH_REAR_OPT_MM) / RH_REAR_OPT_MM
    # Ogni mm sopra l'ottimale riduce la downforce del fondo di ~1.5%
    # (ground effect è sensibile all'altezza: più basso = più suction)
    rh_aero_penalty = 0.015 * max(0.0, rh_front_dev) + 0.015 * max(0.0, rh_rear_dev)
    ride_height_aero_factor = max(0.90, 1.0 - rh_aero_penalty)

    return {
        'mechanical_grip_factor': mechanical_grip_factor,
        'corner_grip_penalty': corner_grip_penalty,
        'braking_stability_factor': braking_stability_factor,
        'ride_height_aero_factor': ride_height_aero_factor,
        # P6: Ride height in metri per compute_forces()
        'ride_height_front_m': ride_height_front_mm / 1000.0,
        'ride_height_rear_m': ride_height_rear_mm / 1000.0,
    }


def compute_grip_limit(
    velocity_ms: float,
    radius_m: float,
    mass_kg: float,
    cla: float,
    mu: float
) -> float:
    """
    Calcola velocità massima in curva dal grip disponibile.
    
    Formula fisica:
      F_centripeta = F_grip
      m × v² / R = μ × (m × g + F_downforce)
      
      v_max = sqrt( μ × (m × g + 0.5 × ρ × v² × CLA) × R / m )
    
    Questa è un'equazione implicita in v. Risolviamo iterativamente.
    
    Returns:
      v_max_ms: velocità massima in curva [m/s]
    """
    
    # Stima iniziale (senza downforce)
    v_max = math.sqrt(mu * G * radius_m)
    
    # Iterazioni per includere downforce (converge in 2-3 passi)
    for _ in range(3):
        # Calcola downforce a questa velocità
        dynamic_pressure = 0.5 * RHO_SEA_LEVEL * v_max ** 2
        f_down = dynamic_pressure * cla
        
        # Grip totale
        f_grip = mu * (mass_kg * G + f_down)
        
        # Nuova velocità massima
        v_max_new = math.sqrt(f_grip * radius_m / mass_kg)
        
        # Media ponderata per stabilità
        v_max = 0.7 * v_max_new + 0.3 * v_max
    
    return v_max


# ============================================================
# V6.0 PURO: FUNZIONI PER PHYSICS-DRIVEN CORNER MODEL
# ============================================================

def compute_v_max_corners(
    waypoints: List[Dict],
    aero,  # AeroAssembly
    mu_cal: float,
    mass_kg: float,
    suspension_effects: Optional[Dict[str, float]] = None,
    n_iter: int = 3,
) -> List[float]:
    """
    Calcola v_max_corner (velocità massima fisica) per ogni waypoint.

    Usa iterazione convergente per il downforce:
    v_max dipende dal downforce, che dipende da v².

    Formula:
    v_max = sqrt(f_grip * cu * radius / mass)
    dove:
    - f_grip = mu_mechanical * F_vert * load_factor
    - cu = min(0.95, 0.35 + radius / 150)
    - downforce è stimato iterativamente

    Returns: List[float] - v_max in m/s per ogni waypoint
    """
    v_max_corner = []

    for wp in waypoints:
        radius_m = wp.get('radius_m', 999999.0)
        is_corner = radius_m < 400.0

        if not is_corner:
            v_max_corner.append(999.0)  # Rettilineo: nessun limite
            continue

        # Stima iniziale: usa v_ref per calcolare downforce
        v_ref_kph = float(wp.get('v_ref_kph', 200.0))
        v_est = v_ref_kph / 3.6

        # Iterazione convergente: 3 volte
        for iteration in range(n_iter):
            # Calcola downforce a velocità stimata
            aero_forces = aero.compute_forces(
                speed_ms=v_est,
                air_density=RHO_SEA_LEVEL
            )
            f_downforce = aero_forces.f_downforce

            # Carico verticale totale
            f_vertical = mass_kg * G + f_downforce

            # Load sensitivity factor (laterale)
            f_vertical_kn = f_vertical / 1000.0
            lat_load_factor = 1.0 - (TYRE_LOAD_SENSITIVITY_K * f_vertical_kn)
            lat_load_factor = max(0.75, min(1.0, lat_load_factor))

            # Grip laterale totale
            f_grip = mu_cal * f_vertical * lat_load_factor

            # Cornering utilization
            cu = min(0.95, 0.35 + radius_m / 150.0)

            # Aggiorna stima v_max
            v_est = math.sqrt(max(0.1, f_grip * cu * radius_m / mass_kg))

        v_max_corner.append(v_est)

    return v_max_corner


def analyze_circuit_profile(waypoints: List[Dict]) -> str:
    """
    Classifica il circuito in base al profilo dei raggi di curvatura.

    Determina il tipo di circuito per applicare il safety factor appropriato:
    - TIGHT: Monaco, Budapest (> 40% curve con r < 100m)
    - MIXED: Suzuka, Barcelona (avg_r < 120m, ma non troppo tight)
    - FAST: Silverstone, Monza, Spa (< 15% tight, avg_r > 150m)
    - BALANCED: resto dei circuiti
    - STRAIGHT: circuiti senza curve significative

    Returns: tipo di circuito (str)
    """
    radii = [wp.get('radius_m', 999999.0) for wp in waypoints]
    corners = [r for r in radii if r < 400.0]

    if not corners:
        return "STRAIGHT"

    avg_radius = sum(corners) / len(corners)
    tight_count = sum(1 for r in corners if r < 100.0)
    tight_pct = (tight_count / len(corners)) * 100.0 if corners else 0.0

    # Classificazione
    if tight_pct > 40:
        return "TIGHT"  # Monaco, Budapest
    elif avg_radius < 120:
        return "MIXED"  # Suzuka, Barcelona, Imola
    elif tight_pct < 15 and avg_radius > 150:
        return "FAST"  # Silverstone, Monza, Spa, Austin
    else:
        return "BALANCED"


def get_safety_factor_v6(circuit_type: str, circuit_id: str) -> float:
    """
    Determina il safety factor per v_max_corner in base al tipo di circuito.

    Physics-based speeds sono ottimistiche vs real driver behavior.
    Safety factor = quanto conservativi essere sulla physics v_max.

    - TIGHT (0.85): physics leggermente ottimista
    - MIXED (0.88): middle ground
    - BALANCED (0.88): default
    - FAST (0.78): physics molto ottimista, serve constraint più aggressivo
    - STRAIGHT (0.92): quasi nessun constraint

    v_limit = v_max_corner * safety_factor
    """
    defaults = {
        "TIGHT": 0.85,
        "MIXED": 0.88,
        "BALANCED": 0.88,
        "FAST": 0.78,
        "STRAIGHT": 0.92,
    }

    # Override per-circuito (empirico da testing)
    # V6.0 Phase 2: Aggiustamento per circuiti veloci (Silverstone, Monza, Spa)
    # Safety factor deve essere molto basso perché questi circuiti hanno pochi corner
    # e v_max_corner physico è molto ottimistico per le curve veloci.
    overrides = {
        "mc-1929_monaco": 0.82,
        "gb-1948_silverstone": 0.60,  # Molto conservativo
        "it-1922_monza": 0.60,         # Molto conservativo
        "be-1925_spa_francorchamps": 0.60,  # Molto conservativo
        "jp-1962_suzuka": 0.85,
        "es-1991_barcelona": 0.87,
    }

    if circuit_id in overrides:
        return overrides[circuit_id]

    return defaults.get(circuit_type, 0.88)


def compute_braking_zones_v6(
    waypoints: List[Dict],
    v_max_corner: List[float],
    max_brake_decel_g: float,
) -> List[bool]:
    """
    V6.0 LOOKAHEAD: Identifica zone di frenata usando v_max_corner fisico.

    Questo è il vero lookahead di V6.0:
    - Cerca il prossimo corner che richiede frenata
    - Usa v_max_corner (physics) per decidere, non v_ref (telemetria)
    - Ritorna array brake_needed[i] = True se al waypoint i serve frenare

    Logica:
    - Per ogni waypoint, lookahead i prossimi 150m-4sec
    - Se per qualche corner futuro: a_needed > a_max_brake → frena ORA
    - Dove a_needed = (v_current² - v_target²) / (2*dist)

    Returns: List[bool] - True dove serve frenare
    """
    brake_needed = [False] * len(waypoints)
    a_max = max_brake_decel_g * G  # ~30 m/s² tipico

    for i in range(len(waypoints) - 1):
        v_current = v_max_corner[i]

        # Lookahead dinamico: almeno 150m, fino a ~4 secondi
        lookahead_max = max(150.0, v_current * 4.0)
        base_dist = waypoints[i].get('dist_m', 0.0)

        must_brake_now = False

        for j in range(i + 1, len(waypoints)):
            wp_dist = waypoints[j].get('dist_m', 0.0)
            dist_to_wp = wp_dist - base_dist

            # Esce dal range di lookahead
            if dist_to_wp > lookahead_max:
                break

            v_target = v_max_corner[j]

            # Evita divisione per zero
            if dist_to_wp < 1.0:
                continue

            # Calcola accelerazione necessaria per raggiungere v_target
            # v_target² = v_current² - 2*a*d
            # a = (v_current² - v_target²) / (2*d)
            a_needed = (v_current**2 - v_target**2) / (2.0 * dist_to_wp)

            # Margine empirico: 1.20 per V6.0 (più aggressivo senza brake commitment)
            # V5.5 aveva 1.30 ma con brake commitment; V6.0 senza commitment serve 1.20
            a_needed_with_margin = a_needed * 1.20

            # Se la decelerazione richiesta supera il max, serve frenare ORA
            if a_needed_with_margin > a_max:
                must_brake_now = True
                break

        brake_needed[i] = must_brake_now

    return brake_needed


def integrate_waypoint(
    state: PhysicsState,
    waypoint: Dict,
    next_waypoint: Dict,
    aero: AeroAssembly,
    setup: Dict,
    mass_kg: float,
    tyre_compound: str = "C3",
    driver_skill: float = 1.0,
    mu_base: Optional[Dict[str, float]] = None,
    max_brake_decel_g: Optional[float] = None,
    max_lateral_g: Optional[float] = None,
    aero_calibration: Optional[Dict[str, Any]] = None,
    section_guidance: Optional[Dict[str, Any]] = None,
    section_exit_guidance: Optional[Dict[str, Any]] = None,
    section_speed_scale: float = 1.0,
    section_entry_guidance: Optional[Dict[str, Any]] = None,
    waypoints: List[Dict] = None,  # Lista completa waypoints per look-ahead
    waypoint_idx: int = 0,         # Indice del waypoint corrente
    suspension_effects: Optional[Dict[str, float]] = None,  # Effetti sospensioni pre-calcolati
    ers_power_fraction: float = 1.0,  # Frazione ERS disponibile (0.0=solo ICE, 1.0=full ERS)
    reference_pull: Optional[Dict] = None,  # V5.0: Reference Pull data
    reference_pull_strength: float = 0.0,  # V5.0: Reference Pull strength (0.0-0.05 tipico)
    pu_lookup_interpolator: Optional[PULookupInterpolator] = None,  # V5.0: PU Lookup interpolator (legacy, unused)
    pu_lookup_blend: float = 0.0,  # V5.0: RPM blend from Reference Pull (0.0=constant power, 1.0=RPM from ref pull)
    pu_config: Optional[Dict] = None,  # V5.4: PU stateful config (None=V5.3 legacy)
    pu_ctx: Optional[PU_Context] = None,  # V5.4: PU state (passed between waypoints)
    # V6.0: Physics-driven corner model
    v_max_corner_array: Optional[List[float]] = None,  # Pre-computed v_max per waypoint
    brake_needed: Optional[List[bool]] = None,  # Pre-computed braking zones
) -> PhysicsState:
    """
    Integra fisica per un singolo waypoint.
    
    Modello fisico rivisto:
    - Braking point dinamico basato su delta-V e distanza
    - Trazione limitata per wheel spin in uscita curva
    - Potenza motore dipende da marcia/RPM (semplificato)
    - Grip dinamico basato su downforce (v²) e load transfer
    - Frenata progressiva con degressioni realistiche
    
    Args:
      state: stato fisico corrente
      waypoint: waypoint corrente
      next_waypoint: waypoint successivo
      aero: assembler aerodinamico
      setup: configurazione ali/sospensioni
      mass_kg: massa totale auto
      tyre_compound: mescola gomme
      driver_skill: fattore pilota (0.9-1.1)
      mu_base: dizionario grip gomme (override)
      max_brake_decel_g: frenata massima (override)
      max_lateral_g: accelerazione laterale max (override)
      aero_calibration: profilo aero calibrato (drag/downforce/balance)
      pu_config: V5.4 PU stateful config (None=V5.3 legacy mode)
      pu_ctx: V5.4 PU state (transported between waypoints)
    
    Returns:
      Nuovo stato fisico aggiornato
    """
    
    # Usa parametri locali o default
    if mu_base is None:
        mu_base = MU_BASE
    if max_brake_decel_g is None:
        max_brake_decel_g = MAX_BRAKE_DECEL_G
    if max_lateral_g is None:
        max_lateral_g = MAX_LATERAL_G
    
    # Distanza tra waypoint (tipicamente 5m)
    dist_step = next_waypoint['dist_m'] - waypoint['dist_m']
    if dist_step <= 0:
        # FIX V5.1: Duplicate waypoint at same distance (section boundary artifact).
        # Instead of forcing a tiny 0.1m step with potentially wrong radius,
        # skip this step entirely by returning the state unchanged.
        # The deduplication in load_hd_waypoints() should prevent this, but
        # this is a safety net for any remaining edge cases.
        return state
    
    # Estrai dati waypoint: usiamo il waypoint successivo come guida del micro-step,
    # così l'integrazione segue il profilo telemetrico già osservato nel runtime legacy.
    source_waypoint = next_waypoint or waypoint
    radius_m = source_waypoint.get('radius_m', waypoint.get('radius_m', 999999.0))
    slope_deg = source_waypoint.get('slope_deg', waypoint.get('slope_deg', 0.0))
    v_ref_kph = source_waypoint.get('v_ref_kph', waypoint.get('v_ref_kph', 200.0))
    throttle_pct = source_waypoint.get('throttle_pct', waypoint.get('throttle_pct', 0))
    brake_pct = source_waypoint.get('brake_pct', waypoint.get('brake_pct', 0))
    drs_active = source_waypoint.get('drs_active', waypoint.get('drs_active', False))
    section_kind = str((section_guidance or {}).get('kind') or '')
    if section_guidance:
        section_radius_m = section_guidance.get('radius_m')
        if section_radius_m is not None and section_kind in {'VerySlowCorner', 'SlowCorner'}:
            try:
                section_radius_m = float(section_radius_m)
                # FIX V4.7: Skip blend when waypoint radius >> section radius (braking zone).
                # The waypoint already has the correct radius from HD data; blending
                # with the apex radius would artificially limit speed during braking.
                if radius_m < section_radius_m * 2.5:
                    blend_weight = 0.60 if section_kind == 'VerySlowCorner' else 0.45
                    radius_m = (max(radius_m, 1.0) ** (1.0 - blend_weight)) * (max(section_radius_m, 1.0) ** blend_weight)
            except (TypeError, ValueError):
                pass
    # FIX V4.10: Floor radius from v_ref to handle noisy HD radius data.
    # If v_ref implies a much larger radius than the HD data provides,
    # the HD radius is likely a GPS artifact (e.g. Silverstone r=48m at 310 kph).
    # Compute minimum radius from v_ref using lateral G limit.
    v_ref_ms_for_radius = v_ref_kph / 3.6
    r_min_from_vref = v_ref_ms_for_radius ** 2 / (max_lateral_g * G)
    if r_min_from_vref > radius_m * 1.5:
        radius_m = r_min_from_vref

    # Se radius > 1000m, è un rettilineo
    is_corner = radius_m < 1000.0
    
    # Calcola forze aerodinamiche
    # P6: Passa ride height da suspension_setup a compute_forces().
    # Senza questo, il fondo/sidepods usano sempre 40mm/50mm di default.
    # Conversione mm→m: ride_height è in mm, compute_forces() vuole metri.
    susp_fx_dict = suspension_effects or {}
    rh_front_m = susp_fx_dict.get('ride_height_front_m', 0.040)  # default 40mm
    rh_rear_m = susp_fx_dict.get('ride_height_rear_m', 0.050)   # default 50mm
    # Validazione: ride height deve essere tra 0.015m e 0.10m (15-100mm)
    rh_front_m = max(0.015, min(0.10, rh_front_m))
    rh_rear_m = max(0.015, min(0.10, rh_rear_m))
    
    aero_forces = aero.compute_forces(
        speed_ms=state.velocity_ms,
        ride_height_front=rh_front_m,
        ride_height_rear=rh_rear_m,
        drs_active=drs_active
    )
    aero_forces = _apply_aero_calibration(aero_forces, aero_calibration)
    
    # P6: Applica ride_height_aero_factor alla downforce del fondo.
    # Ride height troppo alto → meno ground effect → meno downforce dal fondo.
    # Questo fattore è già calcolato in _compute_suspension_effects().
    rh_aero_factor = susp_fx_dict.get('ride_height_aero_factor', 1.0)
    if rh_aero_factor < 1.0:
        # Riduci solo la componente floor/sidepods della downforce.
        # Il floor è ~65-72% della downforce totale (V5.2 floor coupling).
        # Applichiamo il fattore solo alla parte floor, non alle ali.
        floor_fraction = 0.68  # stima conservativa
        aero_forces.f_downforce *= (1.0 - floor_fraction * (1.0 - rh_aero_factor))
    
    # ============================================================
    # 1. POTENZA MOTORE - Modello V5.3 (flat) o V5.4 (stateful)
    # ============================================================
    # V5.3: effective_pu_kw = ICE_PEAK + ERS_PEAK * fraction (flat power)
    # V5.4: F_prop = (T_ICE + T_MGUK + T_MGUH) * G_ratio * FD * η / r_wheel
    #
    # V5.0: rpm_fraction da Reference Pull (per-distanza)
    # Il Reference Pull contiene RPM reale per ogni punto del giro,
    # interpolato per distanza. Questo è molto più informativo della
    # PU Lookup (per-velocità, solo full throttle) perché:
    # - RPM varia 5074-12446 (non solo ~11000)
    # - Include zone di frenata, curva, partiale
    # - Per-distanza → nessuna ambiguità gear/velocità
    #
    # pu_lookup_blend controlla la transizione:
    #   0.0 → potenza costante (comportamento V4, rpm_fraction = 1.0)
    #   1.0 → rpm_fraction completamente da RPM reale (Reference Pull)
    #   0.5 → blend 50/50

    # Calcola rpm_fraction da Reference Pull (per-distanza)
    rpm_fraction = 1.0  # Default: potenza costante (V4)
    throttle_real_pct = throttle_pct  # Default: throttle dai waypoint
    rpm_current = 0.0  # V5.4: RPM for torque calculation
    gear_ratio_current = 1.0  # V5.4: Gear ratio for torque calculation
    
    if pu_lookup_blend > 0.0 and reference_pull is not None:
        ref_data = reference_pull.get("data", {})
        ref_dist = ref_data.get("dist_m", [])
        ref_rpm = ref_data.get("rpm", [])
        ref_throttle = ref_data.get("throttle_pct", [])
        ref_gear = ref_data.get("gear", [])
        
        if ref_dist and ref_rpm and len(ref_dist) > 1:
            # Interpola RPM reale alla distanza corrente
            current_dist = state.distance_m
            # Trova indice per interpolazione
            idx = 0
            for i in range(len(ref_dist) - 1):
                if ref_dist[i + 1] >= current_dist:
                    idx = i
                    break
            else:
                idx = len(ref_dist) - 2
            
            # Interpolazione lineare RPM
            if idx < len(ref_dist) - 1:
                d0 = ref_dist[idx]
                d1 = ref_dist[idx + 1]
                if d1 > d0:
                    t = (current_dist - d0) / (d1 - d0)
                    t = max(0.0, min(1.0, t))
                    rpm_real = ref_rpm[idx] * (1 - t) + ref_rpm[idx + 1] * t
                    # Throttle reale dalla telemetria (Opzione E+)
                    if ref_throttle and idx < len(ref_throttle) - 1:
                        throttle_real_pct = ref_throttle[idx] * (1 - t) + ref_throttle[idx + 1] * t
                        throttle_real_pct = max(0.0, min(100.0, throttle_real_pct))
                    # V5.4: nGear from reference pull
                    if ref_gear and idx < len(ref_gear) - 1:
                        n_gear_real = ref_gear[idx] * (1 - t) + ref_gear[idx + 1] * t
                        n_gear_int = max(1, min(8, int(round(n_gear_real))))
                        gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                        rpm_current = rpm_real
                else:
                    rpm_real = ref_rpm[idx]
                    if ref_throttle and idx < len(ref_throttle):
                        throttle_real_pct = max(0.0, min(100.0, ref_throttle[idx]))
                    if ref_gear and idx < len(ref_gear):
                        n_gear_int = max(1, min(8, int(round(ref_gear[idx]))))
                        gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                        rpm_current = rpm_real
            else:
                rpm_real = ref_rpm[idx]
                if ref_throttle and idx < len(ref_throttle):
                    throttle_real_pct = max(0.0, min(100.0, ref_throttle[idx]))
                if ref_gear and idx < len(ref_gear):
                    n_gear_int = max(1, min(8, int(round(ref_gear[idx]))))
                    gear_ratio_current = get_gear_ratio_from_n_gear(n_gear_int)
                    rpm_current = rpm_real
            
            # rpm_fraction: frazione di potenza disponibile a questo RPM
            # Potenza ICE segue curva: min a idle, max a peak RPM
            rpm_frac_real = max(0.3, min(1.0, (rpm_real - ICE_IDLE_RPM) / (ICE_MAX_RPM - ICE_IDLE_RPM)))
            # Blend tra potenza costante (rpm_frac=1.0) e RPM reale
            rpm_fraction = 1.0 + pu_lookup_blend * (rpm_frac_real - 1.0)

    # ============================================================
    # V5.4: PU Stateful Model (torque-based)
    # ============================================================
    if pu_ctx is not None:
        # V5.4 mode: torque-based propulsive force
        
        # Get RPM and gear ratio
        if rpm_current > 0 and gear_ratio_current > 0:
            # From Reference Pull (Level 1)
            rpm = rpm_current
            gear_ratio = gear_ratio_current
        else:
            # Synthetic gearbox (Level 3 fallback)
            n_gear, gear_ratio, rpm = get_optimal_gear(state.velocity_ms)
        
        # Section kind for MGU-H factors
        section_kind = waypoint.get("section_kind", "Straight")
        
        # Lap progress for dynamic SOC floor
        total_dist = waypoint.get("dist_m", 0.0)
        lap_progress = min(1.0, total_dist / max(waypoint.get("circuit_length_m", 5000.0), 1.0))
        
        # Compute dt for this step
        dt_step = max(0.001, (next_waypoint.get("dist_m", waypoint.get("dist_m", 0) + 5) - waypoint.get("dist_m", 0)) / max(state.velocity_ms, 1.0))
        
        # Derive brake_pct for harvesting: if waypoint brake_pct is 0 (common in HD data),
        # estimate from throttle and look-ahead speed delta
        brake_pct_for_ers = waypoint.get("brake_pct", 0.0)
        if brake_pct_for_ers < 1 and throttle_real_pct < 20:
            # Look ahead 10-20 waypoints to find minimum speed in braking zone
            v_curr = waypoint.get("v_ref_kph", 0)
            v_min_ahead = v_curr
            look_ahead = min(20, len(waypoints) - waypoint_idx - 1) if waypoints else 1
            for la in range(1, look_ahead + 1):
                la_idx = waypoint_idx + la
                if la_idx < len(waypoints):
                    v_la = waypoints[la_idx].get("v_ref_kph", 0)
                    if v_la < v_min_ahead:
                        v_min_ahead = v_la
                    # Stop looking if speed starts increasing (end of braking zone)
                    if v_la > v_min_ahead * 1.02 and la > 3:
                        break

            if v_curr > 0 and v_min_ahead < v_curr * 0.95:
                # Significant speed drop ahead → braking zone
                speed_drop_frac = (v_curr - v_min_ahead) / v_curr
                # Scale: 10% drop = ~30% brake, 30% drop = ~80% brake
                brake_pct_for_ers = min(100, speed_drop_frac * 300)

        # Compute propulsive force using V5.4 model
        f_engine = compute_f_engine_v54(
            pu_ctx=pu_ctx,
            rpm=rpm,
            gear_ratio=gear_ratio,
            throttle_pct=throttle_real_pct,
            section_kind=section_kind,
            dt_s=dt_step,
            lap_progress=lap_progress,
            is_corner=is_corner,
            radius_m=radius_m,
            driver_skill=driver_skill,
            brake_pct=brake_pct_for_ers,
            drs_active=waypoint.get("drs_active", False),
            section_length_m=waypoint.get("section_length_m", 100.0),
            v_ms=state.velocity_ms,
            dist_m=waypoint.get("dist_m", 0.0),
        )
        
        # Update thermal state using instantaneous ERS power (not cumulative)
        # MGU-K power from last deploy + MGU-H power
        last_trace = pu_ctx.energy_trace[-1] if pu_ctx.energy_trace else {}
        mguk_power_kw = last_trace.get("deploy_mj", 0) * 1000.0 / max(dt_step, 0.001)
        mguh_power_kw = last_trace.get("mguh_direct_mj", 0) * 1000.0 / max(dt_step, 0.001)
        total_ers_power_kw = mguk_power_kw + mguh_power_kw
        update_thermal_state(pu_ctx, total_ers_power_kw, state.velocity_ms, dt_step)
        
        # Traction limit at low speed
        if state.velocity_ms <= 1.0:
            max_traction_force = mu_base.get(tyre_compound, 1.65) * mass_kg * G * 0.85
            f_engine = min(f_engine, max_traction_force)
        
        # Power limit: force cannot exceed P_max / v (same physics as V5.3)
        # This prevents V5.4 from having too much force at low speeds
        # compared to V5.3's power/v model. P_max = ICE peak + ERS peak.
        if state.velocity_ms > 1.0:
            ice_peak_kw = 750.0  # kW — approximate ICE peak power
            ers_peak_kw = pu_ctx.ers_output_kw if pu_ctx else 160.0
            p_max_kw = ice_peak_kw + ers_peak_kw
            max_force_from_power = p_max_kw * 1000.0 / state.velocity_ms
            f_engine = min(f_engine, max_force_from_power)
    
    else:
        # ============================================================
        # V5.3: Flat Power Model (legacy, backward compatible)
        # ============================================================
        effective_pu_kw = ICE_PEAK_POWER_KW + ERS_PEAK_POWER_KW * ers_power_fraction

        if is_corner:
            # In curva: potenza ridotta per trazione
            # Più curva stretta = meno potenza disponibile
            corner_factor = min(1.0, 1000.0 / max(radius_m, 100.0))
            power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_real_pct / 100.0) * corner_factor
        else:
            # In rettilineo: potenza massima
            power_available = effective_pu_kw * 1000 * rpm_fraction * (throttle_real_pct / 100.0)
        
        # Efficienza trasmissione e driver skill
        power_available *= DRIVETRAIN_EFFICIENCY
        power_available *= driver_skill

        # Forza motrice = Potenza / Velocità
        if state.velocity_ms > 1.0:
            f_engine = power_available / state.velocity_ms
        else:
            # A basse velocità (uscita curva), limita potenza per trazione
            f_engine = power_available / 1.0
            # Limita accelerazione per evitare wheel spin
            # FIX V4.4: Aumentato da 0.60 a 0.85 per permettere accelerazione in uscita curva
            max_traction_force = mu_base.get(tyre_compound, 1.65) * mass_kg * G * 0.85  # 85% grip posteriore
            f_engine = min(f_engine, max_traction_force)
    
    state.f_engine = f_engine
    state.is_throttle = throttle_pct > 0
    # ============================================================
    # V5.0: REFERENCE PULL - Correzione forza motrice da telemetria reale
    # ============================================================
    # Se la velocità simulata diverge da quella reale (TracingInsights),
    # applichiamo una correzione di coppia per riallineare la traccia.
    # Questo non sostituisce la fisica, ma corregge errori sistematici
    # nel modello PU (mappa RPM/coppia, clipping ERS, ecc.).
    #
    # reference_pull_strength: 0.0 = disabilitato, 1.0 = full correction
    # Tipico: 0.15-0.30 per correzione sottile senza dominare la fisica
    if reference_pull_strength > 0.0 and reference_pull is not None:
        ref_data = reference_pull.get("data", {})
        ref_dist = ref_data.get("dist_m", [])
        ref_speed = ref_data.get("speed_kph", [])
        if ref_dist and ref_speed and len(ref_dist) > 0:
            # Interpola velocità reale alla distanza corrente
            current_dist = state.distance_m
            ref_dist_arr = ref_dist
            ref_speed_arr = ref_speed
            # Trova indice più vicino
            idx = 0
            for i in range(len(ref_dist_arr) - 1):
                if ref_dist_arr[i + 1] >= current_dist:
                    idx = i
                    break
            else:
                idx = len(ref_dist_arr) - 2
            
            # Interpolazione lineare
            if idx < len(ref_dist_arr) - 1:
                d0 = ref_dist_arr[idx]
                d1 = ref_dist_arr[idx + 1]
                if d1 > d0:
                    t = (current_dist - d0) / (d1 - d0)
                    t = max(0.0, min(1.0, t))
                    v_ref_kph_real = ref_speed_arr[idx] * (1 - t) + ref_speed_arr[idx + 1] * t
                else:
                    v_ref_kph_real = ref_speed_arr[idx]
            else:
                v_ref_kph_real = ref_speed_arr[idx]
            
            v_ref_ms_real = v_ref_kph_real / 3.6
            v_sim_ms = state.velocity_ms
            
            # Correzione proporzionale alla differenza di velocità
            # Se la simulazione è più lenta del reale → aumenta forza motrice
            # Se la simulazione è più veloce → riduci forza motrice
            v_error = v_ref_ms_real - v_sim_ms  # Positivo = sim troppo lento
            
            # La correzione è proporzionale all'errore e alla massa
            # F_correction = strength * m * (v_error / v_ref) * g
            # Questo dà una correzione graduale che non domina la fisica
            if abs(v_ref_ms_real) > 1.0:
                f_correction = (reference_pull_strength * mass_kg * v_error 
                                / max(v_ref_ms_real, 10.0) * G)
                # Limita la correzione a ±20% della forza motrice
                max_correction = abs(f_engine) * 0.20
                f_correction = max(-max_correction, min(max_correction, f_correction))
                f_engine += f_correction
                state.f_engine = f_engine
    
    # ============================================================
    # 2. FORZA DRAG - Aerodinamica + Rolling + Steering
    # ============================================================
    state.f_drag = aero_forces.f_drag
    f_rolling = ROLLING_RESISTANCE_COEFF * mass_kg * G
    state.f_drag += f_rolling
    
    # ============================================================
    # PHYSICS FIX V4.2 #1: Steering Induced Drag (Deadzone)
    # ============================================================
    # Deadzone: Se steering_angle < 2 gradi, nessun drag aggiuntivo
    # Questo evita resistenza parassita sui rettilinei (Monza)
    steering_angle_deg = abs(waypoint.get('steering_angle_deg', 0.0))
    if steering_angle_deg >= 2.0 and state.velocity_ms > 1.0:  # Deadzone: ignora < 2 gradi
        v_kph = state.velocity_ms * 3.6
        v_ref_kph = 100.0  # Velocità di riferimento per calibrazione
        steer_drag_coeff = 45.0  # N/degree base a 100 km/h
        
        # Fattore non-lineare: più effetto a basse velocità (Monaco)
        if v_kph < 60.0:
            velocity_factor = 2.0  # Raddoppia effetto a < 60 km/h
        elif v_kph > 200.0:
            velocity_factor = 0.5  # Dimezza effetto a > 200 km/h
        else:
            velocity_factor = 1.0  # Normale tra 60-200 km/h
        
        f_steer_drag = steer_drag_coeff * steering_angle_deg * ((v_kph / v_ref_kph) ** 2) * velocity_factor
        state.f_drag += f_steer_drag
    
    # ============================================================
    # 3. FORZA GRAVITÀ - Pendenza
    # ============================================================
    slope_rad = math.radians(slope_deg)
    state.f_gravity = mass_kg * G * math.sin(slope_rad)
    
    # ============================================================
    # 4. GRIP TOTALE - Modello fisico puro (NO reverse engineering)
    # ============================================================
    # Formula: F_lat_max = (Massa * G + F_downforce) * MU_BASE * track_grip_factor
    # 
    # MU_BASE viene dal compound gomme:
    #   C5 = 1.80, C4 = 1.72, C3 = 1.65, C2 = 1.58, C1 = 1.52
    #
    # V5.0: Se abbiamo mu_mechanical dalla calibrazione aero, usiamo quello
    # come baseline per il grip meccanico. Questo valore è derivato dalla
    # telemetria reale e rappresenta il grip a bassa velocità (senza downforce).
    # È circuit-specific e include l'effetto dell'asfalto e del compound.
    #
    # track_grip_factor è fisso per circuito:
    #   Monza = 1.00, Monaco = 0.90, Suzuka = 1.05
    
    # Grip base dal compound (senza penalità empiriche)
    mu_base_val = mu_base.get(tyre_compound, 1.65)
    
    # V5.0: Se abbiamo mu_mechanical dalla calibrazione aero, usiamo quello.
    # Il mu_mechanical è derivato dalla telemetria reale e rappresenta il
    # grip meccanico a bassa velocità (senza downforce). È circuit-specific
    # e include l'effetto dell'asfalto e del compound.
    # Valori tipici: 1.54 (Las Vegas) a 2.58 (Montreal).
    # NOTA: Valori > 2.0 indicano che il downforce è parzialmente incluso,
    # ma lo usiamo comunque perché rappresenta il grip reale a bassa velocità.
    aero_cal_mu_mechanical = None
    if aero_calibration is not None:
        aero_cal_mu_mechanical = aero_calibration.get("mu_mechanical")
        if aero_cal_mu_mechanical is not None:
            try:
                aero_cal_mu_mechanical = float(aero_cal_mu_mechanical)
            except (TypeError, ValueError):
                aero_cal_mu_mechanical = None
    
    if aero_cal_mu_mechanical is not None and aero_cal_mu_mechanical > 0:
        # V5.6: Scala mu_mechanical per il compound rispetto alla SOFT di calibrazione.
        # La calibrazione aero è fatta con la SOFT del weekend (telemetria qualifica).
        # La soft varia per circuito: C3 (Sakhir), C4 (Spa), C5 (Monza), C6 (Monaco).
        # Il compound ratio preserva la differenza tra mescole:
        #   Se soft=C5 e usiamo C3: ratio = MU_BASE[C3]/MU_BASE[C5] = 0.907/1.154 = 0.786
        #   Se soft=C5 e usiamo C5: ratio = 1.000 (nessun cambio)
        #   Se soft=C5 e usiamo C6: ratio = MU_BASE[C6]/MU_BASE[C5] = 1.187/1.154 = 1.029
        calibration_compound = "C3"  # Default fallback
        if aero_calibration is not None:
            calibration_compound = aero_calibration.get("calibration_compound", "C3")
        cal_mu = mu_base.get(calibration_compound, 1.82)
        target_mu = mu_base.get(tyre_compound, 1.65)
        compound_ratio = target_mu / cal_mu if cal_mu > 0 else 1.0
        mu_base_val = aero_cal_mu_mechanical * compound_ratio
    elif reference_pull is not None:
        # Fallback: Se non abbiamo mu_mechanical dalla calibrazione aero,
        # usiamo il Reference Pull con mu_mechanical derivato dalla telemetria.
        # NOTA: Il mu_mechanical derivato dalla telemetria include downforce
        # anche a basse velocità, quindi va usato con cautela. Lo applichiamo
        # solo se il valore è ragionevole (< 2.0, che è grip meccanico puro).
        # Valori > 2.0 indicano che il downforce è già incluso.
        ref_mu_mechanical = reference_pull.get("mu_mechanical", 0.0)
        if 1.5 < ref_mu_mechanical < 2.0:
            # Il mu_mechanical reale è il grip a bassa velocità (senza downforce).
            # Lo usiamo come baseline, scalato per il compound.
            compound_scale = mu_base_val / mu_base.get(tyre_compound, 1.65)
            mu_base_val = ref_mu_mechanical * compound_scale
    
    # Applica track_grip_factor da telemetry_mu (ora è fisso per circuito)
    track_grip_factor = waypoint.get('telemetry_mu', 1.0)
    if track_grip_factor is not None and track_grip_factor > 0:
        mu_base_val *= track_grip_factor
    
    # Applica driver skill (pilota migliore → sfrutta meglio il grip)
    mu_base_val *= driver_skill

    # Applica effetto sospensioni sul grip meccanico
    # Molle non ottimali → peggior contatto gomma-asfalto → meno grip
    susp_fx = suspension_effects or {}
    mu_base_val *= susp_fx.get('mechanical_grip_factor', 1.0)

    # Calcola downforce (contata UNA SOLA VOLTA qui)
    # FIX V4.14: Usa f_downforce diretto da AeroAssembly (Newtons).
    # Prima: f_downforce = q * cla_total, ma cla_total = f_down/(q*A_REF_F1),
    # quindi f_downforce = f_down/1.60 → perdeva 37.5% della downforce reale.
    # Il drag usava f_drag diretto (100%), creando un bias sistematico che
    # penalizzava le ali alte: pagavano 100% drag ma ottenevano solo 62.5% grip.
    dynamic_pressure = 0.5 * RHO_SEA_LEVEL * state.velocity_ms ** 2
    f_downforce = aero_forces.f_downforce
    
    # Carico verticale totale = peso + downforce
    f_vertical = mass_kg * G + f_downforce  # N
    f_vertical_kn = f_vertical / 1000.0  # kN
    
    # ============================================================
    # PHYSICS FIX V4.2 #2: Load Sensitivity Separata (Long vs Lat)
    # ============================================================
    # Il grip longitudinale (trazione/frenata) deve risentire meno della
    # load sensitivity rispetto al grip laterale (curva).
    # Formula laterale: grip_lat = mu_base * Fz * (1.0 - K * Fz)
    # Formula longitudinale: grip_long = mu_base * Fz * (1.0 - 0.5*K * Fz)
    # Questo aiuta sec_11 (Monaco) a scaricare potenza meglio in uscita curva
    #
    # FIX V4.16: Aumentato K da 0.00008 a 0.010 per rendere il downforce
    # meno sempre-conveniente e creare la curva a campana a Suzuka.
    # Con K=0.00008 il grip decade solo dello 0.1% tra setup basso e alto.
    # Con K=0.010 il grip decade del ~7% tra setup basso e alto.
    # In F1 reale, il grip specifico decade ~15-20% quando il carico raddoppia.
    # K=0.010 produce un decadimento del ~20% a carico doppio, realistico.
    # Questo fa sì che il downforce extra sia meno efficace ad alto carico,
    # creando un optimum intermedio (campana) sui circuiti bilanciati.
    load_sensitivity_k = 0.010  # FIX V4.16: era 0.00008, poi 0.003, poi 0.006
    
    # Load factor per grip laterale (curva) - full sensitivity
    lat_load_factor = 1.0 - (load_sensitivity_k * f_vertical_kn)
    lat_load_factor = max(0.75, min(1.0, lat_load_factor))  # Clamp tra 0.75 e 1.0
    
    # Load factor per grip longitudinale (trazione/frenata) - half sensitivity
    long_load_factor = 1.0 - (load_sensitivity_k * 0.5 * f_vertical_kn)
    long_load_factor = max(0.85, min(1.0, long_load_factor))  # Clamp tra 0.85 e 1.0
    
    # Grip totale laterale (usato per v_max in curva)
    f_grip_total_lateral = mu_base_val * f_vertical * lat_load_factor

    # Applica penalità ARB sospensioni sul grip laterale
    # ARB non ottimale → eccesso load transfer → meno grip in curva
    corner_grip_penalty = susp_fx.get('corner_grip_penalty', 0.0)
    if corner_grip_penalty > 0.0:
        f_grip_total_lateral *= (1.0 - corner_grip_penalty)

    # Grip totale longitudinale (usato per trazione/frenata)
    f_grip_total_longitudinal = mu_base_val * f_vertical * long_load_factor
    
    # ============================================================
    # PHYSICS FIX V4.3 #2: Traction Bonus (Differenziale - Exit Speed)
    # ============================================================
    # Quando le ruote sono quasi dritte (sterzo < 25°), velocità < 120 km/h
    # e raggio curva < 60m (Monaco/Suzuka), il differenziale autobloccante F1
    # massimizza la trazione in uscita curva.
    # Applichiamo un bonus del 20% al grip longitudinale SOLO in queste condizioni.
    # NOTA: Soglia sterzo alzata da 15° a 25° per anticipare accelerazione in uscita
    v_kph = state.velocity_ms * 3.6
    steering_angle_deg = abs(waypoint.get('steering_angle_deg', 0.0))
    
    longitudinal_traction_bonus = 1.0
    # Applica solo per curve strette (Monaco/Suzuka), non per Monza
    # Soglia sterzo aumentata a 25° per permettere accelerazione anticipata
    # FIX V4.4: Esteso da 120 a 160 km/h per coprire marce medie di circuiti veloci (Spa, Silverstone)
    if v_kph < 160.0 and steering_angle_deg < 25.0 and state.is_throttle and radius_m < 60.0 and radius_m > 0.0:
        # Bonus del 20% per simulare differenziale che massimizza spinta
        # Questo aiuta sec_11 (Monaco), sec_08 e sec_14 (Suzuka) in uscita
        longitudinal_traction_bonus = 1.20
        f_grip_total_longitudinal *= longitudinal_traction_bonus
    
    # ============================================================
    # PHYSICS FIX V4.3 #1: Curvature Grip Bonus (Suzuka S-Curves)
    # ============================================================
    # Nelle curve con raggio < 120m (esteso per Suzuka S-Curves), il grip laterale
    # è sottostimato perché il raggio effettivo del waypoint non tiene conto:
    #   - Curb che allargano la traiettoria effettiva
    #   - Banking che aumenta grip
    #   - Gomme che lavorano meglio a angoli di sterzo elevati
    #   - S-Curves che richiedono grip in transizione rapida
    # Applichiamo un bonus progressivo: +12% a r=20m, 0% a r=120m
    # FIX V4.6: Rimosso perché causa sovasterzo in curve medie (Silverstone Luffield)
    curvature_grip_bonus = 1.0
    # if is_corner and radius_m < 120.0 and radius_m > 0.0:  # RIMOSSO
    #     curvature_grip_bonus = 1.12 - 0.12 * ((radius_m - 20.0) / 100.0)
    #     curvature_grip_bonus = max(1.0, min(1.12, curvature_grip_bonus))
    #     f_grip_total_lateral *= curvature_grip_bonus
    
    # Load transfer in frenata/accelerazione (usa grip longitudinale)
    if state.is_braking:
        # Frenata: load transfer anteriore → grip posteriore ridotto
        # Sospensioni sbilanciate peggiorano la stabilità in frenata
        braking_stability = susp_fx.get('braking_stability_factor', 1.0)
        load_transfer_factor = 0.85 * braking_stability  # -15% base + penalità sospensioni
        f_grip_total = f_grip_total_longitudinal * load_transfer_factor
    elif state.is_throttle:
        # Accelerazione: load transfer posteriore → grip posteriore aumentato
        # Se sterzo < 15°, applica bonus differenziale già incluso in f_grip_total_longitudinal
        load_transfer_factor = 1.05  # +5% grip posteriore
        f_grip_total = f_grip_total_longitudinal * load_transfer_factor
    else:
        # In curva costante, usa grip laterale
        f_grip_total = f_grip_total_lateral
    
    # ============================================================
    # 5. VELOCITÀ MASSIMA IN CURVA - Solo dalla fisica (grip limit)
    # ============================================================
    # La velocità deve emergere dalla fisica, non dalla telemetria.
    #
    # FIX V4.13: Due correzioni critiche:
    #
    # (a) Usa SEMPRE f_grip_total_lateral per v_max_corner.
    #     Prima usava f_grip_total che in frenata/trazione era il grip
    #     longitudinale — fisicamente sbagliato per il limite laterale.
    #
    # (b) Applica CORNERING_UTILIZATION = 0.63.
    #     Il grip teorico (mu × F_vert) dà v_max_corner 20-130% superiore
    #     alla velocità reale (es. Monaco hairpin: 107 kph vs reale 47 kph).
    #     In curva il pilota NON usa il 100% del grip laterale perché:
    #       - Combined loading: frenata/trazione consumano parte del grip
    #       - Margine di sicurezza (muri, cordoli)
    #       - Transitori: cambio di direzione, trasferimento di carico
    #       - Superficie irregolare (bumps, vernice)
    #     Il fattore 0.63 porta v_max_corner ~10-20% sopra v_ref per il
    #     setup di riferimento, rendendo la downforce il VINCOLO ATTIVO
    #     sulle curve più impegnative (Monaco, Suzuka hairpin).
    #     Questo fa sì che più downforce → più grip → curva più veloce.

    # Cornering utilization: dipendente dal raggio.
    # Curve strette (r<60m, Monaco hairpin): il pilota usa ~60% del grip
    #   → combined loading, muri, transitori, margine sicurezza
    # Curve aperte (r>90m, Monza/Silverstone): il pilota usa ~95% del grip
    #   → stato stazionario, spazi di fuga, stabilità aerodinamica
    #
    # Formula: CU = min(0.95, 0.35 + radius / 150)
    #   r=30m → CU=0.55    r=45m → CU=0.65    r=77m → CU=0.86
    #   r=90m → CU=0.95    r=150m+ → CU=0.95 (cap)

    if is_corner:
        cu = min(0.95, 0.35 + radius_m / 150.0)
        v_max_corner_ms = math.sqrt(
            f_grip_total_lateral * cu * radius_m / mass_kg
        )
    else:
        v_max_corner_ms = 999.0  # Nessun limite in rettilineo
    
    # ============================================================
    # 6. FRENATA - Driver model con calcolo fisico della distanza
    # ============================================================
    # Il pilota calcola la distanza di frenata D usando:
    #   D = (v_current² - v_corner²) / (2 * a_brake)
    # dove a_brake = F_brakes / Massa = max_brake_decel_g * G
    #
    # Deve iniziare a frenare ESATTAMENTE a distanza D dal punto
    # più lento della curva successiva.
    #
    # V5.5: Frenata con commitment (anti-chatter hysteresis).
    # Il lookahead V5.3 decide WHEN iniziare a frenare (logica fisica invariata).
    # Una volta committato, la frenata resta attiva finché v <= target + EPS,
    # ignorando le decisioni per-step. Questo elimina il chatter brake/throttle
    # vicino alla velocità target che causava 174 transizioni a Monaco.
    # Nessuna dipendenza dalla telemetria: funziona su tutti i 24 circuiti.

    # V6.0: BRAKING LOGIC - PHYSICS-DRIVEN (v_max_corner + brake_needed)
    # ============================================================
    # V6.0: Il target di velocità è physics-driven (v_max_corner) non telemetry-driven (v_ref).
    # Il lookahead (compute_braking_zones_v6) identifica QUANDO frenare, non il target.

    # V6.0 FIX: Inizializza v_target_ms da v_max_corner se è una curva (< 999),
    # altrimenti usa v_ref_kph per i rettilinei. Questo previene il problema di Las Vegas
    # dove v_max_corner=999 causava il car a non frenare mai poiché state.velocity < 999.
    if v_max_corner_array is not None and 0 <= waypoint_idx < len(v_max_corner_array):
        v_mc = v_max_corner_array[waypoint_idx]
        # Se v_max_corner è 999 (rettilineo = no constraint), usa v_ref di telemetria
        if v_mc < 999.0:  # È una curva: usa v_max_corner fisico
            v_target_ms = v_mc
        else:  # È un rettilineo: usa v_ref di telemetria
            v_target_ms = v_ref_kph / 3.6
    else:
        # Fallback a V5.7 se v_max_corner_array non disponibile (backward compatibility)
        v_target_ms = v_ref_kph / 3.6

    # Applica section speed scale (se overridato da calibrazione)
    if section_speed_scale > 0.0:
        v_target_ms *= section_speed_scale

    # V6.0: Braking decision semplificata
    # Se brake_needed[waypoint_idx] = True AND velocità > target, frena
    must_brake = False
    if brake_needed is not None and 0 <= waypoint_idx < len(brake_needed):
        if brake_needed[waypoint_idx] and state.velocity_ms > v_target_ms + 0.1:
            must_brake = True
    else:
        # Fallback: se brake_needed non è disponibile, non frenare (backward compatibility)
        must_brake = False

    # FIX V4.7: Use longitudinal grip for braking decel limit
    max_brake_decel_phys = f_grip_total_longitudinal / mass_kg
    max_brake_decel = min(max_brake_decel_g * G, max_brake_decel_phys)

    # V6.0: Applicazione frenata semplificata
    if must_brake:
        state.is_braking = True
        f_target_decel = mass_kg * max_brake_decel
        state.f_engine = -f_target_decel + state.f_drag + state.f_gravity
        state.f_engine = max(state.f_engine, -f_grip_total)
    else:
        state.is_braking = False
    
    # ============================================================
    # 7. ACCELERAZIONE NETTA (F = m × a)
    # ============================================================
    f_net = state.f_engine - state.f_drag - state.f_gravity
    state.acceleration_ms2 = f_net / mass_kg
    
    # ============================================================
    # 8. LIMITI FISICI
    # ============================================================
    
    # Limita accelerazione laterale in curva
    if is_corner:
        a_lat = state.velocity_ms ** 2 / radius_m
        a_lat_g = a_lat / G
        
        if a_lat_g > max_lateral_g:
            # Troppa accelerazione laterale: riduci velocità
            v_max_safe_ms = math.sqrt(max_lateral_g * G * radius_m)
            v_target_ms = min(v_target_ms, v_max_safe_ms)
    
    # Limita velocità in curva dal grip disponibile
    v_target_ms = min(v_target_ms, v_max_corner_ms)
    
    # ============================================================
    # 9. INTEGRA CINEMATICA - FISICA PURA
    # ============================================================
    # v_new² = v_old² + 2 × a × d
    v_squared_new = state.velocity_ms ** 2 + 2 * state.acceleration_ms2 * dist_step
    v_squared_new = max(0.0, v_squared_new)  # Evita sqrt negativo
    
    v_new_ms = math.sqrt(v_squared_new)
    
    # Limita la velocità al grip fisico disponibile (v_max_corner_ms)
    v_new_ms = min(v_new_ms, v_max_corner_ms)

    # V6.0: Limita anche a v_target_ms (la velocità calcolata dal modello physics-driven)
    # Questo serve per rispettare il limite di curva anche quando non stiamo frenando
    v_new_ms = min(v_new_ms, v_target_ms)

    # FIX V5.4.3: Limit speed drop at section boundary transitions.
    # At section boundaries, the first waypoint of the incoming section
    # carries the APEX minimum radius (e.g. 77m for Monaco T1) instead of
    # the actual radius at that track position (e.g. 4660m at corner entry).
    # This causes v_max_corner to drop catastrophically in a single step.
    # Detection: short steps (dist_step < 1.0m) where radius drops by >80%.
    # At these points, limit the speed drop to 30 kph per step.
    # At normal 5m steps, the car has enough distance to brake properly.
    is_boundary_transition = False
    if dist_step < 1.0 and waypoints is not None and waypoint_idx > 0:
        prev_wp = waypoints[waypoint_idx - 1]
        prev_radius = prev_wp.get('radius_m', 9999.0)
        if radius_m < prev_radius * 0.2 and prev_radius > 100:
            is_boundary_transition = True
    if dist_step < 0.02:  # Also apply at boundary duplicates
        is_boundary_transition = True
    if is_boundary_transition:
        max_drop_ms = 30.0 / 3.6  # 30 kph in m/s
        v_new_ms = max(v_new_ms, state.velocity_ms - max_drop_ms)
    
    v_new_ms = max(v_new_ms, 1.0)  # Floor numerico minimo per stabilità
    
    # ============================================================
    # 10. CALCOLO TEMPO STEP
    # ============================================================
    v_avg_ms = (state.velocity_ms + v_new_ms) / 2.0
    if v_avg_ms > 1.0:
        dt = dist_step / v_avg_ms
    else:
        dt = dist_step / 1.0
    
    # ============================================================
    # 11. AGGIORNA STATO
    # ============================================================
    new_state = PhysicsState(
        distance_m=state.distance_m + dist_step,
        velocity_ms=v_new_ms,
        acceleration_ms2=state.acceleration_ms2,
        time_s=state.time_s + dt,
        f_engine=state.f_engine,
        f_drag=state.f_drag,
        f_downforce=aero_forces.f_downforce,
        f_gravity=state.f_gravity,
        f_centripetal=mass_kg * v_new_ms ** 2 / radius_m if is_corner else 0.0,
        is_braking=state.is_braking,
        is_throttle=state.is_throttle,
        is_drs_active=drs_active,
        brake_target_v_ms=state.brake_target_v_ms,  # V5.5: propaga commitment fra step
        telemetry_points=state.telemetry_points
    )
    
    # Salva telemetria
    new_state.telemetry_points.append({
        'distance_m': new_state.distance_m,
        'velocity_ms': new_state.velocity_ms,
        'velocity_kph': new_state.velocity_ms * 3.6,
        'acceleration_ms2': new_state.acceleration_ms2,
        'time_s': new_state.time_s,
        'radius_m': radius_m,
        'is_braking': new_state.is_braking,
        'is_throttle': new_state.is_throttle,
        'drs_active': new_state.is_drs_active,
    })
    
    return new_state


def integrate_lap_hd(
    circuit_id: str,
    aero_setup: Optional[Dict] = None,
    mass_kg: float = MASS_TOTAL_QUALY_KG,
    tyre_compound: str = "C3",
    driver_skill: float = 1.0,
    verbose: bool = False,
    # Calibration parameters (override defaults)
    mu_override: Optional[Dict[str, float]] = None,
    max_brake_decel_g_override: Optional[float] = None,
    max_lateral_g_override: Optional[float] = None,
    aero_calibration: Optional[Dict[str, Any]] = None,
    # Sospensioni
    suspension_setup: Optional[Dict] = None,
    # Sector tracking (per confronto con telemetria)
    sector_boundaries: Optional[List[float]] = None,
    # ERS mode: frazione di potenza ERS disponibile (0.0=solo ICE, 1.0=full quali)
    ers_power_fraction: float = 1.0,
    # V5.0: Reference Pull strength (0.0=disabilitato, tipico 0.01-0.05)
    # Quando >0, la forza motrice viene corretta per allineare la velocità
    # simulata alla traccia reale di TracingInsights.
    reference_pull_strength: float = 0.0,
    # V5.0: PU Lookup RPM blend (0.0=constant power, 1.0=RPM from lookup)
    # Quando >0, la curva di potenza usa RPM reali dalla PU Lookup
    # per modellare la dipendenza RPM-potenza del motore.
    pu_lookup_blend: float = 0.0,
    pu_config: Optional[Dict] = None,  # V5.5: None=V5.3 flat (legacy), {"engine_map": "QUALIFY"}=V5.4 stateful
) -> Dict[str, Any]:
    """
    Simula giro completo su circuito HD.
    
    Args:
      circuit_id: identificativo circuito (es. "it-1922_monza")
      aero_setup: configurazione aero (es. {"front_wing": 16.0, "rear_wing": 18.0})
      mass_kg: massa totale auto (default: qualifica)
      tyre_compound: mescola gomme
      driver_skill: abilità pilota (1.0 = medio, 1.05 = +5%)
      verbose: stampa debug
      mu_override: override grip gomme (es. {"C5": 1.98})
      max_brake_decel_g_override: override frenata (default: 6.5g)
      max_lateral_g_override: override accelerazione laterale (default: 5.5g)
      aero_calibration: profilo aero calibrato (CdA/ClA/drag/downforce)
      sector_boundaries: lista distanze confini settori [m] (opzionale, default: 3 settori uguali)
    
    Returns:
      Dizionario con:
        - lap_time_s: tempo giro [s]
        - sector_times: lista tempi settori [s] (3 default o N se sector_boundaries fornito)
        - v_max_kph: velocità massima
        - v_min_kph: velocità minima
        - v_avg_kph: velocità media
        - telemetry: lista punti telemetria
    """
    
    # Carica waypoints
    if verbose:
        print(f"🏁 Caricamento {circuit_id}...")
    
    waypoints = load_hd_waypoints(circuit_id)
    reference_sections = _load_reference_sections(circuit_id)
    
    # V5.0: Carica Reference Pull da telemetria reale TracingInsights
    # Se disponibile, fornisce velocità/throttle/brake reali per correggere
    # la forza motrice quando la simulazione diverge dalla traccia reale.
    reference_pull = TelemetryBridge.load_reference_pull(circuit_id)
    if reference_pull and verbose:
        print(f"  📡 Reference Pull caricato: {reference_pull.get('driver', '?')} "
              f"{reference_pull.get('lap_time_s', 0):.3f}s")
    
    # V5.0: Carica PU Lookup per fusione modello generico + dati reali
    pu_lookup_interpolator = None
    if pu_lookup_blend > 0.0:
        pu_lookup_data = load_pu_lookup(circuit_id)
        if pu_lookup_data:
            pu_lookup_interpolator = PULookupInterpolator(pu_lookup_data)
            if verbose:
                speed_min, speed_max = pu_lookup_interpolator.speed_range
                print(f"  🔋 PU Lookup caricato: {pu_lookup_interpolator.num_entries} punti, "
                      f"speed {speed_min:.0f}-{speed_max:.0f} kph, blend={pu_lookup_blend:.2f}")
        elif verbose:
            print(f"  ⚠️ PU Lookup non trovato per {circuit_id}, blend disabilitato")
    
    # V5.5: Inizializza PU stateful model (default: QUALIFY)
    pu_ctx = None
    if pu_config is not None:
        engine_map = pu_config.get("engine_map", "QUALIFY")
        pu_ctx = init_pu_context(circuit_id, engine_map)
    else:
        # V5.5: PU stateful attivo di default con QUALIFY map
        pu_ctx = init_pu_context(circuit_id, "QUALIFY")
    if verbose and pu_ctx is not None:
        print(f"  ⚡ V5.5 PU Stateful: map={pu_ctx.engine_map}, "
              f"deploy={pu_ctx.deploy_mj_per_lap:.2f} MJ, "
              f"harvest={pu_ctx.harvest_mj_per_lap:.2f} MJ, "
              f"mguh_power={pu_ctx.mguh_power_kw:.1f} kW, "
              f"ers_output={pu_ctx.ers_output_kw:.1f} kW")
    
    if not waypoints:
        raise ValueError(f"Nessun waypoint trovato per {circuit_id}")
    
    if verbose:
        print(f"  Waypoints: {len(waypoints)}")
        print(f"  Lunghezza: {waypoints[-1]['dist_m']:.1f}m")
    
    # Inizializza aero
    aero = AeroAssembly()
    
    # Imposta setup aero se fornito
    if aero_setup is None:
        # Setup default (medio)
        aero_setup = {
            "front_wing": 20.0,
            "rear_wing": 22.0,
            "b_wing": 10.0,
        }
    
    aero.set_component_angles(aero_setup)
    
    # Stato iniziale
    # Usa la velocità del primo waypoint come baseline del flying lap,
    # così il benchmark parte dallo stesso stato dinamico della telemetria.
    initial_velocity_kph = float(waypoints[0].get('v_ref_kph', 180.0))
    initial_velocity_ms = max(1.0, initial_velocity_kph / 3.6)
    state = PhysicsState(
        distance_m=0.0,
        velocity_ms=initial_velocity_ms,
        acceleration_ms2=0.0,
        time_s=0.0,
    )
    
    # Integra su tutti i waypoints
    # Inizializza tracking settori
    if sector_boundaries:
        # Usa confini settori dalla telemetria (N settori)
        sector_times = [0.0] * len(sector_boundaries)
        boundaries = sector_boundaries
    else:
        # Default: 3 settori uguali
        sector_times = [0.0, 0.0, 0.0]
        boundaries = [
            waypoints[-1]['dist_m'] / 3,      # 1/3 giro
            waypoints[-1]['dist_m'] * 2 / 3,  # 2/3 giro
            waypoints[-1]['dist_m'],          # fine giro
        ]
    sector_idx = 0
    
    v_max_ms = 0.0
    v_min_ms = 999.0
    
    circuit_calibration = get_circuit_calibration(circuit_id)
    if circuit_calibration:
        if mu_override is None and circuit_calibration.get("mu_override") is not None:
            mu_override = circuit_calibration["mu_override"]
        if max_brake_decel_g_override is None and circuit_calibration.get("max_brake_decel_g") is not None:
            max_brake_decel_g_override = circuit_calibration["max_brake_decel_g"]
        if max_lateral_g_override is None and circuit_calibration.get("max_lateral_g") is not None:
            max_lateral_g_override = circuit_calibration["max_lateral_g"]
        section_speed_scales = circuit_calibration.get("section_speed_scales") or {}
    else:
        section_speed_scales = {}

    if aero_calibration is None:
        aero_calibration = get_aero_calibration(circuit_id)

    # V5.6: Carica la mescola SOFT dal Telemetry JSON.
    # La calibrazione mu_mechanical è fatta con la SOFT (telemetria qualifica).
    # La soft varia per circuito (C3 a Sakhir, C5 a Monza, C6 a Monaco).
    # Questo è il compound di riferimento per lo scaling tra mescole.
    calibration_compound = _load_soft_compound(circuit_id)
    if aero_calibration is not None:
        aero_calibration["calibration_compound"] = calibration_compound
    else:
        aero_calibration = {"calibration_compound": calibration_compound}

    # V5.0: Applica k_wing_coupling dalla calibrazione aero all'AeroAssembly.
    # Questo modifica il coupling ala-floor per riflettere la sensibilità
    # circuito-specifica del ground effect alle variazioni dell'angolo ala.
    if aero_calibration is not None:
        k_wing_coupling = aero_calibration.get("k_wing_coupling")
        if k_wing_coupling is not None:
            try:
                k_wing_coupling = float(k_wing_coupling)
                if k_wing_coupling > 0:
                    aero.set_k_wing_coupling(k_wing_coupling)
            except (TypeError, ValueError):
                pass

    # Applica override parametri per calibrazione
    mu_base_local = MU_BASE.copy()
    if mu_override:
        mu_base_local.update(mu_override)
    
    max_brake_decel_g_local = max_brake_decel_g_override if max_brake_decel_g_override else MAX_BRAKE_DECEL_G
    max_lateral_g_local = max_lateral_g_override if max_lateral_g_override else MAX_LATERAL_G
    
    if verbose:
        print("🚀 Integrazione...")
        if circuit_calibration:
            print(f"  Circuit calibration loaded: {circuit_id}")
        if aero_calibration:
            cda = aero_calibration.get("CdA")
            cla = aero_calibration.get("ClA")
            aero_message = "  Aero calibration loaded:"
            if isinstance(cda, (int, float)):
                aero_message += f" CdA={cda:.4f}"
            if isinstance(cla, (int, float)):
                aero_message += f" ClA={cla:.4f}"
            # V5.0: Stampa parametri calibrazione aero
            mu_mech = aero_calibration.get("mu_mechanical")
            k_wc = aero_calibration.get("k_wing_coupling")
            if mu_mech is not None:
                aero_message += f" mu_mech={float(mu_mech):.3f}"
            if k_wc is not None:
                aero_message += f" k_wing_coupling={float(k_wc):.4f}"
            print(aero_message)
        if mu_override:
            print(f"  MU override: {mu_override}")
        if max_brake_decel_g_override:
            print(f"  Brake override: {max_brake_decel_g_override}g")
        if max_lateral_g_override:
            print(f"  Lateral override: {max_lateral_g_override}g")
    
    # Pre-calcola effetti sospensioni (costanti per tutto il giro)
    # P4/P5: _compute_suspension_effects ora usa valori reali (N/mm, Nm/deg)
    # e restituisce anche ride_height_aero_factor e ride_height in metri.
    # Se suspension_setup contiene già i valori reali (da get_setup_dict),
    # li usa direttamente. Altrimenti converte da slider (backward compatibility).
    susp_effects = _compute_suspension_effects(suspension_setup)

    # V5.4.3: Boundary duplicate speed collapse fix is in integrate_waypoint().
    # At section boundaries (dist_step < 0.02m), v_max_corner clamp is skipped
    # because the duplicate carries the apex minimum radius of the incoming
    # section, not the actual radius at that track position.

    # V6.0: PRE-COMPUTE v_max_corner AND BRAKING ZONES (BEFORE MAIN LOOP)
    # ============================================================
    # Phase 1A: Calcola v_max_corner (velocità massima fisica per ogni waypoint)
    v_max_corner_array = []
    try:
        v_max_corner_array = compute_v_max_corners(
            waypoints=waypoints,
            aero=aero,
            mu_cal=aero_calibration.get("mu_mechanical", 1.55) if aero_calibration else 1.55,
            mass_kg=mass_kg,
            suspension_effects=susp_effects,
            n_iter=3,
        )
        if verbose:
            print(f"  ✓ V6.0 v_max_corner computed: {len(v_max_corner_array)} waypoints")
            print(f"    Min: {min(v_max_corner_array):.1f} m/s, Max: {max(v_max_corner_array):.1f} m/s, "
                  f"Avg: {sum(v_max_corner_array)/len(v_max_corner_array):.1f} m/s")
    except Exception as e:
        if verbose:
            print(f"  ⚠️ V6.0 v_max_corner failed: {e}, falling back to None")
        v_max_corner_array = None

    # Phase 1B (NUOVO): Applica safety factor circuit-specific
    if v_max_corner_array is not None:
        try:
            circuit_type = analyze_circuit_profile(waypoints)
            safety_factor = get_safety_factor_v6(circuit_type, circuit_id)
            v_max_corner_array = [v * safety_factor for v in v_max_corner_array]
            if verbose:
                print(f"  ✓ V6.0 safety factor applied: {circuit_type} → {safety_factor:.2f}")
                print(f"    After safety: Min: {min(v_max_corner_array):.1f} m/s, "
                      f"Max: {max(v_max_corner_array):.1f} m/s")
        except Exception as e:
            if verbose:
                print(f"  ⚠️ V6.0 safety factor failed: {e}")

    # Phase 1B: Identifica braking zones usando v_max_corner (PHYSICS-DRIVEN lookahead)
    brake_needed = []
    try:
        brake_needed = compute_braking_zones_v6(
            waypoints=waypoints,
            v_max_corner=v_max_corner_array if v_max_corner_array else [200/3.6] * len(waypoints),
            max_brake_decel_g=max_brake_decel_g_local,
        )
        brake_count = sum(brake_needed)
        if verbose:
            print(f"  ✓ V6.0 braking zones computed: {brake_count}/{len(brake_needed)} waypoints need braking "
                  f"({100*brake_count/len(brake_needed):.1f}%)")
    except Exception as e:
        if verbose:
            print(f"  ⚠️ V6.0 braking zones failed: {e}, falling back to None")
        brake_needed = None

    for i in range(len(waypoints) - 1):
        wp = waypoints[i]
        wp_next = waypoints[i + 1]
        # FIX V4.10: Distance-based section lookup instead of HD macro_sector_id.
        # HD section IDs can be misaligned with telemetry section boundaries
        # (e.g. Silverstone: HD sec_02 at 340m vs Tel sec_02 at 785m).
        current_section_id = _find_section_id_by_distance(reference_sections, wp.get('dist_m', 0.0))
        next_section_id = _find_section_id_by_distance(reference_sections, wp_next.get('dist_m', 0.0))
        section_guidance = reference_sections.get(current_section_id)
        section_exit_guidance = section_guidance if current_section_id and current_section_id != next_section_id else None
        section_entry_guidance = reference_sections.get(next_section_id) if current_section_id and current_section_id != next_section_id else None
        section_speed_scale = 1.0
        scale_key = next_section_id or current_section_id
        if isinstance(section_speed_scales, dict) and scale_key:
            try:
                section_speed_scale = float(section_speed_scales.get(scale_key, 1.0) or 1.0)
            except (TypeError, ValueError):
                section_speed_scale = 1.0
        
        # Integra step
        state = integrate_waypoint(
            state=state,
            waypoint=wp,
            next_waypoint=wp_next,
            aero=aero,
            setup=aero_setup,
            mass_kg=mass_kg,
            tyre_compound=tyre_compound,
            driver_skill=driver_skill,
            mu_base=mu_base_local,
            max_brake_decel_g=max_brake_decel_g_local,
            max_lateral_g=max_lateral_g_local,
            aero_calibration=aero_calibration,
            section_guidance=section_guidance,
            section_exit_guidance=section_exit_guidance,
            section_speed_scale=section_speed_scale,
            section_entry_guidance=section_entry_guidance,
            waypoints=waypoints,
            waypoint_idx=i,
            suspension_effects=susp_effects,
            ers_power_fraction=ers_power_fraction,
            reference_pull=reference_pull,
            reference_pull_strength=reference_pull_strength,
            pu_lookup_interpolator=pu_lookup_interpolator,
            pu_lookup_blend=pu_lookup_blend,
            pu_config=pu_config,
            pu_ctx=pu_ctx,
            # V6.0: Physics-driven corner model
            v_max_corner_array=v_max_corner_array,
            brake_needed=brake_needed,
        )
        
        # Aggiorna statistiche
        v_max_ms = max(v_max_ms, state.velocity_ms)
        v_min_ms = min(v_min_ms, state.velocity_ms)
        
        # Controlla settori
        if sector_idx < len(boundaries) and state.distance_m >= boundaries[sector_idx]:
            sector_times[sector_idx] = state.time_s
            sector_idx += 1
    
    # Tempo ultimo settore (se necessario)
    if sector_idx == len(boundaries):
        if len(boundaries) >= 3 and not sector_boundaries:
            # Default 3 settori: calcola terzo settore
            sector_times[2] = state.time_s - sum(sector_times[:2])
    
    # Risultati
    lap_time_s = state.time_s
    v_max_kph = v_max_ms * 3.6
    v_min_kph = v_min_ms * 3.6
    v_avg_kph = (waypoints[-1]['dist_m'] / lap_time_s) * 3.6
    
    if verbose:
        print(f"✅ Giro completato!")
        print(f"  Tempo: {lap_time_s:.3f}s")
        print(f"  Settori ({len(sector_times)}): {[f'{t:.3f}' for t in sector_times]}")
        print(f"  V_max: {v_max_kph:.1f} kph")
        print(f"  V_min: {v_min_kph:.1f} kph")
        print(f"  V_avg: {v_avg_kph:.1f} kph")
        if pu_ctx is not None:
            print(f"  ⚡ PU V5.4: deploy={pu_ctx.lap_deploy_mj:.3f} MJ, "
                  f"harvest={pu_ctx.lap_harvest_mj:.3f} MJ, "
                  f"mguh_direct={pu_ctx.lap_mguh_direct_mj:.3f} MJ, "
                  f"soc_end={pu_ctx.soc_mj:.3f} MJ ({pu_ctx.soc_mj/BATTERY_CAPACITY_MJ*100:.1f}%), "
                  f"ers_temp={pu_ctx.ers_temp_c:.1f}°C")
    
    result = {
        "lap_time_s": lap_time_s,
        "sector_times": sector_times,
        "v_max_kph": v_max_kph,
        "v_min_kph": v_min_kph,
        "v_avg_kph": v_avg_kph,
        "telemetry": state.telemetry_points,
        "waypoints_count": len(waypoints),
        "circuit_id": circuit_id,
        "aero_setup": aero_setup,
        "aero_calibration": aero_calibration,
    }
    
    # V5.4: Add PU stateful results
    if pu_ctx is not None:
        # Deployment zones summary
        zones_summary = []
        for z in pu_ctx.deployment_zones:
            zones_summary.append({
                "name": z.name,
                "type": z.zone_type,
                "start_m": round(z.start_m, 1),
                "end_m": round(z.end_m, 1),
                "allocated_mj": round(z.allocated_mj, 3),
                "remaining_mj": round(z.remaining_mj, 3),
                "target_power_kw": round(z.target_power_kw, 1),
            })

        result["pu_v54"] = {
            "engine_map": pu_ctx.engine_map,
            "lap_deploy_mj": round(pu_ctx.lap_deploy_mj, 4),
            "lap_harvest_mj": round(pu_ctx.lap_harvest_mj, 4),
            "lap_mguh_direct_mj": round(pu_ctx.lap_mguh_direct_mj, 4),
            "soc_end_mj": round(pu_ctx.soc_mj, 4),
            "soc_end_pct": round(pu_ctx.soc_mj / BATTERY_CAPACITY_MJ * 100, 1),
            "ers_temp_end_c": round(pu_ctx.ers_temp_c, 1),
            "deployment_zones": zones_summary,
            "energy_trace": pu_ctx.energy_trace,
        }
    
    return result
