#!/usr/bin/env python3
"""
Monza Setup Sweep — Physics V4
==============================
Verifica che il motore fisico reagisca correttamente a setup diversi su Monza.

Esegue 5 preset dall'ottimale al pessimo e confronta:
  - Tempo giro vs telemetria di riferimento
  - CLA / CDA effettivi (post modificatori McLaren)
  - Velocità massima (rettilineo principale)
  - Errore per settore (sintesi OK/warn/bad)

Composti Monza 2025:  Hard=C3  |  Medium=C4  |  Soft=C5

Uso:
    python monza_setup_sweep.py             # sweep completo (5 preset)
    python monza_setup_sweep.py --detail    # aggiunge tabella settori per ogni preset
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup           # noqa: E402
from lap_simulator.physics_engine.core.team_driver_data import (                 # noqa: E402
    get_team_data, get_driver_data,
)

# ─────────────────────────────────────────────────────────────────────────────
# COSTANTI
# ─────────────────────────────────────────────────────────────────────────────
CIRCUIT_ID   = "it-1922_monza"
CIRCUIT_NAME = "Monza"
TEAM         = "mclaren"
DRIVER       = "Lando Norris"

# Compounds Monza (da tyre_allocation nel Telemetry JSON)
HARD   = "C3"
MEDIUM = "C4"
SOFT   = "C5"

# ─────────────────────────────────────────────────────────────────────────────
# PRESET — da ottimale a pessimo per Monza
# ─────────────────────────────────────────────────────────────────────────────
#   front_wing / rear_wing  : gradi angolo ala  (0-45°)
#   spring_front/rear       : slider rigidità   (1-30)
#   arb_front/rear          : slider ARB        (1-10)
#   compound                : mescola gomme
#   fuel_kg                 : kg carburante
#   ers_mode                : quali_deploy | balanced | race_save
# ─────────────────────────────────────────────────────────────────────────────
PRESETS: List[Dict] = [
    {
        "id":           "p1_ottimale",
        "label":        "1 ─ Ottimale (Monza quali)",
        "desc":         "Ali minime, gomme soft, benzina Q, ERS max",
        "front_wing":    8.0,
        "rear_wing":    10.0,
        "spring_front": 18.0,
        "spring_rear":  22.0,
        "arb_front":     5.0,
        "arb_rear":      7.0,
        "compound":     SOFT,
        "fuel_kg":      20.0,
        "ers_mode":     "quali_deploy",
    },
    {
        "id":           "p2_buono",
        "label":        "2 ─ Buono",
        "desc":         "Ali basse-medie, soft, poco carburante",
        "front_wing":   12.0,
        "rear_wing":    15.0,
        "spring_front": 15.0,
        "spring_rear":  18.0,
        "arb_front":     4.0,
        "arb_rear":      6.0,
        "compound":     SOFT,
        "fuel_kg":      25.0,
        "ers_mode":     "quali_deploy",
    },
    {
        "id":           "p3_neutro",
        "label":        "3 ─ Neutro",
        "desc":         "Setup universale, medium, più benzina, ERS bilanciato",
        "front_wing":   20.0,
        "rear_wing":    22.0,
        "spring_front": 12.0,
        "spring_rear":  15.0,
        "arb_front":     4.0,
        "arb_rear":      5.0,
        "compound":     MEDIUM,
        "fuel_kg":      40.0,
        "ers_mode":     "balanced",
    },
    {
        "id":           "p4_ali_alte",
        "label":        "4 ─ Ali Alte (subottimale)",
        "desc":         "Troppo downforce per Monza, medium, carico gara",
        "front_wing":   30.0,
        "rear_wing":    32.0,
        "spring_front":  8.0,
        "spring_rear":  10.0,
        "arb_front":     2.0,
        "arb_rear":      3.0,
        "compound":     MEDIUM,
        "fuel_kg":      60.0,
        "ers_mode":     "balanced",
    },
    {
        "id":           "p5_pessimo",
        "label":        "5 ─ Pessimo (Monaco su Monza)",
        "desc":         "Ali Monaco, hard, serbatoio pieno, ERS risparmio",
        "front_wing":   40.0,
        "rear_wing":    42.0,
        "spring_front":  5.0,
        "spring_rear":   6.0,
        "arb_front":     1.0,
        "arb_rear":      2.0,
        "compound":     HARD,
        "fuel_kg":      80.0,
        "ers_mode":     "race_save",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _load_telemetry() -> Dict:
    path = ROOT / "data" / "circuits" / "2025" / f"{CIRCUIT_ID}_Telemetry.json"
    if not path.exists():
        raise FileNotFoundError(f"Telemetry non trovato: {path}")
    with open(path) as f:
        return json.load(f)


def _interpolate(trace: List[Dict], dist: float, key: str) -> float:
    if dist <= trace[0]["distance_m"]:
        return float(trace[0][key])
    if dist >= trace[-1]["distance_m"]:
        return float(trace[-1][key])
    for left, right in zip(trace, trace[1:]):
        if dist > right["distance_m"]:
            continue
        span = right["distance_m"] - left["distance_m"]
        if span <= 0.0:
            return float(right[key])
        frac = (dist - left["distance_m"]) / span
        return float(left[key]) + frac * (float(right[key]) - float(left[key]))
    return float(trace[-1][key])


def _sector_stats(macro_sectors: List[Dict], telemetry: List[Dict]) -> Tuple[int, int, int]:
    """Ritorna (ok, warn, bad) contando settori per fascia di errore."""
    ok = warn = bad = 0
    for sec in macro_sectors:
        ref = sec["dt_ref_s"]
        start_t = _interpolate(telemetry, sec["start_m"], "time_s")
        end_t   = _interpolate(telemetry, sec["end_m"],   "time_s")
        sim_dt  = max(end_t - start_t, 0.0)
        pct     = abs(sim_dt - ref) / ref * 100 if ref > 0 else 0.0
        if   pct < 2.0: ok   += 1
        elif pct < 5.0: warn += 1
        else:           bad  += 1
    return ok, warn, bad


def _flag(delta_pct: float) -> str:
    if   abs(delta_pct) >= 8.0: return "🔴"
    elif abs(delta_pct) >= 5.0: return "🟠"
    elif abs(delta_pct) >= 2.0: return "🟡"
    else:                       return "✅"


def _sector_table(macro_sectors: List[Dict], telemetry: List[Dict]) -> str:
    lines = []
    hdr = (
        f"  {'ID':<7} {'Nome':<22} {'dt_ref':>7}s │"
        f" {'dt_sim':>7}s │ {'Δ':>7}s │ {'Δ%':>6} │"
        f" {'vIn ref':>7} {'vIn sim':>7} │ {'vOut ref':>8} {'vOut sim':>8}"
    )
    lines.append(hdr)
    lines.append("  " + "─" * 100)

    for sec in macro_sectors:
        ref   = sec["dt_ref_s"]
        start_t = _interpolate(telemetry, sec["start_m"], "time_s")
        end_t   = _interpolate(telemetry, sec["end_m"],   "time_s")
        sim_dt  = max(end_t - start_t, 0.0)
        delta   = sim_dt - ref
        pct     = delta / ref * 100 if ref > 0 else 0.0
        flag    = _flag(pct)

        v_entry_sim = _interpolate(telemetry, sec["start_m"], "velocity_kph")
        v_exit_sim  = _interpolate(telemetry, sec["end_m"],   "velocity_kph")

        lines.append(
            f"  {sec['id']:<7} {sec['name']:<22} {ref:>7.3f}s │"
            f" {sim_dt:>7.3f}s │ {delta:>+7.3f}s │ {pct:>+6.2f}% │"
            f" {sec['v_entry_kph']:>7.1f} {v_entry_sim:>7.1f} │"
            f" {sec['v_exit_kph']:>8.1f} {v_exit_sim:>8.1f}  {flag}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# SIMULAZIONE
# ─────────────────────────────────────────────────────────────────────────────
def simulate_preset(preset: Dict) -> Dict:
    """Simula un preset completo con McLaren/Norris e ritorna un dict risultato."""
    team_data   = get_team_data(TEAM)
    driver_data = get_driver_data(DRIVER)

    cfg = PhysicsV4Setup(
        team_data=team_data,
        driver_data=driver_data,
        circuit=CIRCUIT_ID,
        session="qualifying",
    )

    cfg.set_aero(
        front_wing=preset["front_wing"],
        rear_wing=preset["rear_wing"],
    )
    cfg.set_suspension(
        spring_front=preset["spring_front"],
        spring_rear=preset["spring_rear"],
        ARB_front=preset["arb_front"],
        ARB_rear=preset["arb_rear"],
    )
    cfg.set_tyres(compound=preset["compound"])
    cfg.set_fuels(fuel_kg=preset["fuel_kg"])
    cfg.set_ers_mode(preset["ers_mode"])

    result = cfg.simulate_lap(verbose=False)

    aero    = result.get("setup", {}).get("aero", {})
    cla     = aero.get("cla_total", 0.0)
    cda     = aero.get("cda_total", 0.0)
    v_max   = result.get("v_max_kph", 0.0)

    return {
        "preset":     preset,
        "lap_time_s": result["lap_time_s"],
        "cla":        cla,
        "cda":        cda,
        "v_max_kph":  v_max,
        "telemetry":  result["telemetry"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
def print_summary_table(results: List[Dict], ref_time: float) -> None:
    print()
    print("╔" + "═" * 115 + "╗")
    print(f"║  MONZA SETUP SWEEP ─ Physics V4 ─ McLaren / Lando Norris{' ' * 57}║")
    print(f"║  Riferimento telemetria: {ref_time:.3f}s{' ' * 82}║")
    print("╚" + "═" * 115 + "╝")
    print()

    hdr = (
        f"  {'#':<2} {'Setup':<35} {'FW':>4} {'RW':>4} │"
        f" {'CLA':>6} {'CDA':>6} │"
        f" {'Gomma':>6} {'Fuel':>5} {'ERS':<15} │"
        f" {'Sim':>8}s │ {'Δ':>7}s │ {'Δ%':>6} │"
        f" {'Vmax':>6} │"
        f"  {'OK/W/B':>10}"
    )
    print(hdr)
    print("  " + "─" * 115)

    best_time = min(r["lap_time_s"] for r in results)

    for i, r in enumerate(results, 1):
        p         = r["preset"]
        lap       = r["lap_time_s"]
        delta     = lap - ref_time
        pct       = delta / ref_time * 100
        flag      = _flag(pct)
        is_best   = " ★" if abs(lap - best_time) < 0.001 else "  "

        ok, warn, bad = r["sector_stats"]
        sector_str = f"{ok:2d}/{warn:2d}/{bad:2d}"

        # Abbrevia label ERS
        ers_short = {"quali_deploy": "quali ERS max  ", "balanced": "balanced       ", "race_save": "race save      "}.get(p["ers_mode"], p["ers_mode"][:15])
        # Label corta (senza numero iniziale)
        label_short = p["label"][4:].strip()   # rimuove "N ─ "

        row = (
            f"  {i:<2} {label_short:<35} {p['front_wing']:>4.0f}° {p['rear_wing']:>3.0f}° │"
            f" {r['cla']:>6.3f} {r['cda']:>6.3f} │"
            f" {p['compound']:>6} {p['fuel_kg']:>4.0f}kg {ers_short} │"
            f" {lap:>8.3f}s │ {delta:>+7.3f}s │ {pct:>+6.2f}% │"
            f" {r['v_max_kph']:>6.1f} │"
            f"  {sector_str}{is_best} {flag}"
        )
        print(row)

    print("  " + "─" * 113)
    print()
    print("  ★ = miglior tempo simulato   ✅<2%  🟡2-5%  🟠5-8%  🔴>8%")
    print()


def print_preset_detail(r: Dict, macro_sectors: List[Dict], ref_time: float) -> None:
    p     = r["preset"]
    lap   = r["lap_time_s"]
    delta = lap - ref_time
    pct   = delta / ref_time * 100

    print(f"\n  ┌─ {p['label']} ─ {p['desc']}")
    print(f"  │  FW={p['front_wing']:.0f}° RW={p['rear_wing']:.0f}°  "
          f"CLA={r['cla']:.3f} CDA={r['cda']:.3f}  "
          f"Gomma={p['compound']}  Fuel={p['fuel_kg']:.0f}kg  ERS={p['ers_mode']}")
    print(f"  │  Lap: {lap:.3f}s  (rif {ref_time:.3f}s  Δ {delta:+.3f}s  {pct:+.2f}%)  "
          f"Vmax={r['v_max_kph']:.1f} kph")
    print()
    print(_sector_table(macro_sectors, r["telemetry"]))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(detail: bool = False) -> None:
    tel_data      = _load_telemetry()
    macro_sectors = tel_data["geometry"]["sections"]
    ref_time      = tel_data["reference_lap"]["lap_time"]
    ref_driver    = tel_data["reference_lap"]["driver"]

    print(f"\n  Monza Setup Sweep — circuito {CIRCUIT_ID}  |  ref: {ref_driver} {ref_time:.3f}s")
    print("  Eseguo 5 preset... ", end="", flush=True)

    results = []
    for preset in PRESETS:
        r = simulate_preset(preset)
        r["sector_stats"] = _sector_stats(macro_sectors, r["telemetry"])
        results.append(r)
        print(".", end="", flush=True)

    print(" fatto.\n")

    print_summary_table(results, ref_time)

    if detail:
        print("\n" + "═" * 117)
        print("  DETTAGLIO SETTORI PER OGNI PRESET")
        print("═" * 117)
        for r in results:
            print_preset_detail(r, macro_sectors, ref_time)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monza Setup Sweep — verifica risposta fisica del motore a diversi setup",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Stampa la tabella settori per ogni preset (output lungo)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(detail=args.detail)
