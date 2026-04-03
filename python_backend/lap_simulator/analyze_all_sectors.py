"""
ANALISI DETTAGLIATA: Tutti i 13 Settori Monza vs Physics V3

Confronto completo:
- Tempi (dt_real vs dt_sim)
- Velocità (entry/exit)
- Errori percentuali
- Pattern identificati
- Suggerimenti di tuning
"""

import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lap_simulator.data_types import (
    CarState, AeroSetup, DriverSkills, SectionContext, EnvContext,
    CircuitConfig, WheelPosition, TyreCompound,
    EngineMapName, ERSModeName, SectionKind, CurveProfile
)
from lap_simulator.physics_v3.update_section_v3 import update_section_v3
from lap_simulator.config_loader import load_circuit_config

logger = logging.getLogger(__name__)


def load_monza_telemetry() -> Optional[List[Dict[str, Any]]]:
    """Carica telemetria Monza 13 sezioni."""
    paths_to_try = [
        "python_backend/data/circuits/2025/it-1922_monza_Telemetry.json",
        "data/circuits/2025/it-1922_monza_Telemetry.json",
    ]

    for path in paths_to_try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                return data.get('geometry', {}).get('sections', [])

    return None


@dataclass
class SectorAnalysis:
    """Analisi dettagliata di un settore."""
    idx: int
    name: str
    kind: str
    length_m: float

    # Real data
    dt_real_s: float
    v_entry_real_kph: float
    v_exit_real_kph: float
    v_min_real_kph: float
    v_max_real_kph: float
    v_avg_real_kph: float

    # Simulated data
    dt_sim_s: float
    v_entry_sim_kph: float
    v_exit_sim_kph: float
    v_max_sim_kph: float
    v_avg_sim_kph: float

    # Errors
    dt_error_s: float
    dt_error_pct: float
    v_exit_error_kph: float
    v_exit_error_pct: float

    def is_straight(self) -> bool:
        return "straight" in self.kind.lower()

    def is_corner(self) -> bool:
        return not self.is_straight()

    def error_grade(self) -> str:
        """Classifica errore: EXCELLENT / GOOD / OK / POOR / BAD"""
        abs_error = abs(self.dt_error_pct)
        if abs_error < 2:
            return "EXCELLENT"
        elif abs_error < 5:
            return "GOOD"
        elif abs_error < 10:
            return "OK"
        elif abs_error < 20:
            return "POOR"
        else:
            return "BAD"

    def grade_emoji(self) -> str:
        grade = self.error_grade()
        return {
            "EXCELLENT": "✓✓",
            "GOOD": "✓",
            "OK": "⚠️",
            "POOR": "❌",
            "BAD": "🔴"
        }.get(grade, "?")


def main():
    print("="*150)
    print("ANALISI COMPLETA: Tutti i 13 Settori Monza — Physics V3 vs Telemetria Reale")
    print("="*150)
    print()

    # Load data
    telemetry_sections = load_monza_telemetry()
    if not telemetry_sections:
        print("❌ Telemetria non trovata")
        return

    config = load_circuit_config("it-1922_monza")
    if not config or not config.sections:
        print("❌ Circuit config non trovato")
        return

    # Setup simulazione
    driver_skills = DriverSkills(
        raw_pace=93, race_craft=93, aggression=86, consistency=94,
        tyre_management=88, overtaking_skill=80, defending_skill=80,
        wet_skill=75, smoothness=88, setup_finding=85,
    )

    aero_setup = AeroSetup()
    aero_setup.ride_height_front_mm = 25.0
    aero_setup.ride_height_rear_mm = 40.0

    env = EnvContext(
        air_temp_c=28.0, track_temp_c=42.0,
        air_density_kg_m3=1.225, wind_speed_kph=2.0,
    )

    # Initial car state (LANCIATO!)
    car_state = CarState(
        car_id="mclaren_norris",
        team_code="MCL",
        lap_number=3,
        v_current_ms=321.6 / 3.6,  # 89.3 m/s (giro lanciato!)
    )

    for pos in WheelPosition:
        from lap_simulator.data_types import TyreState
        car_state.tyres[pos] = TyreState(
            wheel_pos=pos, compound=TyreCompound.C5,
            surface_temp_c=118.0, core_temp_c=115.0, wear_pct=2.0,
        )

    car_state.brakes.temp_front_c = 650.0
    car_state.brakes.temp_rear_c = 620.0
    car_state.pu.active_map = EngineMapName.QUALIFY
    car_state.pu.ers_mode = ERSModeName.QUALIFY
    car_state.pu.ice_power_kw = 950.0
    car_state.pu.ers_output_kw = 160.0
    car_state.pu.ers_energy_mj = 4.0
    car_state.pu.fuel_kg = 12.0

    # Simulate all sectors
    analyses: List[SectorAnalysis] = []
    total_dt_real = 0.0
    total_dt_sim = 0.0

    # FIX: Correct the radius values from telemetry JSON which are being incorrectly modified
    # Turn 1 should be 668.5m (Parabolica), not 27.9m
    print(f"[RADIUS FIX]")
    for i, section in enumerate(config.sections):
        if i < len(telemetry_sections):
            telem_radius = telemetry_sections[i].get('radius_m')
            if telem_radius and telem_radius > 50:  # Meaningful radius (not a rettilineo)
                old_radius = section.curve_profile.radius_m
                # Recalculate curvature_factor with correct radius
                section.curve_profile.radius_m = telem_radius
                section.curve_profile.curvature_factor = 1.0 / (1.0 + telem_radius / 100.0)
                if i <= 2:  # Print only first 3 sectors
                    print(f"  Sector {i} ({section.name}): {old_radius:.1f}m → {telem_radius:.1f}m")

    print("[SIMULAZIONE]")
    print("-"*150)

    for idx in range(13):
        telemetry_data = telemetry_sections[idx]
        config_section = config.sections[idx] if idx < len(config.sections) else None

        # Use config section if available
        section = config_section if config_section else None

        if not section:
            continue

        # Real data
        dt_real = telemetry_data.get('dt_ref_s', 0.0)
        v_entry_real = telemetry_data.get('v_entry_kph', 0.0)
        v_exit_real = telemetry_data.get('v_exit_kph', 0.0)
        v_min_real = telemetry_data.get('v_min_kph', v_entry_real)
        v_max_real = telemetry_data.get('v_max_kph', v_exit_real)
        length_m = telemetry_data.get('length_m', 0.0)
        kind = telemetry_data.get('kind', 'UNKNOWN')

        # Simulate
        try:
            result = update_section_v3(
                car_state=car_state,
                aero_setup=aero_setup,
                driver_skills=driver_skills,
                section=section,
                env=env,
                config=config,
                push_level=10,
                is_qualifying=True,
                circuit_id="it-1922_monza",
                driver_id="NORRIS",
                lap_number=3,
            )

            dt_sim = result.dt_s
            v_exit_sim = result.v_exit_kph
            v_max_sim = result.v_max_kph

        except Exception as e:
            print(f"❌ Errore sezione {idx}: {e}")
            continue

        # Calculate averages
        v_avg_real = length_m / dt_real * 3.6 if dt_real > 0 else 0
        v_avg_sim = length_m / dt_sim * 3.6 if dt_sim > 0 else 0

        # Errors
        dt_error_s = dt_sim - dt_real
        dt_error_pct = (dt_error_s / dt_real * 100) if dt_real > 0 else 0
        v_exit_error_kph = v_exit_sim - v_exit_real
        v_exit_error_pct = (v_exit_error_kph / v_exit_real * 100) if v_exit_real > 0 else 0

        # Create analysis
        analysis = SectorAnalysis(
            idx=idx,
            name=telemetry_data.get('name', f'Sector {idx}'),
            kind=kind,
            length_m=length_m,
            dt_real_s=dt_real,
            v_entry_real_kph=v_entry_real,
            v_exit_real_kph=v_exit_real,
            v_min_real_kph=v_min_real,
            v_max_real_kph=v_max_real,
            v_avg_real_kph=v_avg_real,
            dt_sim_s=dt_sim,
            v_entry_sim_kph=car_state.v_current_ms * 3.6,
            v_exit_sim_kph=v_exit_sim,
            v_max_sim_kph=v_max_sim,
            v_avg_sim_kph=v_avg_sim,
            dt_error_s=dt_error_s,
            dt_error_pct=dt_error_pct,
            v_exit_error_kph=v_exit_error_kph,
            v_exit_error_pct=v_exit_error_pct,
        )

        analyses.append(analysis)
        total_dt_real += dt_real
        total_dt_sim += dt_sim

        # Update car state for next sector
        car_state.v_current_ms = v_exit_sim / 3.6

    print()
    print("[VELOCITÀ PROPAGAZIONE]")
    print("="*150)
    print(f"{'#':<3} {'Settore':<25} {'V.Entry Real':<12} {'V.Entry Sim':<12} {'V.Exit Real':<12} {'V.Exit Sim':<12} {'ΔExit':<10}")
    print("-"*150)

    for i, analysis in enumerate(analyses):
        v_exit_delta = analysis.v_exit_sim_kph - analysis.v_exit_real_kph
        print(
            f"{analysis.idx:<3} {analysis.name:<25} "
            f"{analysis.v_entry_real_kph:>10.1f} {analysis.v_entry_sim_kph:>10.1f} "
            f"{analysis.v_exit_real_kph:>10.1f} {analysis.v_exit_sim_kph:>10.1f} "
            f"{v_exit_delta:>+8.1f}"
        )

    print()
    print("[RISULTATI DETTAGLIATI — TEMPI]")
    print("="*150)
    print(f"{'#':<3} {'Settore':<25} {'Tipo':<12} {'Real':<10} {'Sim':<10} {'Δ':<10} {'%':<8} {'Grade':<12}")
    print("-"*150)

    for analysis in analyses:
        print(
            f"{analysis.idx:<3} {analysis.name:<25} {analysis.kind:<12} "
            f"{analysis.dt_real_s:>8.3f}s {analysis.dt_sim_s:>8.3f}s "
            f"{analysis.dt_error_s:+8.3f}s {analysis.dt_error_pct:+7.1f}% "
            f"{analysis.grade_emoji()} {analysis.error_grade():<8}"
        )

    print("="*150)
    print()

    # Summary statistics
    print("[STATISTICHE AGGREGATE]")
    print(f"Tempo totale real:     {total_dt_real:7.3f}s")
    print(f"Tempo totale sim:      {total_dt_sim:7.3f}s")
    print(f"Errore totale:         {total_dt_sim - total_dt_real:+7.3f}s ({(total_dt_sim - total_dt_real)/total_dt_real*100:+6.2f}%)")
    print()

    # Grade distribution
    grades = {}
    for a in analyses:
        grade = a.error_grade()
        grades[grade] = grades.get(grade, 0) + 1

    print("[DISTRIBUZIONE GRADE]")
    for grade in ["EXCELLENT", "GOOD", "OK", "POOR", "BAD"]:
        count = grades.get(grade, 0)
        pct = count / len(analyses) * 100 if analyses else 0
        print(f"  {grade:<12}: {count:2d} settori ({pct:5.1f}%)")

    print()

    # Analisi catena di propagazione velocità
    print("[CATENA DI PROPAGAZIONE VELOCITÀ]")
    print("="*150)
    print()

    # Traccia la divergenza velocità da settore a settore
    v_exit_error_cumulative = 0.0
    first_divergence_idx = None

    for i, analysis in enumerate(analyses):
        v_exit_error = analysis.v_exit_sim_kph - analysis.v_exit_real_kph
        v_exit_error_cumulative += abs(v_exit_error)

        if first_divergence_idx is None and abs(v_exit_error) > 1.0:
            first_divergence_idx = i

    if first_divergence_idx is not None:
        print(f"⚠️ PRIMA DIVERGENZA RILEVATA a: {analyses[first_divergence_idx].name}")
        a = analyses[first_divergence_idx]
        print(f"   v_exit_real: {a.v_exit_real_kph:.1f} kph")
        print(f"   v_exit_sim:  {a.v_exit_sim_kph:.1f} kph")
        print(f"   ΔV_exit: {a.v_exit_sim_kph - a.v_exit_real_kph:+.1f} kph")
        print()

    # Mostra propagazione da sector a sector
    print("DETTAGLIO PROPAGAZIONE (entry → exit per ogni settore):")
    print()

    for i, analysis in enumerate(analyses):
        next_analysis = analyses[i + 1] if i + 1 < len(analyses) else None

        # Verifica se v_exit_sim di questo settore = v_entry_sim del prossimo
        is_first = "✓" if i == 0 else ""

        print(f"[Settore {analysis.idx}: {analysis.name}]")
        print(f"  Entry:  Real={analysis.v_entry_real_kph:7.1f} kph  Sim={analysis.v_entry_sim_kph:7.1f} kph  "
              f"ΔEntry={analysis.v_entry_sim_kph - analysis.v_entry_real_kph:+6.1f} kph")
        print(f"  Exit:   Real={analysis.v_exit_real_kph:7.1f} kph  Sim={analysis.v_exit_sim_kph:7.1f} kph  "
              f"ΔExit={analysis.v_exit_sim_kph - analysis.v_exit_real_kph:+6.1f} kph")
        print(f"  Tempo:  Real={analysis.dt_real_s:7.3f}s  Sim={analysis.dt_sim_s:7.3f}s  "
              f"ΔT={analysis.dt_error_s:+6.3f}s ({analysis.dt_error_pct:+6.1f}%)")

        if next_analysis:
            v_exit_to_entry_propagation = f"{analysis.v_exit_sim_kph:7.1f}"
            print(f"  → Diventa v_entry prossimo: {v_exit_to_entry_propagation} kph")

        print()

    # Straight vs Corner analysis
    straights = [a for a in analyses if a.is_straight()]
    corners = [a for a in analyses if a.is_corner()]

    avg_straight_error = sum(abs(a.dt_error_pct) for a in straights) / len(straights) if straights else 0
    avg_corner_error = sum(abs(a.dt_error_pct) for a in corners) / len(corners) if corners else 0

    print("[ANALISI PER TIPO]")
    print(f"  Rettilinei ({len(straights)}):  Errore medio ±{avg_straight_error:5.1f}%")
    print(f"  Curve ({len(corners)}):       Errore medio ±{avg_corner_error:5.1f}%")
    print()

    # Problem areas
    print("[AREE CRITICHE (errore > 10%)]")
    problem_areas = [a for a in analyses if abs(a.dt_error_pct) > 10]
    if problem_areas:
        for a in problem_areas:
            print(f"  • {a.name:<25} {a.dt_error_pct:+7.1f}% ({a.dt_error_s:+.3f}s)")
    else:
        print("  ✓ Nessun'area critica!")

    print()

    # ANALISI DIAGNOSTICA: Perché le velocità divergono?
    print("[ANALISI DIAGNOSTICA — FISICA DELLA DIVERGENZA]")
    print("="*150)
    print()

    # Identifica "velocity sinks" (settori che perdono troppa velocità)
    print("VELOCITY SINKS (settori che perdono velocità eccessivamente):")
    for a in analyses:
        if a.is_straight():
            # In rettilineo, dovrebbe accelerare o mantenere velocità
            # Se v_exit_sim < v_exit_real, significa che NON sta accelerando abbastanza
            v_gained_real = a.v_exit_real_kph - a.v_entry_real_kph
            v_gained_sim = a.v_exit_sim_kph - a.v_entry_sim_kph
            v_gained_error = v_gained_sim - v_gained_real

            if abs(v_gained_error) > 1.0:
                print(f"  • {a.name:<25} ΔV_real={v_gained_real:+6.1f}kph vs ΔV_sim={v_gained_sim:+6.1f}kph (errore={v_gained_error:+6.1f}kph)")

    print()
    print("VELOCITY GAINS ANALYSIS (accelerazione nei rettilinei):")
    for a in straights:
        v_gained_real = a.v_exit_real_kph - a.v_entry_real_kph
        v_gained_sim = a.v_exit_sim_kph - a.v_entry_sim_kph
        efficiency = (v_gained_sim / v_gained_real * 100) if v_gained_real != 0 else 0

        symbol = "✓✓" if efficiency > 95 else "✓" if efficiency > 85 else "⚠️" if efficiency > 75 else "❌"
        print(f"  {symbol} {a.name:<25} Real:{v_gained_real:+6.1f}kph → Sim:{v_gained_sim:+6.1f}kph ({efficiency:5.1f}%)")

    print()
    print("BRAKING EFFICIENCY IN CORNERS (efficienza frenata nelle curve):")
    for a in corners:
        v_lost_real = a.v_entry_real_kph - a.v_exit_real_kph
        v_lost_sim = a.v_entry_sim_kph - a.v_exit_sim_kph

        if v_lost_real > 0:
            efficiency = (v_lost_sim / v_lost_real * 100) if v_lost_real != 0 else 0
            symbol = "✓✓" if 95 < efficiency < 110 else "✓" if 85 < efficiency < 120 else "⚠️" if 70 < efficiency < 130 else "❌"
            print(f"  {symbol} {a.name:<25} Real:{v_lost_real:+6.1f}kph ↓ Sim:{v_lost_sim:+6.1f}kph (efficienza={efficiency:5.1f}%)")

    print()

    # Recommendations
    print("[SUGGERIMENTI DI TUNING]")
    print()

    # Straight 2 problem
    straight2 = next((a for a in analyses if a.idx == 2), None)
    if straight2 and straight2.dt_error_pct > 30:
        print(f"1. STRAIGHT 2 (+{straight2.dt_error_pct:.1f}%)")
        print(f"   Problema: Velocità di entry bassa causa rallentamento")
        print(f"   Fix: Verificare v_exit da Turn 1 e propagazione di stato")
        print()

    # Straight 3 problem
    straight3 = next((a for a in analyses if a.idx == 4), None)
    if straight3 and straight3.dt_error_pct > 20:
        print(f"2. STRAIGHT 3 (+{straight3.dt_error_pct:.1f}%)")
        print(f"   Problema: Velocità media bassa")
        print(f"   Fix: Verificare CDA calibrazione per accelerazione realistica")
        print()

    # General recommendations
    if avg_straight_error > avg_corner_error + 5:
        print(f"3. RETTILINEI LENTI (Avg: ±{avg_straight_error:.1f}% vs curve ±{avg_corner_error:.1f}%)")
        print(f"   Problema: CDA potrebbe essere troppo alto (drag eccessivo)")
        print(f"   Fix: Ridurre CDA di ~5-10% e ritestare")
        print()

    if any(a.dt_error_pct < -5 for a in analyses):
        print(f"4. ALCUNI SETTORI TROPPO VELOCI")
        print(f"   Nota: Potrebbe indicare che v_apex è troppo aggressiva")
        print(f"   Fix: Verificare balance model e corner_solver")
        print()

    print("="*150)
    print(f"✓ Analisi completata")
    print("="*150)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
