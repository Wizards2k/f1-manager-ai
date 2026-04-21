"""
Test di Non Regressione per Waypoint Integrator

Questo test cattura i tempi su giro e le metriche chiave per un set
di circuiti rappresentativi PRIMA di qualsiasi refactoring del
waypoint_integrator. Dopo il refactoring, rieseguendo il test si
verifica che i risultati non siano cambiati oltre una tolleranza.

USO:
  1. Prima del refactoring:
     python -m pytest tests/physics_v4/test_integrator_regression.py -v --capture-baseline

  2. Dopo il refactoring:
     python -m pytest tests/physics_v4/test_integrator_regression.py -v

Se il test fallisce, confronta i diff per identificare regressioni.
"""

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Path setup
backend_dir = Path(__file__).resolve().parents[2] / "python_backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd
from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Circuiti rappresentativi che coprono diversi profili
CIRCUITS = [
    # (circuit_id, descrizione, aero_setup, compound, mass_kg, push_level)
    ("mc-1929_monaco", "Tight (Monaco)", {"front_wing": 38, "rear_wing": 42, "b_wing": 18}, "C6", 798.0, 10),
    ("it-1922_monza", "Fast (Monza)", {"front_wing": 4, "rear_wing": 6, "b_wing": 2}, "C5", 798.0, 10),
    ("jp-1962_suzuka", "Mixed (Suzuka)", {"front_wing": 22, "rear_wing": 18, "b_wing": 8}, "C4", 798.0, 10),
    ("gb-1948_silverstone", "Fast (Silverstone)", {"front_wing": 16, "rear_wing": 14, "b_wing": 6}, "C4", 798.0, 10),
    ("es-1991_barcelona", "Balanced (Barcelona)", {"front_wing": 24, "rear_wing": 20, "b_wing": 10}, "C3", 798.0, 10),
]

# Tolleranze per confronto
TOLERANCE_LAP_TIME_PCT = 0.05  # 0.05% = ~0.04s su 80s
TOLERANCE_VELOCITY_PCT = 0.1  # 0.1% su velocità
TOLERANCE_FUEL_PCT = 0.5  # 0.5% su carburante

# File dove salvare/caricare la baseline
BASELINE_FILE = Path(__file__).parent / "integrator_regression_baseline.json"


# ============================================================================
# FUNZIONI DI UTILITÀ
# ============================================================================

def run_single_lap(circuit_id: str, aero_setup: Dict, compound: str, mass_kg: float, push_level: int) -> Dict[str, Any]:
    """Esegue un singolo giro e restituisce le metriche chiave."""
    aero_calibration = get_aero_calibration(circuit_id)

    result = integrate_lap_hd(
        circuit_id=circuit_id,
        aero_setup=aero_setup,
        mass_kg=mass_kg,
        tyre_compound=compound,
        driver_skill=1.0,
        push_level=push_level,
        verbose=False,
        aero_calibration=aero_calibration,
        ers_power_fraction=1.0,
        pu_config={"engine_map": "QUALIFY"},
    )

    # Estrai metriche stabili (non oggetti complessi)
    telemetry = result.get("telemetry", [])
    n_telemetry = len(telemetry)

    # Calcola medie dai telemetry points (se disponibili)
    avg_accel = 0.0
    max_brake_fade = 0.0
    if telemetry:
        avg_accel = sum(p.get("acceleration_ms2", 0.0) for p in telemetry) / n_telemetry
        max_brake_fade = max(p.get("brake_fade_factor", 0.0) for p in telemetry)

    return {
        "circuit_id": circuit_id,
        "lap_time_s": round(result["lap_time_s"], 3),
        "v_max_kph": round(result["v_max_kph"], 1),
        "v_min_kph": round(result["v_min_kph"], 1),
        "v_avg_kph": round(result["v_avg_kph"], 1),
        "fuel_consumed_kg": round(result.get("fuel_consumed_kg", 0.0), 4),
        "waypoints_count": result["waypoints_count"],
        "avg_acceleration_ms2": round(avg_accel, 4),
        "max_brake_fade": round(max_brake_fade, 4),
        "sector_times": [round(t, 3) for t in result.get("sector_times", [])],
    }


def load_baseline() -> Dict[str, Any]:
    """Carica la baseline dal file JSON."""
    if not BASELINE_FILE.exists():
        pytest.skip(f"Baseline non trovata: {BASELINE_FILE}\n"
                    f"Esegui prima: pytest {Path(__file__).name} --capture-baseline")
    with open(BASELINE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_baseline(data: Dict[str, Any]) -> None:
    """Salva la baseline nel file JSON."""
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Baseline salvata in: {BASELINE_FILE}")


def compare_metrics(current: Dict, baseline: Dict, circuit_id: str) -> List[str]:
    """Confronta metriche current vs baseline, restituisce lista di errori."""
    errors = []

    # Lap time (la metrica più importante)
    lt_curr = current["lap_time_s"]
    lt_base = baseline["lap_time_s"]
    lt_diff_pct = abs(lt_curr - lt_base) / lt_base * 100 if lt_base > 0 else 0
    if lt_diff_pct > TOLERANCE_LAP_TIME_PCT:
        errors.append(
            f"  ❌ lap_time_s: {lt_curr:.3f}s vs baseline {lt_base:.3f}s "
            f"(diff {lt_diff_pct:+.3f}%, tolleranza {TOLERANCE_LAP_TIME_PCT}%)"
        )
    else:
        print(f"  ✅ lap_time_s: {lt_curr:.3f}s vs {lt_base:.3f}s ({lt_diff_pct:+.3f}%)")

    # Velocità max
    vm_curr = current["v_max_kph"]
    vm_base = baseline["v_max_kph"]
    vm_diff_pct = abs(vm_curr - vm_base) / vm_base * 100 if vm_base > 0 else 0
    if vm_diff_pct > TOLERANCE_VELOCITY_PCT:
        errors.append(
            f"  ❌ v_max_kph: {vm_curr:.1f} vs baseline {vm_base:.1f} "
            f"(diff {vm_diff_pct:+.3f}%, tolleranza {TOLERANCE_VELOCITY_PCT}%)"
        )
    else:
        print(f"  ✅ v_max_kph: {vm_curr:.1f} vs {vm_base:.1f} ({vm_diff_pct:+.3f}%)")

    # Velocità min
    vmin_curr = current["v_min_kph"]
    vmin_base = baseline["v_min_kph"]
    vmin_diff_pct = abs(vmin_curr - vmin_base) / vmin_base * 100 if vmin_base > 0 else 0
    if vmin_diff_pct > TOLERANCE_VELOCITY_PCT:
        errors.append(
            f"  ❌ v_min_kph: {vmin_curr:.1f} vs baseline {vmin_base:.1f} "
            f"(diff {vmin_diff_pct:+.3f}%, tolleranza {TOLERANCE_VELOCITY_PCT}%)"
        )
    else:
        print(f"  ✅ v_min_kph: {vmin_curr:.1f} vs {vmin_base:.1f} ({vmin_diff_pct:+.3f}%)")

    # Velocità media
    vavg_curr = current["v_avg_kph"]
    vavg_base = baseline["v_avg_kph"]
    vavg_diff_pct = abs(vavg_curr - vavg_base) / vavg_base * 100 if vavg_base > 0 else 0
    if vavg_diff_pct > TOLERANCE_VELOCITY_PCT:
        errors.append(
            f"  ❌ v_avg_kph: {vavg_curr:.1f} vs baseline {vavg_base:.1f} "
            f"(diff {vavg_diff_pct:+.3f}%, tolleranza {TOLERANCE_VELOCITY_PCT}%)"
        )
    else:
        print(f"  ✅ v_avg_kph: {vavg_curr:.1f} vs {vavg_base:.1f} ({vavg_diff_pct:+.3f}%)")

    # Carburante
    fuel_curr = current["fuel_consumed_kg"]
    fuel_base = baseline["fuel_consumed_kg"]
    fuel_diff_pct = abs(fuel_curr - fuel_base) / fuel_base * 100 if fuel_base > 0 else 0
    if fuel_diff_pct > TOLERANCE_FUEL_PCT:
        errors.append(
            f"  ❌ fuel_consumed_kg: {fuel_curr:.4f} vs baseline {fuel_base:.4f} "
            f"(diff {fuel_diff_pct:+.3f}%, tolleranza {TOLERANCE_FUEL_PCT}%)"
        )
    else:
        print(f"  ✅ fuel_consumed_kg: {fuel_curr:.4f} vs {fuel_base:.4f} ({fuel_diff_pct:+.3f}%)")

    # Sector times
    st_curr = current.get("sector_times", [])
    st_base = baseline.get("sector_times", [])
    if len(st_curr) == len(st_base):
        for i, (sc, sb) in enumerate(zip(st_curr, st_base)):
            st_diff_pct = abs(sc - sb) / sb * 100 if sb > 0 else 0
            if st_diff_pct > TOLERANCE_LAP_TIME_PCT:
                errors.append(
                    f"  ❌ sector_{i+1}: {sc:.3f}s vs baseline {sb:.3f}s "
                    f"(diff {st_diff_pct:+.3f}%)"
                )
            else:
                print(f"  ✅ sector_{i+1}: {sc:.3f}s vs {sb:.3f}s ({st_diff_pct:+.3f}%)")
    else:
        errors.append(f"  ❌ sector_times length mismatch: {len(st_curr)} vs {len(st_base)}")

    return errors


# ============================================================================
# TEST
# ============================================================================

@pytest.fixture(scope="module")
def capture_baseline(request):
    """Fixture che gestisce la cattura baseline."""
    return request.config.getoption("--capture-baseline", default=False)


def pytest_addoption(parser):
    """Aggiunge l'opzione --capture-baseline a pytest."""
    parser.addoption(
        "--capture-baseline",
        action="store_true",
        default=False,
        help="Cattura una nuova baseline invece di confrontarla",
    )


class TestIntegratorRegression:
    """Test suite di non regressione per il waypoint integrator."""

    def test_capture_or_compare(self, capture_baseline):
        """Test principale: cattura baseline o confronta."""
        results = {}
        all_errors = []

        if capture_baseline:
            print("\n" + "=" * 80)
            print("📸 CAPTURE BASELINE MODE")
            print("=" * 80)
        else:
            baseline_data = load_baseline()
            print("\n" + "=" * 80)
            print("🔍 COMPARE AGAINST BASELINE MODE")
            print("=" * 80)

        for circuit_id, desc, aero_setup, compound, mass_kg, push_level in CIRCUITS:
            print(f"\n🏁 {circuit_id} ({desc})")
            try:
                current = run_single_lap(circuit_id, aero_setup, compound, mass_kg, push_level)
                results[circuit_id] = current

                if capture_baseline:
                    print(f"  📊 lap_time_s={current['lap_time_s']:.3f}, "
                          f"v_max={current['v_max_kph']:.1f}, "
                          f"v_avg={current['v_avg_kph']:.1f}")
                else:
                    baseline = baseline_data.get(circuit_id)
                    if baseline is None:
                        all_errors.append(f"{circuit_id}: baseline mancante")
                        continue
                    errors = compare_metrics(current, baseline, circuit_id)
                    all_errors.extend([f"{circuit_id}: {e}" for e in errors])

            except Exception as e:
                error_msg = f"{circuit_id}: EXCEPTION {type(e).__name__}: {str(e)[:200]}"
                print(f"  ❌ {error_msg}")
                all_errors.append(error_msg)

        # Salva baseline se in capture mode
        if capture_baseline:
            save_baseline(results)
            pytest.skip("Baseline catturata con successo. Riesegui senza --capture-baseline per confrontare.")

        # Report finale
        print("\n" + "=" * 80)
        if all_errors:
            print(f"❌ TEST FALLITO: {len(all_errors)} regressioni trovate")
            for err in all_errors:
                print(err)
            print("=" * 80)
            pytest.fail(f"\n{len(all_errors)} regressioni rilevate:\n" + "\n".join(all_errors))
        else:
            print("✅ TEST PASSATO: Nessuna regressione rilevata su tutti i circuiti")
            print("=" * 80)


# ============================================================================
# ENTRY POINT DIRETTO
# ============================================================================

if __name__ == "__main__":
    # Se eseguito direttamente, cattura la baseline
    print("=" * 80)
    print("INTEGRATOR REGRESSION TEST - Direct Execution")
    print("=" * 80)
    print("\nPer catturare la baseline:")
    print("  python test_integrator_regression.py --capture")
    print("\nPer confrontare:")
    print("  pytest test_integrator_regression.py -v")
    print("=" * 80)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="Cattura baseline")
    parser.add_argument("--compare", action="store_true", help="Confronta con baseline esistente")
    args = parser.parse_args()

    if args.capture:
        results = {}
        for circuit_id, desc, aero_setup, compound, mass_kg, push_level in CIRCUITS:
            print(f"\n🏁 {circuit_id} ({desc})")
            current = run_single_lap(circuit_id, aero_setup, compound, mass_kg, push_level)
            results[circuit_id] = current
            print(f"  📊 lap_time_s={current['lap_time_s']:.3f}, "
                  f"v_max={current['v_max_kph']:.1f}, "
                  f"v_avg={current['v_avg_kph']:.1f}")
        save_baseline(results)
    elif args.compare:
        baseline_data = load_baseline()
        all_errors = []
        print("\n" + "=" * 80)
        print("🔍 COMPARE AGAINST BASELINE MODE")
        print("=" * 80)

        for circuit_id, desc, aero_setup, compound, mass_kg, push_level in CIRCUITS:
            print(f"\n🏁 {circuit_id} ({desc})")
            try:
                current = run_single_lap(circuit_id, aero_setup, compound, mass_kg, push_level)
                baseline = baseline_data.get(circuit_id)
                if baseline is None:
                    all_errors.append(f"{circuit_id}: baseline mancante")
                    continue
                errors = compare_metrics(current, baseline, circuit_id)
                all_errors.extend([f"{circuit_id}: {e}" for e in errors])
            except Exception as e:
                error_msg = f"{circuit_id}: EXCEPTION {type(e).__name__}: {str(e)[:200]}"
                print(f"  ❌ {error_msg}")
                all_errors.append(error_msg)

        print("\n" + "=" * 80)
        if all_errors:
            print(f"❌ TEST FALLITO: {len(all_errors)} regressioni trovate")
            for err in all_errors:
                print(err)
            print("=" * 80)
            sys.exit(1)
        else:
            print("✅ TEST PASSATO: Nessuna regressione rilevata su tutti i circuiti")
            print("=" * 80)
            sys.exit(0)
    else:
        print("\nNessuna azione specificata. Usa:")
        print("  --capture  per catturare la baseline")
        print("  --compare  per confrontare con la baseline")
        sys.exit(0)
