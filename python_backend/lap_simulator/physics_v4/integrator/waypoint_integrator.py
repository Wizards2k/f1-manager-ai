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
    """
    from pathlib import Path
    import json
    
    circuits_dir = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025")
    hd_file = circuits_dir / f"{circuit_id}_HD.json"
    
    if not hd_file.exists():
        raise FileNotFoundError(f"HD file non trovato: {hd_file}")
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get("waypoints", [])


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


def _apply_aero_calibration(aero_forces: AeroForces, aero_calibration: Optional[Dict[str, Any]]) -> AeroForces:
    """Applica un profilo aero calibrato ai coefficienti calcolati dal modello fisico."""
    if not aero_calibration:
        return aero_forces

    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    drag_scale = _as_float(aero_calibration.get("drag_index"), 1.0)
    downforce_scale = _as_float(aero_calibration.get("downforce_index"), 1.0)
    balance_target = aero_calibration.get("aero_balance_target")

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
        dist_step = 0.1
    
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
                blend_weight = 0.60 if section_kind == 'VerySlowCorner' else 0.45
                radius_m = (max(radius_m, 1.0) ** (1.0 - blend_weight)) * (max(section_radius_m, 1.0) ** blend_weight)
            except (TypeError, ValueError):
                pass
    # Se radius > 1000m, è un rettilineo
    is_corner = radius_m < 1000.0
    
    # Calcola forze aerodinamiche
    aero_forces = aero.compute_forces(
        speed_ms=state.velocity_ms,
        drs_active=drs_active
    )
    aero_forces = _apply_aero_calibration(aero_forces, aero_calibration)
    
    # ============================================================
    # 1. POTENZA MOTORE - Modello realistico
    # ============================================================
    # La potenza non è costante: dipende da marcia e velocità
    # In F1, la potenza massima è disponibile solo in marce alte
    # e a RPM elevati
    
    # Fattore marcia (semplificato): potenza massima in rettilineo,
    # ridotta in curva per evitare wheel spin
    if is_corner:
        # In curva: potenza ridotta per trazione
        # Più curva stretta = meno potenza disponibile
        corner_factor = min(1.0, 1000.0 / max(radius_m, 100.0))
        power_available = PU_TOTAL_PEAK_KW * 1000 * (throttle_pct / 100.0) * corner_factor
    else:
        # In rettilineo: potenza massima
        power_available = PU_TOTAL_PEAK_KW * 1000 * (throttle_pct / 100.0)
    
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
        max_traction_force = mu_base.get(tyre_compound, 1.65) * mass_kg * G * 0.6  # 60% grip posteriore
        f_engine = min(f_engine, max_traction_force)
    
    state.f_engine = f_engine
    state.is_throttle = throttle_pct > 0
    
    # ============================================================
    # 2. FORZA DRAG - Aerodinamica + Rolling
    # ============================================================
    state.f_drag = aero_forces.f_drag
    f_rolling = ROLLING_RESISTANCE_COEFF * mass_kg * G
    state.f_drag += f_rolling
    
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
    # track_grip_factor è fisso per circuito:
    #   Monza = 1.00, Monaco = 0.90, Suzuka = 1.05
    
    # Grip base dal compound (senza penalità empiriche)
    mu_base_val = mu_base.get(tyre_compound, 1.65)
    
    # Applica track_grip_factor da telemetry_mu (ora è fisso per circuito)
    track_grip_factor = waypoint.get('telemetry_mu', 1.0)
    if track_grip_factor is not None and track_grip_factor > 0:
        mu_base_val *= track_grip_factor
    
    # Applica driver skill (pilota migliore → sfrutta meglio il grip)
    mu_base_val *= driver_skill
    
    # Calcola downforce (contata UNA SOLA VOLTA qui)
    dynamic_pressure = 0.5 * RHO_SEA_LEVEL * state.velocity_ms ** 2
    f_downforce = dynamic_pressure * aero_forces.cla_total
    
    # Carico verticale totale = peso + downforce
    f_vertical = mass_kg * G + f_downforce  # N
    f_vertical_kn = f_vertical / 1000.0  # kN
    
    # Load sensitivity lineare: Grip = Mu * Fz * (1 - K * Fz)
    # K = 0.005 per F1 2025 (riduzione ~20% grip a 300 km/h)
    load_factor = 1.0 - (TYRE_LOAD_SENSITIVITY_K * f_vertical_kn)
    load_factor = max(0.5, min(1.0, load_factor))  # Clamp tra 0.5 e 1.0
    
    # Grip totale = mu_base * Fz * load_factor
    f_grip_total = mu_base_val * f_vertical * load_factor
    
    # Load transfer in frenata/accelerazione
    if state.is_braking:
        # Frenata: load transfer anteriore → grip posteriore ridotto
        load_transfer_factor = 0.85  # -15% grip posteriore
    elif state.is_throttle:
        # Accelerazione: load transfer posteriore → grip posteriore aumentato
        load_transfer_factor = 1.05  # +5% grip posteriore
    else:
        load_transfer_factor = 1.0  # Nessun load transfer
    
    f_grip_total *= load_transfer_factor
    
    # ============================================================
    # 5. VELOCITÀ MASSIMA IN CURVA - Solo dalla fisica (grip limit)
    # ============================================================
    # La velocità deve emergere dalla fisica, non dalla telemetria
    # v_ref serve solo come riferimento per il driver model
    
    if is_corner:
        # v_max corner: dove F_centripeta = F_grip
        # m × v² / R = F_grip
        # v_max = sqrt(F_grip × R / m)
        v_max_corner_ms = math.sqrt(f_grip_total * radius_m / mass_kg)
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
    
    v_target_ms = v_ref_kph / 3.6
    if section_speed_scale > 0.0:
        v_target_ms *= section_speed_scale
    
    # Trova il punto più lento della prossima curva (minimo v_ref nei prossimi waypoint)
    min_corner_v_ms = v_target_ms
    min_corner_dist_m = waypoint.get('dist_m', 0.0)
    
    if waypoints is not None:
        # Dynamic lookahead: at least 150m, up to ~300m at top speed (velocità in m/s * 3.5s)
        lookahead_distance_max = max(150.0, state.velocity_ms * 3.5)
        base_dist = waypoint.get('dist_m', 0.0)
        
        # Calcola decelerazione massima permessa dai freni (fisica)
        max_brake_decel_phys = f_grip_total / mass_kg
        max_brake_decel = min(max_brake_decel_g * G, max_brake_decel_phys)  # m/s²
        
        v_current = state.velocity_ms
        must_brake = False
        target_brake_v = v_current
        
        # Lookahead: search until we reach max distance or end of array
        for i in range(waypoint_idx + 1, len(waypoints)):
            wp = waypoints[i]
            wp_dist = wp.get('dist_m', 0.0)
            
            if wp_dist - base_dist > lookahead_distance_max:
                break
                
            wp_v_ref = wp.get('v_ref_kph', 200.0) / 3.6
            
            # Quanta distanza serve per rallentare da v_current a wp_v_ref?
            if v_current > wp_v_ref + 1.0:
                braking_dist_req = ((v_current ** 2) - (wp_v_ref ** 2)) / (2 * max_brake_decel)
                braking_dist_req *= 1.02  # Margine minimo stabilità numerica
                
                dist_to_wp = wp_dist - base_dist
                if dist_to_wp <= braking_dist_req:
                    must_brake = True
                    target_brake_v = min(target_brake_v, wp_v_ref)
                    break
                    
        if must_brake:
            state.is_braking = True
            # Forza di frenata target (include compensazione drag per decelerazione lineare)
            f_target_decel = mass_kg * max_brake_decel
            state.f_engine = -f_target_decel + state.f_drag + state.f_gravity
            # Limita alla potenza frenante massima
            state.f_engine = max(state.f_engine, -f_grip_total)
        else:
            state.is_braking = False
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
    # 9. INTEGRA CINEMATICA - FISICA PURA (NO REFERENCE_PULL)
    # ============================================================
    # v_new² = v_old² + 2 × a × d
    v_squared_new = state.velocity_ms ** 2 + 2 * state.acceleration_ms2 * dist_step
    v_squared_new = max(0.0, v_squared_new)  # Evita sqrt negativo
    
    v_new_ms = math.sqrt(v_squared_new)
    # RIMOSSO reference_pull: la fisica deve emergere dai parametri fisici, non da guide empiriche
    # v_new_ms = (v_new_ms * (1.0 - reference_pull)) + (v_target_ms * reference_pull)
    
    # Limita la velocità al grip fisico disponibile (v_max_corner_ms)
    v_new_ms = min(v_new_ms, v_max_corner_ms)
    
    # RIMOSSI section_exit_guidance e section_entry_guidance: sono guide empiriche che "inquinano" la fisica
    # La velocità deve essere determinata solo da: grip, aero, PU, driver skill
    
    # Clampa a limiti fisici
    v_new_ms = min(v_new_ms, v_max_corner_ms)
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
    # Sector tracking (per confronto con telemetria)
    sector_boundaries: Optional[List[float]] = None,
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
            print(aero_message)
        if mu_override:
            print(f"  MU override: {mu_override}")
        if max_brake_decel_g_override:
            print(f"  Brake override: {max_brake_decel_g_override}g")
        if max_lateral_g_override:
            print(f"  Lateral override: {max_lateral_g_override}g")
    
    for i in range(len(waypoints) - 1):
        wp = waypoints[i]
        wp_next = waypoints[i + 1]
        current_section_id = str(wp.get('macro_sector_id') or wp.get('section_id') or '')
        next_section_id = str(wp_next.get('macro_sector_id') or wp_next.get('section_id') or '')
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
    
    return {
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
