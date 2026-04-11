#!/usr/bin/env python3
"""
Circuit Setup Sweep — Physics V4
=================================
Verifica che il motore fisico reagisca correttamente a setup diversi
su qualsiasi circuito supportato.

Esegue 5 preset dal migliore al peggiore per il circuito selezionato
e confronta: tempo giro, CLA/CDA, Vmax, qualità settori.

Uso:
    python circuit_setup_sweep.py monza
    python circuit_setup_sweep.py monaco
    python circuit_setup_sweep.py monaco --detail
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup           # noqa: E402
from lap_simulator.physics_v4.core.team_driver_data import (                 # noqa: E402
    get_team_data, get_driver_data,
)

TEAM   = "mclaren"
DRIVER = "Lando Norris"

# ─────────────────────────────────────────────────────────────────────────────
# PRESET PER CIRCUITO
#
# Ogni circuito ha 5 preset ordinati dal migliore al peggiore.
# front_wing / rear_wing : angolo ala in gradi (0-45°)
# spring_front/rear      : slider rigidità sospensioni (1-30)
# arb_front/rear         : slider ARB (1-10)
# compound               : mescola gomme (es. C3, C5, C6...)
# fuel_kg                : kg carburante
# ers_mode               : quali_deploy | balanced | race_save
# ─────────────────────────────────────────────────────────────────────────────
CIRCUIT_CONFIGS: Dict[str, Dict] = {

    # ── MONZA ──────────────────────────────────────────────────────────────
    # Circuito ad alta velocità: bassa resistenza aerodinamica, ali minime.
    # Compounds: Hard=C3  Medium=C4  Soft=C5
    "monza": {
        "circuit_id":   "it-1922_monza",
        "circuit_name": "Monza",
        "presets": [
            {
                "label": "Ottimale (Monza quali)",
                "desc":  "Ali minime, C5 soft, 20kg, ERS max",
                "front_wing": 8.0,  "rear_wing": 10.0,
                "spring_front": 18.0, "spring_rear": 22.0,
                "arb_front": 5.0, "arb_rear": 7.0,
                "compound": "C5", "fuel_kg": 20.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Buono",
                "desc":  "Ali basse-medie, C5 soft, 25kg",
                "front_wing": 12.0, "rear_wing": 15.0,
                "spring_front": 15.0, "spring_rear": 18.0,
                "arb_front": 4.0, "arb_rear": 6.0,
                "compound": "C5", "fuel_kg": 25.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Neutro",
                "desc":  "Ali medie, C4 medium, 40kg, ERS bilanciato",
                "front_wing": 20.0, "rear_wing": 22.0,
                "spring_front": 12.0, "spring_rear": 15.0,
                "arb_front": 4.0, "arb_rear": 5.0,
                "compound": "C4", "fuel_kg": 40.0, "ers_mode": "balanced",
            },
            {
                "label": "Ali Alte (subottimale)",
                "desc":  "Troppo downforce per Monza, C4, 60kg",
                "front_wing": 30.0, "rear_wing": 32.0,
                "spring_front": 8.0, "spring_rear": 10.0,
                "arb_front": 2.0, "arb_rear": 3.0,
                "compound": "C4", "fuel_kg": 60.0, "ers_mode": "balanced",
            },
            {
                "label": "Pessimo (Monaco su Monza)",
                "desc":  "Ali Monaco, C3 hard, 80kg, ERS risparmio",
                "front_wing": 40.0, "rear_wing": 42.0,
                "spring_front": 5.0, "spring_rear": 6.0,
                "arb_front": 1.0, "arb_rear": 2.0,
                "compound": "C3", "fuel_kg": 80.0, "ers_mode": "race_save",
            },
        ],
    },

    # ── MONACO ─────────────────────────────────────────────────────────────
    # Circuito cittadino: massimo downforce, massimo grip, bump management.
    # Compounds: Hard=C4  Medium=C5  Soft=C6
    "monaco": {
        "circuit_id":   "mc-1929_monaco",
        "circuit_name": "Monaco",
        "presets": [
            {
                "label": "Ottimale (Monaco quali)",
                "desc":  "Ali max, C6 soft, 20kg, ERS max",
                "front_wing": 38.0, "rear_wing": 42.0,
                "spring_front": 22.0, "spring_rear": 24.0,
                "arb_front": 7.0, "arb_rear": 8.0,
                "compound": "C6", "fuel_kg": 20.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Buono",
                "desc":  "Ali alte, C6 soft, 25kg",
                "front_wing": 32.0, "rear_wing": 36.0,
                "spring_front": 18.0, "spring_rear": 20.0,
                "arb_front": 6.0, "arb_rear": 7.0,
                "compound": "C6", "fuel_kg": 25.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Neutro",
                "desc":  "Ali medie, C5 medium, 40kg, ERS bilanciato",
                "front_wing": 24.0, "rear_wing": 28.0,
                "spring_front": 14.0, "spring_rear": 16.0,
                "arb_front": 4.0, "arb_rear": 5.0,
                "compound": "C5", "fuel_kg": 40.0, "ers_mode": "balanced",
            },
            {
                "label": "Ali Basse (subottimale)",
                "desc":  "Poco downforce per Monaco, C5, 60kg",
                "front_wing": 14.0, "rear_wing": 16.0,
                "spring_front": 8.0, "spring_rear": 10.0,
                "arb_front": 3.0, "arb_rear": 4.0,
                "compound": "C5", "fuel_kg": 60.0, "ers_mode": "balanced",
            },
            {
                "label": "Pessimo (Monza su Monaco)",
                "desc":  "Ali Monza, C4 hard, 80kg, ERS risparmio",
                "front_wing": 8.0, "rear_wing": 10.0,
                "spring_front": 5.0, "spring_rear": 6.0,
                "arb_front": 2.0, "arb_rear": 3.0,
                "compound": "C4", "fuel_kg": 80.0, "ers_mode": "race_save",
            },
        ],
    },

    # ── SUZUKA ─────────────────────────────────────────────────────────────
    # Circuito ALTO DOWNFORCE (4/5): S-Curves veloci, 130R, hairpin lento.
    # Il rettilineo principale (~800m) non è abbastanza lungo per premiare il basso carico.
    # Setup ottimale: FW=28-36°, RW=32-40° (alto carico, come in F1 reale).
    # Compounds: Hard=C1  Medium=C2  Soft=C3
    # 7 preset: da iper carico (Monaco-style) a iper scarico (Monza-style)
    "suzuka": {
        "circuit_id":   "jp-1962_suzuka",
        "circuit_name": "Suzuka",
        "presets": [
            {
                "label": "Iper Carico (Monaco-style)",
                "desc":  "Troppa downforce per i rettilinei, C3, 20kg, ERS max",
                "front_wing": 36.0, "rear_wing": 40.0,
                "spring_front": 20.0, "spring_rear": 24.0,
                "arb_front": 6.0, "arb_rear": 7.0,
                "compound": "C3", "fuel_kg": 20.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Ottimale (Suzuka quali)",
                "desc":  "Ali medie-alte per S-Curves, C3 soft, 20kg, ERS max",
                "front_wing": 24.0, "rear_wing": 28.0,
                "spring_front": 16.0, "spring_rear": 20.0,
                "arb_front": 5.0, "arb_rear": 6.0,
                "compound": "C3", "fuel_kg": 20.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Buono",
                "desc":  "Ali medie, C3 soft, 25kg",
                "front_wing": 20.0, "rear_wing": 24.0,
                "spring_front": 14.0, "spring_rear": 18.0,
                "arb_front": 4.0, "arb_rear": 5.0,
                "compound": "C3", "fuel_kg": 25.0, "ers_mode": "quali_deploy",
            },
            {
                "label": "Neutro",
                "desc":  "Ali medie, C2 medium, 40kg, ERS bilanciato",
                "front_wing": 20.0, "rear_wing": 22.0,
                "spring_front": 12.0, "spring_rear": 15.0,
                "arb_front": 4.0, "arb_rear": 5.0,
                "compound": "C2", "fuel_kg": 40.0, "ers_mode": "balanced",
            },
            {
                "label": "Ali Basse (subottimale)",
                "desc":  "Poco downforce per S-Curves, C2, 60kg",
                "front_wing": 12.0, "rear_wing": 14.0,
                "spring_front": 8.0, "spring_rear": 10.0,
                "arb_front": 3.0, "arb_rear": 4.0,
                "compound": "C2", "fuel_kg": 60.0, "ers_mode": "balanced",
            },
            {
                "label": "Iper Scarico (Monza-style)",
                "desc":  "Ali minime, nessun downforce per curve, C2, 40kg",
                "front_wing": 6.0, "rear_wing": 8.0,
                "spring_front": 6.0, "spring_rear": 8.0,
                "arb_front": 2.0, "arb_rear": 3.0,
                "compound": "C2", "fuel_kg": 40.0, "ers_mode": "balanced",
            },
            {
                "label": "Pessimo",
                "desc":  "Ali Monza, C1 hard, 80kg, ERS risparmio",
                "front_wing": 6.0, "rear_wing": 8.0,
                "spring_front": 5.0, "spring_rear": 6.0,
                "arb_front": 2.0, "arb_rear": 3.0,
                "compound": "C1", "fuel_kg": 80.0, "ers_mode": "race_save",
            },
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _load_telemetry(circuit_id: str) -> Dict:
    path = ROOT / "data" / "circuits" / "2025" / f"{circuit_id}_Telemetry.json"
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
    ok = warn = bad = 0
    for sec in macro_sectors:
        ref     = sec["dt_ref_s"]
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
        ref     = sec["dt_ref_s"]
        start_t = _interpolate(telemetry, sec["start_m"], "time_s")
        end_t   = _interpolate(telemetry, sec["end_m"],   "time_s")
        sim_dt  = max(end_t - start_t, 0.0)
        delta   = sim_dt - ref
        pct     = delta / ref * 100 if ref > 0 else 0.0
        v_in    = _interpolate(telemetry, sec["start_m"], "velocity_kph")
        v_out   = _interpolate(telemetry, sec["end_m"],   "velocity_kph")
        lines.append(
            f"  {sec['id']:<7} {sec['name']:<22} {ref:>7.3f}s │"
            f" {sim_dt:>7.3f}s │ {delta:>+7.3f}s │ {pct:>+6.2f}% │"
            f" {sec['v_entry_kph']:>7.1f} {v_in:>7.1f} │"
            f" {sec['v_exit_kph']:>8.1f} {v_out:>8.1f}  {_flag(pct)}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# SIMULAZIONE
# ─────────────────────────────────────────────────────────────────────────────
def simulate_preset(circuit_id: str, preset: Dict) -> Dict:
    cfg = PhysicsV4Setup(
        team_data   = get_team_data(TEAM),
        driver_data = get_driver_data(DRIVER),
        circuit     = circuit_id,
        session     = "qualifying",
    )
    cfg.set_aero(front_wing=preset["front_wing"], rear_wing=preset["rear_wing"])
    cfg.set_suspension(
        spring_front=preset["spring_front"], spring_rear=preset["spring_rear"],
        ARB_front=preset["arb_front"],       ARB_rear=preset["arb_rear"],
    )
    cfg.set_tyres(compound=preset["compound"])
    cfg.set_fuels(fuel_kg=preset["fuel_kg"])
    cfg.set_ers_mode(preset["ers_mode"])

    result = cfg.simulate_lap(verbose=False)
    aero   = result.get("setup", {}).get("aero", {})
    return {
        "preset":     preset,
        "lap_time_s": result["lap_time_s"],
        "cla":        aero.get("cla_total", 0.0),
        "cda":        aero.get("cda_total", 0.0),
        "v_max_kph":  result.get("v_max_kph", 0.0),
        "telemetry":  result["telemetry"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
def print_summary_table(circuit_name: str, results: List[Dict], ref_time: float, ref_driver: str) -> None:
    print()
    print("╔" + "═" * 115 + "╗")
    print(f"║  {circuit_name.upper()} SETUP SWEEP ─ Physics V4 ─ McLaren / Lando Norris{' ' * (57 - len(circuit_name))}║")
    print(f"║  Riferimento telemetria: {ref_driver} {ref_time:.3f}s{' ' * (82 - len(ref_driver))}║")
    print("╚" + "═" * 115 + "╝")
    print()

    hdr = (
        f"  {'#':<2} {'Setup':<35} {'FW':>4} {'RW':>4} │"
        f" {'CLA':>6} {'CDA':>6} │"
        f" {'Gomma':>6} {'Fuel':>5} {'ERS':<15} │"
        f" {'Sim':>8}s │ {'Δ':>7}s │ {'Δ%':>6} │"
        f" {'Vmax':>6} │  {'OK/W/B':>8}"
    )
    print(hdr)
    print("  " + "─" * 115)

    best_time = min(r["lap_time_s"] for r in results)
    ERS_LABEL = {"quali_deploy": "quali ERS max  ", "balanced": "balanced       ", "race_save": "race save      "}

    for i, r in enumerate(results, 1):
        p       = r["preset"]
        lap     = r["lap_time_s"]
        delta   = lap - ref_time
        pct     = delta / ref_time * 100
        flag    = _flag(pct)
        is_best = " ★" if abs(lap - best_time) < 0.001 else "  "
        ok, warn, bad = r["sector_stats"]
        print(
            f"  {i:<2} {p['label']:<35} {p['front_wing']:>4.0f}° {p['rear_wing']:>3.0f}° │"
            f" {r['cla']:>6.3f} {r['cda']:>6.3f} │"
            f" {p['compound']:>6} {p['fuel_kg']:>4.0f}kg {ERS_LABEL.get(p['ers_mode'], p['ers_mode'][:15])} │"
            f" {lap:>8.3f}s │ {delta:>+7.3f}s │ {pct:>+6.2f}% │"
            f" {r['v_max_kph']:>6.1f} │  {ok:2d}/{warn:2d}/{bad:2d}{is_best} {flag}"
        )

    print("  " + "─" * 115)
    print()
    print("  ★ = miglior tempo simulato   ✅<2%  🟡2-5%  🟠5-8%  🔴>8%")
    print()


def print_preset_detail(r: Dict, macro_sectors: List[Dict], ref_time: float) -> None:
    p     = r["preset"]
    delta = r["lap_time_s"] - ref_time
    pct   = delta / ref_time * 100
    print(f"\n  ┌─ {p['label']} — {p['desc']}")
    print(f"  │  FW={p['front_wing']:.0f}° RW={p['rear_wing']:.0f}°  "
          f"CLA={r['cla']:.3f} CDA={r['cda']:.3f}  "
          f"Gomma={p['compound']}  Fuel={p['fuel_kg']:.0f}kg  ERS={p['ers_mode']}")
    print(f"  │  Lap: {r['lap_time_s']:.3f}s  (rif {ref_time:.3f}s  Δ {delta:+.3f}s  {pct:+.2f}%)"
          f"  Vmax={r['v_max_kph']:.1f} kph")
    print()
    print(_sector_table(macro_sectors, r["telemetry"]))
    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main(circuit_key: str, detail: bool = False) -> None:
    if circuit_key not in CIRCUIT_CONFIGS:
        available = list(CIRCUIT_CONFIGS.keys())
        print(f"Circuito '{circuit_key}' non trovato. Disponibili: {available}")
        sys.exit(1)

    config       = CIRCUIT_CONFIGS[circuit_key]
    circuit_id   = config["circuit_id"]
    circuit_name = config["circuit_name"]
    presets      = config["presets"]

    tel_data      = _load_telemetry(circuit_id)
    macro_sectors = tel_data["geometry"]["sections"]
    ref_lap       = tel_data["reference_lap"]
    ref_time      = ref_lap["lap_time"]
    ref_driver    = ref_lap["driver"]

    print(f"\n  {circuit_name} Setup Sweep — {circuit_id}  |  ref: {ref_driver} {ref_time:.3f}s")
    print(f"  Eseguo {len(presets)} preset... ", end="", flush=True)

    results = []
    for preset in presets:
        r = simulate_preset(circuit_id, preset)
        r["sector_stats"] = _sector_stats(macro_sectors, r["telemetry"])
        results.append(r)
        print(".", end="", flush=True)

    print(" fatto.\n")

    print_summary_table(circuit_name, results, ref_time, ref_driver)

    if detail:
        print("\n" + "═" * 117)
        print(f"  DETTAGLIO SETTORI — {circuit_name.upper()}")
        print("═" * 117)
        for r in results:
            print_preset_detail(r, macro_sectors, ref_time)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Circuit Setup Sweep — verifica risposta fisica del motore su diversi circuiti",
    )
    parser.add_argument(
        "circuit",
        choices=list(CIRCUIT_CONFIGS.keys()),
        help="Circuito da testare",
    )
    parser.add_argument(
        "--detail", action="store_true",
        help="Stampa la tabella settori per ogni preset",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.circuit, detail=args.detail)
