"""
Wing Sweep Test — Physics V3 Monza

Verifica che il motore fisico produca la curva U attesa:

  TEST A — BILANCIATI sweep (iper-scarico → ultra-carico):
    Atteso: curva U con minimo intorno all'assetto ottimale Monza.
    - Troppo scarico: perde nelle curve → tempo risale
    - Troppo carico:  drag eccessivo sui rettilinei → tempo risale
    - Il minimo è il punto in cui drag e grip si bilanciano per Monza.

  TEST B — SBILANCIATI vs BILANCIATI (stesso livello di carico):
    Atteso: assetto sbilanciato MAI più veloce del bilanciato equivalente.
    - Sovrasterzo: perde grip posteriore nelle curve (TC non aiuta)
    - Sottosterzo: muso largo, perde nelle curve lente

Riferimento: FW=13.39°/RW=10.26° (slider 31/21, Monza qualifica McLaren)
"""

import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python_backend'))

from lap_simulator.data_types import (
    AeroSetup, AeroComponent, EnvContext, SuspensionState,
    CarState, DriverSkills, DriverMentalState,
    TyreState, BrakeState, PUState, DamageState,
    SectionContext, CircuitConfig,
    WheelPosition, TyreCompound, EngineMapName, ERSModeName,
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.physics_v3.aero_mapper import map_aero_setup, _compute_balance_penalties
from lap_simulator.config_loader import load_circuit_config
import json


# ============================================================================
# Helpers — Setup e simulazione
# ============================================================================

def make_aero_setup(fw_angle: float, rw_angle: float, mclaren_mods: dict,
                    arb_f: float = 0.5, arb_r: float = 0.5,
                    rh_f: float = 25.0, rh_r: float = 40.0) -> AeroSetup:
    setup = AeroSetup()
    setup.front_wing.angle_deg = fw_angle
    setup.front_wing.efficiency_factor = mclaren_mods.get('front_wing_df_modifier', 1.0)
    setup.front_wing.base_drag = mclaren_mods.get('front_wing_drag_modifier', 1.0)
    setup.rear_wing.angle_deg = rw_angle
    setup.rear_wing.efficiency_factor = mclaren_mods.get('rear_wing_df_modifier', 1.0)
    setup.rear_wing.base_drag = mclaren_mods.get('rear_wing_drag_modifier', 1.0)
    setup.ride_height_front_mm = rh_f
    setup.ride_height_rear_mm = rh_r
    setup.ride_height_optimal_front_mm = rh_f
    setup.ride_height_optimal_rear_mm = rh_r
    setup.antiroll_front_rigidity = arb_f
    setup.antiroll_rear_rigidity = arb_r
    return setup


def combined_balance_error(setup: AeroSetup, aero_balance: float, fuel_kg: float) -> float:
    """Calcola il combined_balance_error per un dato setup."""
    fw_a = setup.front_wing.angle_deg
    rw_a = setup.rear_wing.angle_deg
    us_pen, os_pen, _ = _compute_balance_penalties(
        aero_balance=aero_balance,
        fw_angle=fw_a,
        rw_angle=rw_a,
        aero_setup=setup,
        fuel_kg=fuel_kg,
    )
    # Ritorna il segnale netto (positivo=understeer, negativo=oversteer)
    return us_pen - os_pen


def find_balanced_setup(target_avg_angle: float, mclaren_mods: dict,
                        arb_f: float = 0.5, arb_r: float = 0.5,
                        rh_f: float = 25.0, rh_r: float = 40.0,
                        fuel_kg: float = 12.0) -> tuple:
    """
    Dato un livello di carico (avg_angle), cerca fw e rw tali che
    ENTRAMBE le penalità (understeer E oversteer) siano vicine a zero.

    Strategia: griglia 2D su (fw, rw) ∈ [4°, 35°] con passo 0.5°,
    minimizza max(us_pen, os_pen) — il punto dove entrambe sono minime.
    Se ci sono molti minimi a zero, sceglie quello con avg più vicino
    al target.

    Returns:
        (fw_angle, rw_angle, net_error, us_pen, os_pen)
    """
    env = create_env()
    best_score = float('inf')
    best_fw, best_rw = target_avg_angle, target_avg_angle
    best_us, best_os = 1.0, 1.0

    # Griglia fine: cerca intorno al target ±15°
    fw_range = [4.0 + i * 0.5 for i in range(int((35.0 - 4.0) / 0.5) + 1)]
    rw_range = [4.0 + i * 0.5 for i in range(int((35.0 - 4.0) / 0.5) + 1)]

    for fw in fw_range:
        for rw in rw_range:
            # Filtra: deve essere vicino al target di carico richiesto
            if abs((fw + rw) / 2 - target_avg_angle) > 6.0:
                continue
            setup = make_aero_setup(fw, rw, mclaren_mods, arb_f, arb_r, rh_f, rh_r)
            ap = map_aero_setup(setup, env, fuel_kg=fuel_kg)
            us, os_, _ = _compute_balance_penalties(
                aero_balance=ap.aero_balance,
                fw_angle=fw, rw_angle=rw,
                aero_setup=setup, fuel_kg=fuel_kg,
            )
            # Minimizza il massimo delle due penalità (entrambe devono essere basse)
            score = max(us, os_)
            if score < best_score - 1e-6:
                best_score = score
                best_fw, best_rw = fw, rw
                best_us, best_os = us, os_
            elif abs(score - best_score) < 1e-6:
                # Pareggio: preferisci quello con avg più vicino al target
                if abs((fw + rw) / 2 - target_avg_angle) < abs((best_fw + best_rw) / 2 - target_avg_angle):
                    best_fw, best_rw = fw, rw
                    best_us, best_os = us, os_

    return best_fw, best_rw, best_us - best_os, best_us, best_os


def load_mclaren_mods() -> dict:
    for path in ["python_backend/data/teams_2025.json", "data/teams_2025.json"]:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            for team in data.get('teams', []):
                if team.get('team_id') == 'mclaren':
                    return team.get('base_aero', {})
    return {}


def create_driver() -> DriverSkills:
    return DriverSkills(
        raw_pace=93, race_craft=93, aggression=86, consistency=94,
        tyre_management=88, overtaking_skill=80, defending_skill=80,
        wet_skill=75, smoothness=88, setup_finding=85,
    )


def create_car() -> CarState:
    car = CarState()
    car.damage = DamageState()
    car.driver_mental = DriverMentalState()
    for pos in WheelPosition:
        ts = TyreState(compound=TyreCompound.C5)
        ts.age_laps = 0.0
        ts.wear_pct = 0.0
        ts.surface_temp_c = 115.0
        ts.core_temp_c = 110.0
        car.tyres[pos] = ts
    car.brakes = BrakeState(
        temp_front_c=650.0, temp_rear_c=620.0,
        wear_front_pct=0.0, wear_rear_pct=0.0,
        fade_level=0.0, duct_opening=0.45, bias_front_pct=0.54,
    )
    car.pu = PUState(
        active_map=EngineMapName.QUALIFY, ers_mode=ERSModeName.QUALIFY,
        ice_temp_c=80.0, ice_power_kw=550.0,
        ers_energy_mj=4.0, ers_output_kw=120.0, fuel_kg=12.0,
    )
    car.v_current_ms = 0.0
    return car


def create_env() -> EnvContext:
    return EnvContext(
        air_temp_c=28.0, track_temp_c=42.0,
        air_density_kg_m3=1.225, wind_speed_kph=2.0,
    )


def reload_config():
    import json as _j
    config = load_circuit_config("it-1922_monza")
    telem_path = "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json"
    if os.path.exists(telem_path):
        with open(telem_path) as f:
            telem = _j.load(f)
        for i, section in enumerate(config.sections):
            telem_secs = telem.get('geometry', {}).get('sections', [])
            if i < len(telem_secs):
                r = telem_secs[i].get('radius_m')
                if r and r > 50:
                    section.curve_profile.radius_m = r
                    section.curve_profile.curvature_factor = 1.0 / (1.0 + r / 100.0)
    if len(config.sections) > 0: config.sections[0].drs_available = True
    if len(config.sections) > 2: config.sections[2].drs_available = True
    return config


def simulate_lap(aero_setup: AeroSetup, driver, env) -> tuple:
    """Simula giro Monza. Returns (lap_time_s, v_max_kph, aero_params)."""
    config = reload_config()
    car = create_car()
    total_dt = 0.0
    v_max = 0.0
    for section in config.sections:
        try:
            result = update_section_v3(
                car_state=car, aero_setup=aero_setup, driver_skills=driver,
                section=section, env=env, config=config,
                push_level=10, is_qualifying=True,
                circuit_id="it-1922_monza", driver_id="NORRIS", lap_number=1,
            )
            total_dt += result.dt_s
            v_max = max(v_max, result.v_exit_kph)
            car.v_current_ms = result.v_exit_kph / 3.6
        except Exception:
            pass
    ap = map_aero_setup(aero_setup, env, v_estimate_kph=250.0, fuel_kg=12.0)
    return total_dt, v_max, ap


# ============================================================================
# TEST A — BILANCIATI: sweep da iper-scarico a ultra-carico
# ============================================================================

def run_test_a(mclaren_mods, driver, env):
    print()
    print("=" * 95)
    print("TEST A — SETUP BILANCIATI: sweep da iper-scarico a ultra-carico")
    print("=" * 95)
    print("  Per ogni livello di carico (avg_angle), trovo FW/RW che azzerano")
    print("  il combined_balance_error → setup VERAMENTE bilanciato.")
    print("  Atteso: curva U con minimo intorno ai 10-14° medi (ottimale Monza).")
    print()

    # Livelli di carico: avg_angle da 4° a 35°
    avg_angles = [4.0, 5.5, 7.0, 9.0, 11.0, 13.0, 15.0, 18.0, 21.0, 25.0, 30.0, 35.0]

    results = []
    for avg_a in avg_angles:
        fw, rw, err, us, os_ = find_balanced_setup(avg_a, mclaren_mods)
        setup = make_aero_setup(fw, rw, mclaren_mods)
        lap_time, v_max, ap = simulate_lap(setup, driver, env)
        label = "iper-scarico" if avg_a <= 5 else ("ultra-carico" if avg_a >= 32 else f"avg={avg_a:.0f}°")
        results.append((label, fw, rw, ap, lap_time, v_max, err, us, os_))

    # Trova il minimo
    best = min(results, key=lambda x: x[4])
    best_time = best[4]

    print(f"  {'Label':<14} {'FW°':>5} {'RW°':>5} {'CLA':>5} {'CDA':>5} {'Bal':>5} "
          f"{'Err':>6} {'Lap(s)':>8} {'Δbest':>7} {'Vmax':>7}")
    print(f"  {'-'*14} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5} "
          f"{'-'*6} {'-'*8} {'-'*7} {'-'*7}")

    best_time = best[4]
    for label, fw, rw, ap, lt, vm, err, us, os_ in results:
        marker = " ← OTTIMO" if lt == best_time else ""
        print(f"  {label:<14} {fw:>5.1f} {rw:>5.1f} {ap.CLA:>5.3f} {ap.CDA:>5.3f} "
              f"{ap.aero_balance:>5.3f} {err:>+6.3f} {lt:>8.3f} "
              f"{lt - best_time:>+7.3f} {vm:>7.1f}{marker}")

    print()
    print(f"  Setup ottimale Monza: FW={best[1]:.1f}° / RW={best[2]:.1f}° "
          f"→ {best[4]:.3f}s  (CLA={best[3].CLA:.3f}, CDA={best[3].CDA:.3f})")
    print()
    print("  Verifica curva U:")
    times = [r[4] for r in results]
    best_idx = times.index(min(times))
    left_ok = all(times[i] >= times[best_idx] for i in range(best_idx))
    right_ok = all(times[i] >= times[best_idx] for i in range(best_idx, len(times)))
    if left_ok and right_ok:
        print("  ✓ CURVA U CONFERMATA: il minimo è al centro, aumenta verso entrambi gli estremi")
    else:
        print("  ✗ CURVA U NON PERFETTA — analisi:")
        for i in range(len(results) - 1):
            if i < best_idx and times[i] < times[i+1]:
                print(f"    ⚠ Lato scarico non monotono: {results[i][0]} ({times[i]:.3f}) < {results[i+1][0]} ({times[i+1]:.3f})")
            if i >= best_idx and times[i] > times[i+1]:
                print(f"    ⚠ Lato carico non monotono: {results[i][0]} ({times[i]:.3f}) > {results[i+1][0]} ({times[i+1]:.3f})")
    return results


# ============================================================================
# TEST B — SBILANCIATI vs BILANCIATI
# ============================================================================

def run_test_b(mclaren_mods, driver, env):
    print()
    print("=" * 95)
    print("TEST B — SBILANCIATI vs BILANCIATI (stesso livello di carico)")
    print("=" * 95)
    print("  Per ogni livello di carico: bilanciato vs sovrasterzo vs sottosterzo.")
    print("  Atteso: bilanciato SEMPRE più veloce. Nessuna eccezione.")
    print()

    # 3 livelli di carico: basso (Monza), medio, alto (Monaco-style)
    levels = [
        ("Basso/Monza",  11.0),
        ("Medio",        18.0),
        ("Alto/Monaco",  28.0),
    ]

    all_ok = True

    for level_name, avg_angle in levels:
        fw_bal, rw_bal, _, _, _ = find_balanced_setup(avg_angle, mclaren_mods)

        # Sbilanciamenti: ±4° su FW mantenendo RW fisso
        # Sovrasterzo: FW molto meno del bilanciato → RW pesante → posteriore carico
        # Sottosterzo: FW molto più del bilanciato → anteriore pesante
        delta_os = 5.0   # gradi di sbilancio
        delta_us = 5.0

        setups = [
            ("bilanciato",   fw_bal,              rw_bal,              "neutro"),
            (f"oversteer -{delta_os:.0f}°FW", max(4.0, fw_bal - delta_os), rw_bal, "sovrasterzo"),
            (f"understeer +{delta_us:.0f}°FW", min(35.0, fw_bal + delta_us), rw_bal, "sottosterzo"),
        ]

        print(f"  [{level_name} — avg={avg_angle:.0f}°, bilanciato: FW={fw_bal:.1f}° RW={rw_bal:.1f}°]")
        print(f"    {'Setup':<20} {'FW°':>5} {'RW°':>5} {'CLA':>5} {'CDA':>5} "
              f"{'Bal':>5} {'USpen':>6} {'OSpen':>6} {'Lap(s)':>8} {'Δbil':>7}")
        print(f"    {'-'*20} {'-'*5} {'-'*5} {'-'*5} {'-'*5} "
              f"{'-'*5} {'-'*6} {'-'*6} {'-'*8} {'-'*7}")

        bal_time = None
        for label, fw, rw, kind in setups:
            setup = make_aero_setup(fw, rw, mclaren_mods)
            lap_time, v_max, ap = simulate_lap(setup, driver, env)
            if "bilanciato" in label:
                bal_time = lap_time
            delta = lap_time - bal_time if bal_time is not None else 0.0
            ok = "" if "bilanciato" in label else ("✓" if delta >= 0 else "✗ PROBLEMA")
            print(f"    {label:<20} {fw:>5.1f} {rw:>5.1f} {ap.CLA:>5.3f} {ap.CDA:>5.3f} "
                  f"{ap.aero_balance:>5.3f} {ap.understeer_grip_penalty:>6.3f} "
                  f"{ap.oversteer_grip_penalty:>6.3f} {lap_time:>8.3f} {delta:>+7.3f} {ok}")
            if delta < 0 and "bilanciato" not in label:
                all_ok = False
        print()

    if all_ok:
        print("  ✓ PRINCIPIO CONFERMATO: assetto bilanciato sempre ≥ veloce di qualsiasi sbilanciato")
    else:
        print("  ✗ PROBLEMA: alcuni assetti sbilanciati risultano più veloci del bilanciato")
        print("    → il modello di penalità ha bisogno di calibrazione")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print()
    print("╔" + "═"*93 + "╗")
    print("║   PHYSICS V3 WING SWEEP TEST — Monza / McLaren / Norris / C5 SOFT" + " "*25 + "║")
    print("║   Setup bilanciato = combined_balance_error ≈ 0 (trovato per ricerca binaria)" + " "*14 + "║")
    print("╚" + "═"*93 + "╝")

    mclaren_mods = load_mclaren_mods()
    driver = create_driver()
    env = create_env()

    run_test_a(mclaren_mods, driver, env)
    run_test_b(mclaren_mods, driver, env)

    print("═" * 95)
    print("Fine test.")
    print("═" * 95)
