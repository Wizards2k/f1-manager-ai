#!/usr/bin/env python3
"""
Setup Sensitivity Tests — V5.6 Pipeline
========================================
6 batterie di test per verificare che il motore fisico reagisca correttamente
a cambiamenti di setup, UNA VARIABILE ALLA VOLTA.

Usa lo stesso pipeline di validate_v56.py:
  - PhysicsV4Setup con DriverSkill generico (quali_skill=1.0)
  - Nessun team_data (modifier DF = 1.0 di default)
  - push_level=10 (zero penalty)
  - Suspension, compound, fuel dal validate_v56.py

Circuiti di test: Monza, Monaco, Silverstone, Suzuka, Barcelona

Batterie:
  1. Aero sweep    — FW/RW/bwing variano insieme (5 livelli)
  2. Fuel load     — 5kg → 110kg (5 livelli)
  3. Tyre compound — C1 → C6 (6 livelli)
  4. Suspension    — spring/ARB/RH variano (5 livelli)
  5. ICE/ERS       — engine_map + ers_mode (5 livelli)
  6. Push level    — push 1→10 (5 livelli)

Uso:
    python setup_sensitivity_v56.py aero
    python setup_sensitivity_v56.py fuel
    python setup_sensitivity_v56.py tyres
    python setup_sensitivity_v56.py suspension
    python setup_sensitivity_v56.py ers
    python setup_sensitivity_v56.py push
    python setup_sensitivity_v56.py all
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup, DriverSkill
from lap_simulator.push_penalty import compute_push_penalty
from lap_simulator.data_types import CircuitConfig

# ── Configurazione circuiti di test ──────────────────────────────────────────
# Stessi parametri di validate_v56.py
TEST_CIRCUITS = {
    "monza": {
        "circuit_id": "it-1922_monza",
        "front_wing": 8.0, "rear_wing": 10.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 78.869,
        "susp_source": "monza",
        "bwing": 5.0,
    },
    "monaco": {
        "circuit_id": "mc-1929_monaco",
        "front_wing": 38.0, "rear_wing": 42.0,
        "compound": "C6", "fuel_kg": 20.0,
        "ref_time": 69.954,
        "susp_source": "monaco",
        "bwing": 18.0,
    },
    "silverstone": {
        "circuit_id": "gb-1948_silverstone",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C5", "fuel_kg": 20.0,
        "ref_time": 85.010,
        "susp_source": "silverstone",
        "bwing": 10.0,
    },
    "suzuka": {
        "circuit_id": "jp-1962_suzuka",
        "front_wing": 24.0, "rear_wing": 28.0,
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 86.995,
        "susp_source": "silverstone",
        "bwing": 10.0,
    },
    "barcelona": {
        "circuit_id": "es-1991_barcelona",
        "front_wing": 22.0, "rear_wing": 26.0,
        "compound": "C3", "fuel_kg": 20.0,
        "ref_time": 71.546,
        "susp_source": "silverstone",
        "bwing": 10.0,
    },
}

# Stesse sospensioni di validate_v56.py
SUSP_SETUPS = {
    "monza": {
        "spring_front": 25.0, "spring_rear": 33.0,
        "arb_front": 8.0, "arb_rear": 13.0,
        "ride_height_front": 10.0, "ride_height_rear": 17.0,
    },
    "monaco": {
        "spring_front": 10.0, "spring_rear": 18.0,
        "arb_front": 25.0, "arb_rear": 30.0,
        "ride_height_front": 16.0, "ride_height_rear": 23.0,
    },
    "silverstone": {
        "spring_front": 25.0, "spring_rear": 33.0,
        "arb_front": 25.0, "arb_rear": 30.0,
        "ride_height_front": 2.0, "ride_height_rear": 9.0,
    },
}

# Driver generico (stesso di validate_v56.py)
REFERENCE_DRIVER = DriverSkill(
    name="Reference",
    quali_skill=1.0,
    race_skill=1.0,
    braking_skill=1.0,
    cornering_skill=1.0,
    throttle_skill=1.0,
    consistency=1.0,
    front_wing_offset=0,
    rear_wing_offset=0,
    brake_bias_offset=0.0,
)


# ── Helper: simulazione singola ──────────────────────────────────────────────
def simulate_lap(
    circuit_id: str,
    front_wing: float,
    rear_wing: float,
    bwing: float,
    susp_source: str,
    compound: str,
    fuel_kg: float,
    ers_mode: str = "quali_deploy",
    push_level: int = 10,
) -> Dict:
    """Simula un giro con il pipeline V5.6 (stesso di validate_v56.py)."""
    susp = SUSP_SETUPS[susp_source]

    setup = PhysicsV4Setup(
        driver_data=REFERENCE_DRIVER,
        circuit=circuit_id,
        session="qualifying",
    )

    setup.set_aero(front_wing=front_wing, rear_wing=rear_wing, bwing=bwing)
    setup.set_suspension(
        spring_front=susp["spring_front"],
        spring_rear=susp["spring_rear"],
        ARB_front=susp["arb_front"],
        ARB_rear=susp["arb_rear"],
        ride_height_front=susp["ride_height_front"],
        ride_height_rear=susp["ride_height_rear"],
    )
    setup.set_fuels(fuel_kg=fuel_kg, fuel_mix="rich")
    setup.set_tyres(compound=compound)
    setup.set_ers_mode(ers_mode)

    r = setup.simulate_lap(verbose=False)
    physics_time = r["lap_time_s"]

    # Push penalty (0.0 for push=10)
    if push_level < 10:
        config = CircuitConfig()
        penalty = compute_push_penalty(
            push_level=push_level,
            driver_qualifica=50,
            driver_gara=50,
            driver_costanza=50,
            is_qualifying=True,
            circuit_id=circuit_id,
            driver_id="reference",
            lap_number=1,
            config=config,
        )
        physics_time += penalty

    return {
        "lap_time_s": physics_time,
        "v_max_kph": r.get("v_max_kph", 0),
        "setup": r.get("setup", {}),
    }


# ── Helper: stampa risultati ─────────────────────────────────────────────────
def print_header(title: str):
    print()
    print("╔" + "═" * 100 + "╗")
    print(f"║  {title:<98}║")
    print("╚" + "═" * 100 + "╝")


def print_table(
    circuit_name: str,
    rows: List[Tuple[str, float, Dict]],  # (label, lap_time, extra_cols)
    ref_time: float,
    baseline_time: Optional[float] = None,
    extra_headers: List[str] = None,
):
    """Stampa tabella risultati per un circuito."""
    extra_headers = extra_headers or []
    extra_w = sum(len(h) + 3 for h in extra_headers)

    print(f"\n  🏁 {circuit_name}  (ref={ref_time:.3f}s)")
    sep = "  " + "─" * (95 + extra_w)
    print(sep)

    hdr_extra = "".join(f"  {h}" for h in extra_headers)
    print(f"  {'Livello':<35} {'Lap s':>8} {'Δ base':>8} {'Δ ref':>9} {'%':>7}{hdr_extra}")
    print(sep)

    if baseline_time is None and rows:
        baseline_time = rows[0][1]

    for label, lap_time, extras in rows:
        d_ref = lap_time - ref_time
        d_base = lap_time - baseline_time
        pct = d_ref / ref_time * 100

        if abs(d_base) < 0.001:
            mark = " ◀ BASE"
        elif d_base < 0:
            mark = " ⚡"
        else:
            mark = ""

        flag = "✅" if abs(pct) < 1.0 else ("🟡" if abs(pct) < 3.0 else "🔴")
        extra_str = "".join(f"  {v}" for v in extras.values()) if extras else ""
        print(f"  {label:<35} {lap_time:>8.3f} {d_base:>+8.3f} {d_ref:>+8.3f}s ({pct:>+5.2f}%) {flag}{mark}{extra_str}")

    print(sep)

    # Gap primo → ultimo
    if len(rows) >= 2:
        gap = rows[-1][1] - rows[0][1]
        print(f"    Δ min → max:  {gap:+.3f}s  ({gap / rows[0][1] * 100:+.2f}%)")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 1 — AERO SWEEP
# ══════════════════════════════════════════════════════════════════════════════
def test_aero_sweep():
    """
    Variare FW, RW e bwing insieme su 5 livelli.
    Fisso: compound=SOFT, fuel=20kg, susp=calibrata, ERS=quali, push=10.

    Aspettativa:
      - Monza: Low DF (baseline) è il più veloce, High DF più lento
      - Monaco: High DF (baseline) è il più veloce, Low DF più lento
      - Silverstone/Suzuka/Barcelona: Medium DF (baseline) è il più veloce
    """
    print_header("BATTERIA 1 — AERO SWEEP  (FW + RW + bWing)")

    # 5 livelli di DF: da minimo a massimo
    # Ogni livello: (delta_fw, delta_rw, delta_bwing)
    DF_LEVELS = [
        ("Min DF  (FW-6 RW-6 BW-8)",    -6, -6, -8),
        ("Low DF  (FW-3 RW-3 BW-4)",    -3, -3, -4),
        ("Baseline ★ (calibrated)",       0,  0,  0),
        ("High DF (FW+6 RW+6 BW+4)",    +6, +6, +4),
        ("Max DF  (FW+14 RW+14 BW+8)", +14, +14, +8),
    ]

    for name, cfg in TEST_CIRCUITS.items():
        rows = []
        for label, dfw, drw, dbw in DF_LEVELS:
            fw = max(1.0, cfg["front_wing"] + dfw)
            rw = max(1.0, cfg["rear_wing"] + drw)
            bw = max(1.0, min(20.0, cfg["bwing"] + dbw))

            r = simulate_lap(
                circuit_id=cfg["circuit_id"],
                front_wing=fw, rear_wing=rw, bwing=bw,
                susp_source=cfg["susp_source"],
                compound=cfg["compound"],
                fuel_kg=cfg["fuel_kg"],
            )

            rows.append((
                label,
                r["lap_time_s"],
                {
                    "FW/RW": f"FW={fw:.0f}° RW={rw:.0f}°",
                    "BW": f"BW={bw:.0f}°",
                    "Vmax": f"Vmax={r['v_max_kph']:.0f}",
                },
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["FW/RW", "BW", "Vmax"],
        )

    # Riepilogo comparativo con setup completo (FW + RW + BW)
    print("\n  📋 RIEPILOGO — Setup più veloce per circuito:")
    print("  " + "─" * 95)
    print(f"  {'Circuito':<15} {'Miglior livello':<30} {'Lap s':>8} {'FW':>5} {'RW':>5} {'BW':>5} {'Vmax':>6}")
    print("  " + "─" * 95)

    # Ricalcola per trovare il migliore per circuito
    for name, cfg in TEST_CIRCUITS.items():
        best_time = 999
        best_label = ""
        best_fw = best_rw = best_bw = 0
        best_vmax = 0
        for label, dfw, drw, dbw in DF_LEVELS:
            fw = max(1.0, cfg["front_wing"] + dfw)
            rw = max(1.0, cfg["rear_wing"] + drw)
            bw = max(1.0, min(20.0, cfg["bwing"] + dbw))
            r = simulate_lap(
                circuit_id=cfg["circuit_id"],
                front_wing=fw, rear_wing=rw, bwing=bw,
                susp_source=cfg["susp_source"],
                compound=cfg["compound"],
                fuel_kg=cfg["fuel_kg"],
            )
            if r["lap_time_s"] < best_time:
                best_time = r["lap_time_s"]
                best_label = label
                best_fw = fw
                best_rw = rw
                best_bw = bw
                best_vmax = r["v_max_kph"]
        print(f"  {name:<15} {best_label:<30} {best_time:>8.3f} {best_fw:>5.0f}° {best_rw:>5.0f}° {best_bw:>5.0f}° {best_vmax:>5.0f}")

    print("  " + "─" * 95)

    # Aspettative
    print("\n  📋 ASPETTATIVE:")
    print("     Monza:     Min DF → più veloce ✅  (circuito veloce, BW bassa)")
    print("     Monaco:    Max DF → più veloce ✅  (circuito lento/torto, BW alta)")
    print("     Silverstone: Baseline → più veloce ✅  (circuito medio, BW=10°)")
    print("     Suzuka:    Baseline → più veloce ✅  (circuito medio-alto, BW=10°)")
    print("     Barcelona: Baseline → più veloce ✅  (circuito medio, BW=10°)")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 2 — FUEL LOAD
# ══════════════════════════════════════════════════════════════════════════════
def test_fuel_load():
    """
    Carburante varia da 5kg a 110kg.
    Fisso: aero=calibrato, compound=SOFT, susp=calibrata, ERS=quali, push=10.

    Aspettativa: più fuel = più lento (linearmente ~0.03s/kg)
    """
    print_header("BATTERIA 2 — FUEL LOAD  (5kg → 110kg)")

    FUEL_LEVELS = [
        ("Q pura     (5 kg)",    5.0),
        ("Q standard (20 kg) ★", 20.0),
        ("Sprint     (45 kg)",   45.0),
        ("Gara media (75 kg)",   75.0),
        ("Gara piena (110 kg)", 110.0),
    ]

    for name, cfg in TEST_CIRCUITS.items():
        rows = []
        for label, fuel in FUEL_LEVELS:
            r = simulate_lap(
                circuit_id=cfg["circuit_id"],
                front_wing=cfg["front_wing"],
                rear_wing=cfg["rear_wing"],
                bwing=cfg["bwing"],
                susp_source=cfg["susp_source"],
                compound=cfg["compound"],
                fuel_kg=fuel,
            )
            rows.append((
                label,
                r["lap_time_s"],
                {"Fuel": f"Fuel={fuel:.0f}kg", "Mass": f"Mass={798+fuel:.0f}kg"},
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["Fuel", "Mass"],
        )

    print("\n  📋 ASPETTATIVE:")
    print("     Ogni +10kg fuel → ~+0.3s (Monza) a ~+0.2s (Monaco)")
    print("     5kg → 110kg: ~3-4s spread su tutti i circuiti")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 3 — TYRE COMPOUND
# ══════════════════════════════════════════════════════════════════════════════
def test_tyre_compound():
    """
    Compound varia da C1 (duro) a C6 (morbido).
    Fisso: aero=calibrato, fuel=20kg, susp=calibrata, ERS=quali, push=10.

    Aspettativa: C6 (più grip) → più veloce, C1 (meno grip) → più lento
    """
    print_header("BATTERIA 3 — TYRE COMPOUND  (C1 → C6)")

    COMPOUND_LEVELS = [
        ("C1  (hard estremo)",  "C1"),
        ("C2  (hard)",          "C2"),
        ("C3  (medium)",        "C3"),
        ("C4  (medium-soft)",   "C4"),
        ("C5  (soft)",          "C5"),
        ("C6  (ultra-soft)",    "C6"),
    ]

    from lap_simulator.physics_v4.core.constants import MU_BASE

    for name, cfg in TEST_CIRCUITS.items():
        rows = []
        for label, compound in COMPOUND_LEVELS:
            r = simulate_lap(
                circuit_id=cfg["circuit_id"],
                front_wing=cfg["front_wing"],
                rear_wing=cfg["rear_wing"],
                bwing=cfg["bwing"],
                susp_source=cfg["susp_source"],
                compound=compound,
                fuel_kg=cfg["fuel_kg"],
            )
            mu = MU_BASE.get(compound, 0)
            is_baseline = "★" if compound == cfg["compound"] else ""
            rows.append((
                f"{label} {is_baseline}",
                r["lap_time_s"],
                {"μ": f"μ={mu:.2f}"},
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["μ"],
        )

    print("\n  📋 ASPETTATIVE:")
    print("     C6 → più veloce (μ=1.75), C1 → più lento (μ=1.45)")
    print("     Spread C1→C6: ~0.5-1.5s per giro")
    print("     Il compound calibrato (★) è il riferimento per la validazione")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 4 — SUSPENSION SWEEP
# ══════════════════════════════════════════════════════════════════════════════
def test_suspension_sweep():
    """
    Sospensioni variano su 5 livelli (molle + ARB + ride height).
    Fisso: aero=calibrato, compound=SOFT, fuel=20kg, ERS=quali, push=10.

    Aspettativa: setup ottimale → più veloce, setup estremo → penalità
    """
    print_header("BATTERIA 4 — SUSPENSION SWEEP  (Spring + ARB + RH)")

    # 5 livelli di sospensione: da rigida a morbida
    # Ogni livello: (delta_spring, delta_arb, delta_rh)
    SUSP_LEVELS = [
        ("Molto rigida  (Sp+10 ARB+5 RH-5)",  +10, +5, -5),
        ("Rigida        (Sp+5  ARB+3 RH-2)",   +5, +3, -2),
        ("Baseline ★    (calibrated)",            0,  0,  0),
        ("Morbida       (Sp-5  ARB-3 RH+2)",    -5, -3, +2),
        ("Molto morbida (Sp-10 ARB-5 RH+5)",   -10, -5, +5),
    ]

    for name, cfg in TEST_CIRCUITS.items():
        susp_base = SUSP_SETUPS[cfg["susp_source"]]
        rows = []
        for label, ds, da, drh in SUSP_LEVELS:
            sf = max(1.0, susp_base["spring_front"] + ds)
            sr = max(1.0, susp_base["spring_rear"] + ds)
            af = max(0.5, susp_base["arb_front"] + da)
            ar = max(0.5, susp_base["arb_rear"] + da)
            rhf = max(1.0, susp_base["ride_height_front"] + drh)
            rhr = max(1.0, susp_base["ride_height_rear"] + drh)

            # Build setup with custom suspension
            setup = PhysicsV4Setup(
                driver_data=REFERENCE_DRIVER,
                circuit=cfg["circuit_id"],
                session="qualifying",
            )
            setup.set_aero(
                front_wing=cfg["front_wing"],
                rear_wing=cfg["rear_wing"],
                bwing=cfg["bwing"],
            )
            setup.set_suspension(
                spring_front=sf, spring_rear=sr,
                ARB_front=af, ARB_rear=ar,
                ride_height_front=rhf, ride_height_rear=rhr,
            )
            setup.set_fuels(fuel_kg=cfg["fuel_kg"], fuel_mix="rich")
            setup.set_tyres(compound=cfg["compound"])
            setup.set_ers_mode("quali_deploy")

            r = setup.simulate_lap(verbose=False)
            rows.append((
                label,
                r["lap_time_s"],
                {
                    "Sp": f"Sp={sf:.0f}/{sr:.0f}",
                    "ARB": f"ARB={af:.0f}/{ar:.0f}",
                    "RH": f"RH={rhf:.0f}/{rhr:.0f}",
                },
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["Sp", "ARB", "RH"],
        )

    print("\n  📋 ASPETTATIVE:")
    print("     Baseline (calibrated) → più veloce o vicino al migliore")
    print("     Setup estremi → penalità per handling fuori finestra")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 5 — ICE / ERS MAPPING
# ══════════════════════════════════════════════════════════════════════════════
def test_ers_mapping():
    """
    ERS mode + ICE mode variano su 5 livelli.
    Fisso: aero=calibrato, compound=SOFT, fuel=20kg, susp=calibrata, push=10.

    Aspettativa: quali_deploy → più veloce, race_save → più lento
    """
    print_header("BATTERIA 5 — ICE / ERS MAPPING")

    ERS_LEVELS = [
        ("Quali Deploy ★ (max ERS)",  "quali_deploy", "aggressive"),
        ("Balanced       (std ERS)",  "balanced",     "balanced"),
        ("Race Save      (save ERS)", "race_save",    "balanced"),
        ("Practice       (min ERS)",   "practice",     "balanced"),
        ("Safety Car     (zero ERS)",  "safety_car",  "conservative"),
    ]

    for name, cfg in TEST_CIRCUITS.items():
        rows = []
        for label, ers_mode, ice_mode in ERS_LEVELS:
            setup = PhysicsV4Setup(
                driver_data=REFERENCE_DRIVER,
                circuit=cfg["circuit_id"],
                session="qualifying",
            )
            setup.set_aero(
                front_wing=cfg["front_wing"],
                rear_wing=cfg["rear_wing"],
                bwing=cfg["bwing"],
            )
            susp = SUSP_SETUPS[cfg["susp_source"]]
            setup.set_suspension(
                spring_front=susp["spring_front"],
                spring_rear=susp["spring_rear"],
                ARB_front=susp["arb_front"],
                ARB_rear=susp["arb_rear"],
                ride_height_front=susp["ride_height_front"],
                ride_height_rear=susp["ride_height_rear"],
            )
            setup.set_fuels(fuel_kg=cfg["fuel_kg"], fuel_mix="rich")
            setup.set_tyres(compound=cfg["compound"])
            setup.set_ers_mode(ers_mode)

            # Override ICE mode
            setup.car.power_unit.ice_mode = ice_mode

            r = setup.simulate_lap(verbose=False)
            rows.append((
                label,
                r["lap_time_s"],
                {"ERS": f"ERS={ers_mode}", "ICE": f"ICE={ice_mode}"},
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["ERS", "ICE"],
        )

    print("\n  📋 ASPETTATIVE:")
    print("     Quali Deploy → più veloce (4.0 MJ/lap)")
    print("     Safety Car → più lento (minimo deploy)")
    print("     Spread: ~1-3s tra quali e safety_car")


# ══════════════════════════════════════════════════════════════════════════════
# BATTERIA 6 — PUSH LEVEL
# ══════════════════════════════════════════════════════════════════════════════
def test_push_level():
    """
    Push level varia da 1 (conservativo) a 10 (qualifying).
    Fisso: aero=calibrato, compound=SOFT, fuel=20kg, susp=calibrata, ERS=quali.

    Aspettativa: push=10 → zero penalty, push=1 → massima penalità
    """
    print_header("BATTERIA 6 — PUSH LEVEL  (1 → 10)")

    PUSH_LEVELS = [
        ("Push 10 ★ (qualifying)",  10),
        ("Push 8  (aggressivo)",     8),
        ("Push 6  (neutrale)",       6),
        ("Push 4  (conservativo)",   4),
        ("Push 2  (molto conserv.)", 2),
    ]

    for name, cfg in TEST_CIRCUITS.items():
        rows = []
        for label, push in PUSH_LEVELS:
            r = simulate_lap(
                circuit_id=cfg["circuit_id"],
                front_wing=cfg["front_wing"],
                rear_wing=cfg["rear_wing"],
                bwing=cfg["bwing"],
                susp_source=cfg["susp_source"],
                compound=cfg["compound"],
                fuel_kg=cfg["fuel_kg"],
                push_level=push,
            )
            rows.append((
                label,
                r["lap_time_s"],
                {"Push": f"Push={push}"},
            ))

        print_table(
            name.upper(), rows, cfg["ref_time"],
            extra_headers=["Push"],
        )

    print("\n  📋 ASPETTATIVE:")
    print("     Push 10 → zero penalty (baseline qualifica)")
    print("     Push 2  → ~1-3s penalty (guida conservativa)")
    print("     Penalità crescente al diminuire del push level")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
TESTS = {
    "aero":       ("Aero Sweep",    test_aero_sweep),
    "fuel":      ("Fuel Load",     test_fuel_load),
    "tyres":     ("Tyre Compound", test_tyre_compound),
    "suspension": ("Suspension",   test_suspension_sweep),
    "ers":       ("ICE/ERS Map",   test_ers_mapping),
    "push":      ("Push Level",    test_push_level),
}


def main():
    if len(sys.argv) < 2:
        print("Uso: python setup_sensitivity_v56.py <test_name>")
        print(f"Test disponibili: {', '.join(TESTS.keys())}, all")
        sys.exit(1)

    test_name = sys.argv[1].lower()

    if test_name == "all":
        for key, (label, fn) in TESTS.items():
            fn()
    elif test_name in TESTS:
        label, fn = TESTS[test_name]
        fn()
    else:
        print(f"Test '{test_name}' non trovato. Disponibili: {', '.join(TESTS.keys())}, all")
        sys.exit(1)


if __name__ == "__main__":
    main()