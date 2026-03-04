"""
Car.update_section() – orchestrates Steps 1-8 of the physics loop.

This is the core function that computes the time a single car takes
to traverse one circuit section, updating all internal state.

Reference: docs/lap-physics-spec-v0.5.md §3.3 (Passi 1-8)
"""
from __future__ import annotations

from typing import List

from .aero_package import compute_forces
from .brake_system import update_brakes
from .data_types import (
    AeroForces,
    AeroSetup,
    CarState,
    CircuitConfig,
    CORNER_KINDS,
    CURVE_FACTOR,
    DriverIntent,
    DriverSkills,
    EnvContext,
    SectionContext,
    SectionEvent,
    SectionKind,
    SectionResult,
    WheelPosition,
    clamp,
)
from .driver_model import compute_inputs, update_mental_state
from .power_unit import generate_output
from .tyre_model import update_tyres


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_section(
    car_state: CarState,
    aero_setup: AeroSetup,
    driver_skills: DriverSkills,
    section: SectionContext,
    env: EnvContext,
    config: CircuitConfig,
    push_level: float = 1.0,
    airflow_penalty: float = 0.0,
    traffic_v_max_kph: float = 0.0,
    delta_aero: float = 0.0,
    delta_grip: float = 0.0,
    apply_baseline_delta: bool = True,
) -> SectionResult:
    """
    Compute the physics for one car traversing one section.

    Parameters
    ----------
    car_state : CarState       – mutable state (updated in-place)
    aero_setup : AeroSetup     – car's aero configuration
    driver_skills : DriverSkills – static driver ratings
    section : SectionContext    – current circuit section
    env : EnvContext            – environmental conditions
    config : CircuitConfig      – circuit + tuning parameters
    push_level : float          – player push command (0.8-1.1)
    airflow_penalty : float     – dirty air (0-1)
    traffic_v_max_kph : float   – speed constraint from car ahead (0 = none)
    """
    all_events: List[SectionEvent] = []

    # ===================================================================
    # STEP 1 – Input & initial state (Passo 1)
    # ===================================================================
    v_base = section.v_base_kph
    
    # CORREZIONE: Se la velocità corrente è maggiore della v_entry del settore,
    # significa che c'è una frenata nella transizione tra settori (waypoints HD).
    # Applichiamo questa frenata prima di iniziare la simulazione del settore.
    if section.v_entry_kph > 0 and car_state.v_current_ms * 3.6 > section.v_entry_kph:
        car_state.v_current_ms = section.v_entry_kph / 3.6
    
    v_entry_kph = car_state.v_current_ms * 3.6
    v_estimate = v_base  # initial speed estimate for calculations

    # ===================================================================
    # STEP 2 – Driver decision (Passo 2)
    # ===================================================================
    driver_intent = compute_inputs(
        skills=driver_skills,
        mental=car_state.driver_mental,
        section=section,
        env=env,
        car_state=car_state,
        config=config,
        push_level=push_level,
    )

    # ===================================================================
    # STEP 3 – Aero forces (Passo 3)
    # ===================================================================
    drs_active = section.drs_available and not car_state.side_by_side
    aero_forces = compute_forces(
        aero=aero_setup,
        section=section,
        env=env,
        car_state=car_state,
        config=config,
        v_kph=v_estimate,
        airflow_penalty=airflow_penalty,
        drs_active=drs_active,
    )
    
    # Store aero_forces in car_state for UI and telemetry
    car_state.aero_forces = aero_forces

    # ===================================================================
    # STEP 4 – Power Unit (Passo 4)
    # ===================================================================
    dt_estimate = section.length_m / max(v_estimate / 3.6, 1.0)

    car_state.pu, pu_events = generate_output(
        pu_state=car_state.pu,
        driver_intent=driver_intent,
        aero_forces=aero_forces,
        section=section,
        env=env,
        config=config,
        dt_estimate_s=dt_estimate,
    )
    all_events.extend(pu_events)

    # Update cooling margin now that PU demand is known
    pu_map = config.pu_maps.get(car_state.pu.active_map)
    if pu_map:
        cooling_demand = pu_map.heat_load_kw / 1000.0
        aero_forces.cooling_margin = aero_forces.cooling_capacity - cooling_demand

    total_power_kw = car_state.pu.ice_power_kw + car_state.pu.ers_output_kw

    # ===================================================================
    # STEP 5 – Tyres & Brakes (Passo 5)
    # ===================================================================
    eff_grip_front, eff_grip_rear, tyre_events = update_tyres(
        car_state=car_state,
        section=section,
        env=env,
        aero=aero_forces,
        driver=driver_intent,
        config=config,
        dt_s=dt_estimate,
        v_kph=v_estimate,
        aero_setup=aero_setup,
    )
    all_events.extend(tyre_events)

    braking_efficiency, brake_events, brake_snapshot = update_brakes(
        car_state=car_state,
        section=section,
        env=env,
        aero=aero_forces,
        driver=driver_intent,
        config=config,
        dt_s=dt_estimate,
        v_kph=v_estimate,
        driver_skills=driver_skills,
    )
    car_state.brakes.snapshot = brake_snapshot
    all_events.extend(brake_events)

    # ===================================================================
    # STEP 6 – Pure Kinematics Integration (Passo 6)
    # ===================================================================
    import math
    is_corner = section.kind in CORNER_KINDS
    
    # Costanti fisiche di conversione e taratura
    MASS_DRY = 798.0
    mass = MASS_DRY + car_state.pu.fuel_kg
    RHO = env.air_density_kg_m3
    
    # Coefficienti fisici reali F1 2025 (AeroSetup 8 componenti)
    # Calibrati su assetto neutro bilanciato FW=20°/RW=15°, condizioni qualifica reali:
    # gomme C5 quasi nuove (2% usura), temp ottimale 95°C, giro lanciato (v_entry=347kph)
    # Target F1 2025:
    # CDA_REF: Base drag (ruote/telaio) ~ 1.10 m2 + drag_eff scalato (0.015)
    # CLA_REF: Downforce totale scalato (0.020) per valori realistici 3-5 m²
    CDA_REF = 1.10 + aero_forces.drag_eff * 0.015
    CLA_REF = aero_forces.df_total * 0.020

    # Grip meccanico: F1 2025 mu_mech ~ 1.6 (gomme Pirelli C3 nuove)
    # Degradato esponenzialmente con l'usura per amplificare l'effetto
    grip_avg = (eff_grip_front + eff_grip_rear) / 2.0
    mu = 1.6 * (grip_avg ** 2.0) * (1.0 - aero_forces.handling_penalty)
    # Identificazione del carico ottimale del circuito (per R_eff e next_v_apex)
    cid = config.circuit_id
    if "monaco" in cid:
        df_opt = 230.0       # Alto carico (es. FW=80/RW=80)
    elif "suzuka" in cid:
        df_opt = 180.0       # Medio-alto (es. FW=55/RW=54)
    elif "silverstone" in cid:
        df_opt = 120.0       # Medio-basso (es. FW=30/RW=27)
    elif "monza" in cid:
        df_opt = 80.0        # Basso carico (es. FW=15/RW=11)
    else:
        # Interpolazione fallback basata sulla V_max del circuito
        if not hasattr(config, '_circuit_vmax'):
            config._circuit_vmax = max((s.v_max_kph for s in config.sections), default=300.0)
        vmax = clamp(config._circuit_vmax, 289.0, 348.0)
        df_opt = 230.0 - (vmax - 289.0) * ((230.0 - 80.0) / (348.0 - 289.0))
        
    cla_opt = df_opt * 0.040

    radius = section.curve_profile.radius_m if is_corner else None
    v_apex_limit = config.v_cap_kph / 3.6

    if is_corner and section.v_min_kph > 0:
        # CORREZIONE: usa raggio dal JSON se disponibile e valido
        if radius is None or radius <= 0:
            # Fallback: reverse-engineering del raggio da v_min (solo se il JSON non fornisce uno valido)
            v_min_ms = section.v_min_kph / 3.6
            mu_ideal = 1.6
            term1 = (mu_ideal * mass * 9.81) / (v_min_ms**2)
            term2 = 0.5 * mu_ideal * RHO * cla_opt
            radius = mass / (term1 + term2)
        
    mu_target = mu
    telemetry_mu = section.telemetry_mu if hasattr(section, 'telemetry_mu') else 0.0
    if telemetry_mu and telemetry_mu > 0:
        mu_target = min(mu_target, telemetry_mu)
    if radius and radius > 0 and section.v_min_kph > 0:
        v_min_ms = section.v_min_kph / 3.6
        telem_den = (mass * 9.81) / max(v_min_ms**2, 1e-4) + 0.5 * RHO * CLA_REF
        if telem_den > 0:
            mu_from_vmin = (mass / radius) / telem_den
            mu_target = min(mu_target, mu_from_vmin)
            mu_target = max(0.4, mu_target)

    if radius and radius > 0:
        # 2. V_apex fisica reale per l'auto corrente
        denominator = (mass / radius) - (0.5 * mu_target * RHO * CLA_REF)
        if denominator > 0:
            v_apex_limit = math.sqrt((mu_target * mass * 9.81) / denominator)
        else:
            v_apex_limit = config.v_cap_kph / 3.6
        v_apex_limit *= driver_intent.pace_factor


    # Se siamo in rettilineo, guardiamo se la PROSSIMA sezione è una curva per calcolare la staccata
    next_v_apex = config.v_cap_kph / 3.6
    next_idx = car_state.current_section_idx + 1
    if not is_corner and next_idx < len(config.sections):
        next_sec = config.sections[next_idx]
        if next_sec.kind in CORNER_KINDS and next_sec.v_min_kph > 0:
            # CORREZIONE: usa raggio dal JSON della sezione successiva se disponibile
            next_r = next_sec.curve_profile.radius_m
            if next_r is None or next_r <= 0:
                # Fallback: ricalcola da v_min
                v_min_next = next_sec.v_min_kph / 3.6
                term1 = (1.6 * mass * 9.81) / (v_min_next**2)
                term2 = 0.5 * 1.6 * RHO * cla_opt
                next_r = mass / (term1 + term2)
            
            denom = (mass / next_r) - (0.5 * mu * RHO * CLA_REF)
            if denom > 0:
                next_v_apex = math.sqrt((mu * mass * 9.81) / denom) * driver_intent.pace_factor
            else:
                next_v_apex = config.v_cap_kph / 3.6

    
    v_max_reached_ms = max(car_state.v_current_ms, 10.0)
    
    # ===================================================================
    # HD Micro-Sector Integration (if waypoints are available)
    # ===================================================================
    if hasattr(section, 'waypoints') and section.waypoints:
        v = max(car_state.v_current_ms, 10.0)
        t = 0.0
        v_max_reached_ms = v
        power_kw = total_power_kw
        if drs_active:
            CDA_REF *= 0.8
            
        waypoints = section.waypoints
        
        for i in range(len(waypoints) - 1):
            wp = waypoints[i]
            next_wp = waypoints[i+1]
            dist_step = next_wp.dist_m - wp.dist_m
            if dist_step <= 0:
                continue
                
            # --- Cornering Scrub ---
            # Calcolo drag indotto dallo sterzo (se girato)
            steering_drag_coeff = 0.0
            if hasattr(wp, 'steering_angle_deg') and abs(wp.steering_angle_deg) > 0.5:
                # 0.01 extra CDA per ogni grado di sterzo è una buona baseline per simulare lo scrub
                steering_drag_coeff = abs(wp.steering_angle_deg) * 0.01 
                
            # Forze aerodinamiche per questo step
            F_drag = 0.5 * RHO * (v**2) * (CDA_REF + steering_drag_coeff) + (mass * 9.81 * 0.015)
            F_df = 0.5 * RHO * (v**2) * CLA_REF
            F_z = mass * 9.81 + F_df
            
            # Grip meccanico per questo micro-settore
            F_lat_max = F_z * mu
            max_brake_force = F_z * mu * braking_efficiency
            
            # === ACCELERAZIONE DERIVATA DA V_REF ===
            # Invece di usare un modello di forze teoriche, calcoliamo l'accelerazione
            # necessaria per raggiungere esattamente la velocità indicata dalla telemetria
            # per il prossimo waypoint.
            v_target = next_wp.v_ref_kph / 3.6 if next_wp.v_ref_kph > 0 else v
            
            # Non applichiamo il pace_factor qui, la telemetria è il ground truth.
            # Il pace_factor verrà gestito a livello macro o penalizzando il tempo finale.
            
            # Calcolo cinematico dell'accelerazione: v² = v₀² + 2as  ->  a = (v² - v₀²) / 2s
            a = (v_target**2 - v**2) / (2 * max(dist_step, 0.1))
            
            # Traffico
            if traffic_v_max_kph > 0 and (v * 3.6) > traffic_v_max_kph:
                a = min(a, -F_drag/mass)
                
            # La nuova velocità è esattamente il target (limitato ai cap)
            v_new = v_target
            v_new = clamp(v_new, config.v_min_kph / 3.6, config.v_cap_kph / 3.6)
            
            # Avanzamento esatto allo step
            v_avg = (v + v_new) / 2.0
            actual_dt = dist_step / max(v_avg, 1.0)
            
            t += actual_dt
            v = v_new
            
            if v > v_max_reached_ms:
                v_max_reached_ms = v
                
        dt_s = max(t, 0.01)
        v_effective = (section.length_m / dt_s) * 3.6
        
        # Cap velocità di uscita sezione con ground truth telemetria (come nel loop macro)
        if section.v_exit_kph > 0:
            v_exit_cap = (section.v_exit_kph / 3.6) * (0.97 + 0.06 * driver_intent.pace_factor)
            
            # NELLE CURVE: moduliamo il cap in base a quanto l'auto è aerodinamicamente
            # superiore/inferiore rispetto all'auto telemetrica (che aveva cla_opt)
            if section.kind in CORNER_KINDS and section.v_min_kph > 0:
                speed_ratio = v_apex_limit / (section.v_min_kph / 3.6)
                speed_ratio = clamp(speed_ratio, 0.85, 1.15)
                v_exit_cap *= speed_ratio
                
            if v > v_exit_cap:
                v = v_exit_cap
        
        # Sostituiamo il while loop macro standard

    else:
    # Variabili di integrazione
        v = max(car_state.v_current_ms, 10.0) # non fermarsi mai completamente
        d = 0.0
        t = 0.0
        dt_step = 0.05 # 50ms per frame
    
        # Eventi (es. DR, clipping) - qui possiamo aggiungere penalty sul momento
        power_kw = total_power_kw
        if drs_active:
            CDA_REF *= 0.8 # -20% drag con DRS aperto
    
        while d < section.length_m:
            # Forze Aerodinamiche
            F_drag = 0.5 * RHO * (v**2) * CDA_REF + (mass * 9.81 * 0.015) # Aerodynamic drag + Rolling resistance based on weight
            F_df = 0.5 * RHO * (v**2) * CLA_REF
            
            # Carico verticale e limite di grip (per trazione e frenata)
            F_z = mass * 9.81 + F_df
            F_lat_max = F_z * mu
            max_brake_force = F_z * mu * braking_efficiency
            
            current_radius = radius
            if is_corner and d >= section.length_m * 0.5:
                current_radius = None  # Il pilota riallinea lo sterzo in uscita, grip laterale scende a 0
                
            # Forza Motrice (limitata dalla potenza e dal grip)
            F_drive_max_power = (power_kw * 1000.0) / max(v, 1.0)
            # Se in curva, il grip è condiviso con la forza laterale (Circle of Traction approssimato)
            # Usiamo un approccio semplificato:
            F_drive_max_grip = F_z * mu
            if is_corner and current_radius and current_radius > 0:
                F_lat_req = mass * (v**2) / current_radius
                if F_lat_req < F_lat_max:
                    F_drive_max_grip = math.sqrt(max(0.0, F_lat_max**2 - F_lat_req**2))
                else:
                    F_drive_max_grip = 0.0 # Perde aderenza, deve rallentare
                    
            F_drive = min(F_drive_max_power, F_drive_max_grip)
            
            # Frenata: Controllo Look-ahead
            dist_remaining = section.length_m - d
            F_net = F_drive - F_drag
            
            # Devo frenare per l'apex successivo?
            braking = False
            if not is_corner and next_v_apex < v:
                # Calcolo spazio di frenata necessario da 'v' a 'next_v_apex'
                # Decelerazione attesa a_brake = (F_brake + F_drag) / mass
                # Usiamo un F_drag stimato conservativo
                a_brake = (max_brake_force + F_drag) / mass
                d_brake_req = (v**2 - next_v_apex**2) / (2 * max(a_brake, 1.0))
                
                if dist_remaining <= d_brake_req:
                    braking = True
    
            # Frenata per l'apice: prima metà della curva
            if is_corner and d < section.length_m * 0.5 and v > v_apex_limit:
                braking = True
    
            if braking:
                F_net = -max_brake_force - F_drag
    
            # Traffico
            if traffic_v_max_kph > 0 and (v * 3.6) > traffic_v_max_kph:
                F_net = min(F_net, -F_drag) # Rilascia il gas o frena leggermente
    
            # Aggiornamento cinematico
            a = F_net / mass
            v_new = v + a * dt_step
            
            # Cap a V_MIN e V_MAX
            v_new = clamp(v_new, config.v_min_kph / 3.6, config.v_cap_kph / 3.6)
            
            # Avanzamento
            v_avg = (v + v_new) / 2.0
            d_step = v_avg * dt_step
            
            if d + d_step > section.length_m:
                # Ultimo step parziale
                fraction = (section.length_m - d) / max(d_step, 0.001)
                t += dt_step * fraction
                v = v + a * (dt_step * fraction)
                d = section.length_m
                break
                
            d += d_step
            t += dt_step
            v = v_new
    
        dt_s = t
        v_effective = (section.length_m / max(dt_s, 0.01)) * 3.6
    
        # Cap velocità di uscita sezione con ground truth telemetria.
        if section.v_exit_kph > 0:
            # Il cap base è la telemetria (scalata per aggressività)
            v_exit_cap = (section.v_exit_kph / 3.6) * (0.97 + 0.06 * driver_intent.pace_factor)
            
            # NELLE CURVE: moduliamo il cap in base a quanto l'auto è aerodinamicamente
            # superiore/inferiore rispetto all'auto telemetrica (che aveva cla_opt).
            # Se ho più DF, la mia v_apex_limit calcolata fisicamente su R_eff sarà
            # maggiore della v_min_kph telemetrica -> speed_ratio > 1.0 -> esco più veloce!
            if is_corner and section.v_min_kph > 0:
                speed_ratio = v_apex_limit / (section.v_min_kph / 3.6)
                # Limitiamo il boost/nerf estremo (es. max ±15%)
                speed_ratio = clamp(speed_ratio, 0.85, 1.15)
                v_exit_cap *= speed_ratio
                
            if v > v_exit_cap:
                v = v_exit_cap
    
        
    # ------------------------------------------------------------------
    # Apply dt_ref penalty model (baseline + aero/grip deltas)
    # ------------------------------------------------------------------
    ref_dt = section.dt_ref_s if (hasattr(section, 'dt_ref_s') and section.dt_ref_s > 0.0) else dt_s
    # Fuel penalty (per lap) scaled by current fuel mass
    # Convert per-lap penalty to per-section penalty
    fuel_delta_s = 0.0
    if config.fuel_penalty_coeff > 0.0:
        extra_fuel = max(0.0, car_state.pu.fuel_kg - config.fuel_reference_kg)
        # Scale penalty by section length relative to total lap
        section_fraction = section.length_m / config.circuit_length_m
        fuel_delta_s = config.fuel_penalty_coeff * extra_fuel * section_fraction

    # Tyre penalty (compound + wear + temperature)
    tyre_delta_s = 0.0
    
    # Define curve kinds
    CURVE_KINDS = {
        SectionKind.VERY_SLOW_CORNER, 
        SectionKind.SLOW_CORNER, 
        SectionKind.MEDIUM_CORNER, 
        SectionKind.FAST_CORNER, 
        SectionKind.ULTRA_FAST_CORNER
    }

    if config.tyre_compound_deltas and config.tyre_reference_compound:
        # Get current tyre compound string (e.g. "C3")
        # Ensure we handle both Enum and string types robustly
        raw_compound = car_state.tyres[WheelPosition.LF].compound
        current_compound = raw_compound.value if hasattr(raw_compound, "value") else str(raw_compound)
        
        # APPLY PENALTIES ONLY ON CURVES
        if section.kind in CURVE_KINDS:
            # 1. Compound penalty
            # Distribute per-lap delta across total number of curve sections
            n_curves = max(1, config.n_curve_sections)
            compound_penalty = config.tyre_compound_deltas.get(current_compound, 0.0)
            compound_delta_section = compound_penalty / n_curves
            
            # 2. Wear penalty
            wear_coeff = config.tyre_wear_coeffs.get(current_compound, 0.12)
            total_wear = sum(tyre.wear_pct for tyre in car_state.tyres.values()) / 4.0
            
            # Scale to meaningful time penalties (approx 0.05s - 0.15s per 10% wear)
            wear_multiplier = 0.05
            
            if total_wear <= 50.0:
                wear_penalty = wear_coeff * wear_multiplier * (total_wear / 10.0)
            else:
                base_penalty = wear_coeff * wear_multiplier * 5.0  # Penalty at 50%
                excess_wear = total_wear - 50.0
                wear_penalty = base_penalty + wear_coeff * wear_multiplier * (excess_wear / 10.0) * 4.0
            
            # 3. Temperature penalty
            temp_penalty = 0.0
            tyre_temp_windows = config.tyre_temp_windows.get(current_compound, {})
            if tyre_temp_windows:
                surface_temp = car_state.tyres[WheelPosition.LF].surface_temp_c
                optimal_range = tyre_temp_windows.get("surface", [80, 100, 120])
                
                if surface_temp < optimal_range[0]:
                    temp_penalty = (optimal_range[0] - surface_temp) * 0.0005
                elif surface_temp > optimal_range[2]:
                    temp_penalty = (surface_temp - optimal_range[2]) * 0.001
            
            # Total tyre penalty for this curve section
            tyre_delta_s = compound_delta_section + wear_penalty + temp_penalty
        else:
            # Straight section: no tyre penalty applied (physical model assumption)
            tyre_delta_s = 0.0


    delta_penalty = clamp(
        config.k_aero_penalty * delta_aero + config.k_grip_penalty * delta_grip,
        -0.05,
        0.30,
    )
    baseline = config.baseline_delta if apply_baseline_delta else 0.0
    total_penalty = baseline + delta_penalty
    dt_s = max(dt_s + ref_dt * total_penalty + fuel_delta_s + tyre_delta_s, 0.01)
    v_effective = (section.length_m / dt_s) * 3.6

    car_state.v_current_ms = v

    # ===================================================================    # ===================================================================
    # STEP 7 – Internal state update (Passo 7)
    # ===================================================================
    # Fuel already updated in PU step
    # ERS already updated in PU step
    # Tyres already updated in tyre step
    # Brakes already updated in brake step

    # Driver mental state
    expected_dt = section.length_m / max(v_base / 3.6, 1.0)
    section_performance = dt_s / max(expected_dt, 0.01)
    events_severity = sum(e.severity for e in all_events)

    update_mental_state(
        mental=car_state.driver_mental,
        skills=driver_skills,
        section_performance=section_performance,
        events_severity=events_severity,
    )

    # Lap tracking
    car_state.lap_time_acc_s += dt_s
    car_state.section_progress = 1.0  # completed this section

    # Battle cooldowns
    if car_state.attack_cooldown > 0:
        car_state.attack_cooldown -= 1
    if car_state.defense_reset > 0:
        car_state.defense_reset -= 1

    # --- Overtake window (§6.10) ---
    # Base opportunity from section type (straights = easy, slow corners = possible, fast corners = hard)
    _OW_SECTION_BASE = {
        SectionKind.STRAIGHT: 0.6,
        SectionKind.MEDIUM_STRAIGHT: 0.4,
        SectionKind.VERY_SLOW_CORNER: 0.15,
        SectionKind.SLOW_CORNER: 0.10,
        SectionKind.MEDIUM_CORNER: 0.05,
        SectionKind.FAST_CORNER: 0.02,
        SectionKind.ULTRA_FAST_CORNER: 0.01,
    }
    ow_base = _OW_SECTION_BASE.get(section.kind, 0.1)

    # DRS bonus
    ow_drs = 0.15 if (section.drs_available and not car_state.side_by_side) else 0.0

    # Driver overtaking skill (0-100 → 0.0-0.15 bonus)
    ow_driver = driver_skills.overtaking_skill / 100.0 * 0.15

    # Tyre grip advantage (better grip = more overtake potential)
    grip_avg = (eff_grip_front + eff_grip_rear) / 2.0
    ow_grip = clamp((grip_avg - 0.85) * 0.5, -0.1, 0.1)

    # Braking zone bonus (late braking = overtake opportunity)
    ow_brake = 0.0
    if section.braking_energy_mj > 0.5:
        ow_brake = 0.1 * braking_efficiency  # better brakes = more chance

    # Aggression bonus
    ow_aggression = driver_intent.aggression_curve_bonus * 0.05

    car_state.overtake_window = clamp(
        ow_base + ow_drs + ow_driver + ow_grip + ow_brake + ow_aggression,
        0.0, 1.0,
    )

    # ===================================================================
    # STEP 8 – Return (Passo 8)
    # ===================================================================
    late_brake = any(e.event_type == "late_brake_success" for e in all_events)

    return SectionResult(
        dt_s=dt_s,
        v_exit_kph=car_state.v_current_ms * 3.6,
        v_entry_kph=v_entry_kph,
        v_effective_kph=v_effective,
        v_max_kph=v_max_reached_ms * 3.6,
        events=all_events,
        overtake_window=car_state.overtake_window,
        section_progress=1.0,
        braking_efficiency=braking_efficiency,
        late_brake_tag=late_brake,
        df_available=aero_forces.df_total,
        drag_eff=aero_forces.drag_eff,
        power_kw=total_power_kw,
        effective_grip_front=eff_grip_front,
        effective_grip_rear=eff_grip_rear,
        handling_penalty=aero_forces.handling_penalty,
        fuel_penalty_s=fuel_delta_s,
        tyre_penalty_s=tyre_delta_s,
    )
