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
    GRIP_CORNERING_EFFICIENCY,
)

from aero.aero_assembly import AeroAssembly, AeroForces


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
) -> PhysicsState:
    """
    Integra fisica per un singolo waypoint.
    
    Args:
      state: stato fisico corrente
      waypoint: waypoint corrente
      next_waypoint: waypoint successivo (per calcolo dt)
      aero: assembler aerodinamico
      setup: configurazione ali/sospensioni
      mass_kg: massa totale auto
      tyre_compound: mescola gomme
      driver_skill: fattore pilota (0.9-1.1)
    
    Returns:
      Nuovo stato fisico aggiornato
    """
    
    # Distanza tra waypoint (tipicamente 5m)
    dist_step = next_waypoint['dist_m'] - waypoint['dist_m']
    if dist_step <= 0:
        dist_step = 5.0  # fallback
    
    # Estrai dati waypoint
    radius_m = waypoint.get('radius_m', 999999.0)
    slope_deg = waypoint.get('slope_deg', 0.0)
    v_ref_kph = waypoint.get('v_ref_kph', 200.0)
    throttle_pct = waypoint.get('throttle_pct', 0)
    brake_pct = waypoint.get('brake_pct', 0)
    
    # Se radius > 1000m, è un rettilineo
    is_corner = radius_m < 1000.0
    
    # Calcola forze aerodinamiche (senza setup, usa valori correnti)
    aero_forces = aero.compute_forces(
        speed_ms=state.velocity_ms,
        drs_active=waypoint.get('drs_active', False)
    )
    
    # 1. Forza motrice (da potenza PU)
    if throttle_pct > 0:
        # Potenza disponibile
        p_available = PU_TOTAL_PEAK_KW * 1000 * (throttle_pct / 100.0)
        p_available *= DRIVETRAIN_EFFICIENCY
        p_available *= driver_skill
        
        # Forza = Potenza / Velocità
        if state.velocity_ms > 1.0:
            state.f_engine = p_available / state.velocity_ms
        else:
            state.f_engine = p_available / 1.0  # evita divisione per zero
        
        state.is_throttle = True
    else:
        state.f_engine = 0.0
        state.is_throttle = False
    
    # 2. Forza drag (aerodinamica + rolling)
    state.f_drag = aero_forces.f_drag
    f_rolling = ROLLING_RESISTANCE_COEFF * mass_kg * G
    state.f_drag += f_rolling
    
    # 3. Forza gravità (pendenza)
    slope_rad = math.radians(slope_deg)
    state.f_gravity = mass_kg * G * math.sin(slope_rad)
    
    # 4. Grip limite in curva
    mu = MU_BASE.get(tyre_compound, 1.65) * GRIP_CORNERING_EFFICIENCY
    mu *= driver_skill  # pilota migliore → più grip
    
    if is_corner:
        v_max_corner = compute_grip_limit(
            velocity_ms=state.velocity_ms,
            radius_m=radius_m,
            mass_kg=mass_kg,
            cla=aero_forces.cla_total,
            mu=mu
        )
    else:
        v_max_corner = 999.0  # nessun limite in rettilineo
    
    # 5. Decisione: accelerare o frenare?
    v_target = v_ref_kph / 3.6  # converte a m/s
    
    # Se siamo sopra il limite curva o il waypoint dice di frenare
    if state.velocity_ms > v_max_corner * 1.05 or brake_pct > 0:
        # Frenata
        state.is_braking = True
        f_brake = mass_kg * MAX_BRAKE_DECEL_G * G * (brake_pct / 100.0)
        state.f_engine = -f_brake  # negativo = frenante
    else:
        state.is_braking = False
    
    # 6. Accelerazione netta (F = m × a → a = F / m)
    f_net = state.f_engine - state.f_drag - state.f_gravity
    state.acceleration_ms2 = f_net / mass_kg
    
    # Limita accelerazione laterale in curva
    if is_corner:
        a_lat = state.velocity_ms ** 2 / radius_m
        a_lat_g = a_lat / G
        
        if a_lat_g > MAX_LATERAL_G:
            # Troppa accelerazione laterale: riduci velocità
            v_max_safe = math.sqrt(MAX_LATERAL_G * G * radius_m)
            state.acceleration_ms2 = min(state.acceleration_ms2, 0.0)
            v_target = min(v_target, v_max_safe)
    
    # 7. Integra cinematica
    # v_new² = v_old² + 2 × a × d
    v_squared_new = state.velocity_ms ** 2 + 2 * state.acceleration_ms2 * dist_step
    v_squared_new = max(0.0, v_squared_new)  # evita sqrt negativo
    
    v_new = math.sqrt(v_squared_new)
    
    # Clampa a limiti fisici
    v_new = min(v_new, v_max_corner)
    v_new = max(v_new, 5.0)  # minimo 18 km/h
    
    # Tempo per percorrere questo step
    v_avg = (state.velocity_ms + v_new) / 2.0
    if v_avg > 1.0:
        dt = dist_step / v_avg
    else:
        dt = dist_step / 1.0
    
    # Aggiorna stato
    new_state = PhysicsState(
        distance_m=state.distance_m + dist_step,
        velocity_ms=v_new,
        acceleration_ms2=state.acceleration_ms2,
        time_s=state.time_s + dt,
        f_engine=state.f_engine,
        f_drag=state.f_drag,
        f_downforce=aero_forces.f_downforce,
        f_gravity=state.f_gravity,
        f_centripetal=mass_kg * v_new ** 2 / radius_m if is_corner else 0.0,
        is_braking=state.is_braking,
        is_throttle=state.is_throttle,
        is_drs_active=waypoint.get('drs_active', False),
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
    
    Returns:
      Dizionario con:
        - lap_time_s: tempo giro [s]
        - sector_times: [s1, s2, s3]
        - v_max_kph: velocità massima
        - v_min_kph: velocità minima
        - v_avg_kph: velocità media
        - telemetry: lista punti telemetria
    """
    
    # Carica waypoints
    if verbose:
        print(f"🏁 Caricamento {circuit_id}...")
    
    waypoints = load_hd_waypoints(circuit_id)
    
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
    state = PhysicsState(
        distance_m=0.0,
        velocity_ms=50.0,  # 180 km/h partenza (uscita box)
        acceleration_ms2=0.0,
        time_s=0.0,
    )
    
    # Integra su tutti i waypoints
    sector_times = [0.0, 0.0, 0.0]
    sector_boundaries = [
        waypoints[-1]['dist_m'] / 3,      # 1/3 giro
        waypoints[-1]['dist_m'] * 2 / 3,  # 2/3 giro
        waypoints[-1]['dist_m'],          # fine giro
    ]
    sector_idx = 0
    
    v_max_ms = 0.0
    v_min_ms = 999.0
    
    if verbose:
        print("🚀 Integrazione...")
    
    for i in range(len(waypoints) - 1):
        wp = waypoints[i]
        wp_next = waypoints[i + 1]
        
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
        )
        
        # Aggiorna statistiche
        v_max_ms = max(v_max_ms, state.velocity_ms)
        v_min_ms = min(v_min_ms, state.velocity_ms)
        
        # Controlla settori
        if sector_idx < 3 and state.distance_m >= sector_boundaries[sector_idx]:
            sector_times[sector_idx] = state.time_s
            sector_idx += 1
    
    # Tempo ultimo settore
    if sector_idx == 3:
        sector_times[2] = state.time_s - sum(sector_times[:2])
    
    # Risultati
    lap_time_s = state.time_s
    v_max_kph = v_max_ms * 3.6
    v_min_kph = v_min_ms * 3.6
    v_avg_kph = (waypoints[-1]['dist_m'] / lap_time_s) * 3.6 / 1000.0
    
    if verbose:
        print(f"✅ Giro completato!")
        print(f"  Tempo: {lap_time_s:.3f}s")
        print(f"  Settori: {[f'{t:.3f}' for t in sector_times]}")
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
    }
