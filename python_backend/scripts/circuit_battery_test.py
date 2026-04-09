#!/usr/bin/env python3
"""
Circuit Battery Test - Physics V4

Tre batterie di test isolate — una variabile alla volta:

  BATTERIA 1 — Aero + Sospensioni
    Ali e sospensioni variano insieme (come in real F1: ali alte = susp morbide).
    Tutto il resto fisso: SOFT del circuito, 20 kg carburante, ERS quali_deploy.

  BATTERIA 2 — Peso / Carburante
    Carburante varia da qualifica (5 kg) a gara piena (110 kg).
    Tutto il resto fisso: DefaultSetups aero, SOFT, ERS quali_deploy.

  BATTERIA 3 — Mescole Gomme
    Compound varia sui tre del circuito (Hard, Medium, Soft) + C1 e C6 come estremi.
    Tutto il resto fisso: DefaultSetups aero, 20 kg, ERS quali_deploy.

Uso:
    python scripts/circuit_battery_test.py                # monza, tutte e tre le batterie
    python scripts/circuit_battery_test.py monaco
    python scripts/circuit_battery_test.py monza aero
    python scripts/circuit_battery_test.py monza fuel
    python scripts/circuit_battery_test.py monza tyres
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ── path setup ───────────────────────────────────────────────────────────────
_HERE           = Path(__file__).resolve().parent
_PYTHON_BACKEND = _HERE.parent
if str(_PYTHON_BACKEND) not in sys.path:
    sys.path.insert(0, str(_PYTHON_BACKEND))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.core.team_driver_data import get_team_data, get_driver_data
from lap_simulator.physics_v4.setup.default_setups import DefaultSetups

# ── costanti ERS ─────────────────────────────────────────────────────────────
_ERS_DEPLOY_MAX = 0.67   # MJ/km (full quali deploy = fraction 1.0)

# ──────────────────────────────────────────────────────────────────────────────
# MAPPA CIRCUITI
# ──────────────────────────────────────────────────────────────────────────────
CIRCUITS = {
    "monza":       ("it-1922_monza",             "Monza"),
    "monaco":      ("mc-1929_monaco",            "Monaco"),
    "suzuka":      ("jp-1962_suzuka",            "Suzuka"),
    "silverstone": ("gb-1948_silverstone",       "Silverstone"),
    "spa":         ("be-1925_spa_francorchamps", "Spa-Francorchamps"),
    "barcelona":   ("es-1991_barcelona",         "Barcelona"),
    "baku":        ("az-2016_baku",              "Baku"),
    "singapore":   ("sg-2008_singapore",         "Singapore"),
}

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS CIRCUITO
# ──────────────────────────────────────────────────────────────────────────────
def _data_dir() -> Path:
    return _PYTHON_BACKEND / "data" / "circuits" / "2025"


def load_telemetry(circuit_id: str) -> Dict:
    path = _data_dir() / f"{circuit_id}_Telemetry.json"
    if not path.exists():
        raise FileNotFoundError(f"Telemetry non trovato: {path}")
    with open(path) as f:
        return json.load(f)


def get_compounds(circuit_id: str) -> Tuple[str, str, str]:
    """(hard, medium, soft) dal tyre_allocation del circuito."""
    try:
        dry = load_telemetry(circuit_id).get("tyre_allocation", {}).get("dry_compounds", {})
        return dry.get("hard", "C3"), dry.get("medium", "C4"), dry.get("soft", "C5")
    except FileNotFoundError:
        return "C3", "C4", "C5"


def get_ref_lap(circuit_id: str) -> Tuple[float, str]:
    data = load_telemetry(circuit_id)
    ref  = data.get("reference_lap", {})
    return ref.get("lap_time", 0.0), ref.get("driver", "?")


# ──────────────────────────────────────────────────────────────────────────────
# SIMULAZIONE SINGOLA
# ──────────────────────────────────────────────────────────────────────────────
def simulate(circuit_id: str,
             front_wing: float, rear_wing: float,
             spring_front: float, spring_rear: float,
             arb_front: float, arb_rear: float,
             ride_height: float, brake_bias: float,
             compound: str,
             fuel_kg: float,
             ers_mode: str) -> Optional[Dict]:
    """Simula un giro completo con McLaren/Norris e i parametri dati."""
    try:
        cfg = PhysicsV4Setup(
            team_data   = get_team_data("mclaren"),
            driver_data = get_driver_data("Lando Norris"),
            circuit     = circuit_id,
            session     = "qualifying",
        )
        cfg.set_aero(front_wing=front_wing, rear_wing=rear_wing)
        cfg.set_suspension(
            spring_front      = spring_front,
            spring_rear       = spring_rear,
            ARB_front         = arb_front,
            ARB_rear          = arb_rear,
            ride_height_front = ride_height,
            ride_height_rear  = ride_height,
        )
        cfg.set_brakes(bias_front=brake_bias)
        cfg.set_tyres(compound=compound)
        cfg.set_fuels(fuel_kg=fuel_kg)
        cfg.set_ers_mode(ers_mode)
        return cfg.simulate_lap(verbose=False)
    except Exception as exc:
        print(f"  ⚠  Errore simulazione: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS OUTPUT
# ──────────────────────────────────────────────────────────────────────────────
def _flag(pct: float) -> str:
    a = abs(pct)
    if   a >= 8: return "🔴"
    elif a >= 5: return "🟠"
    elif a >= 2: return "🟡"
    return "✅"


def _section_header(title: str):
    print()
    print("  ┌─" + "─" * 100 + "─┐")
    print(f"  │  {title:<99}│")
    print("  └─" + "─" * 100 + "─┘")


def _run_battery(label: str, entries: List[Dict], ref_time: float,
                 circuit_id: str, col_headers: List[str], row_fn) -> List[Tuple]:
    """
    Esegue una batteria di test e stampa la tabella.
    entries: lista di dicts con i parametri per ogni run.
    row_fn(entry, result) → tuple di valori extra da stampare (oltre lap time e delta).
    """
    _section_header(label)
    print()

    results = []
    for e in entries:
        print(f"    {e['label']:<30} ...", end="", flush=True)
        res = simulate(circuit_id, **e["sim_params"])
        results.append((e, res))
        if res:
            lt  = res["lap_time_s"]
            pct = (lt - ref_time) / ref_time * 100
            print(f"  {lt:.3f}s  ({pct:+.2f}%)")
        else:
            print("  ERRORE")

    print()
    # Intestazione tabella
    extra_w = sum(len(h) + 2 for h in col_headers)
    sep = "  " + "─" * (95 + extra_w)
    print(sep)
    hdr_extra = "".join(f"  {h}" for h in col_headers)
    print(f"  {'Livello':<30} {'Lap s':>7} {'Δ s':>7} {'Δ vs ref':>9}{hdr_extra}")
    print(sep)

    base_time = None
    rows_data = []
    for e, res in results:
        if res:
            lt = res["lap_time_s"]
            if base_time is None:
                base_time = lt
            d_ref  = lt - ref_time
            d_base = lt - base_time
            pct    = d_ref / ref_time * 100
            flag   = _flag(pct)
            extra  = row_fn(e, res)
            rows_data.append((e["label"], lt, d_base, d_ref, pct, flag, extra))
        else:
            rows_data.append((e["label"], None, None, None, None, "❓", []))

    for label, lt, d_base, d_ref, pct, flag, extra in rows_data:
        if lt is None:
            print(f"  {label:<30}  ERRORE")
            continue
        extra_str = "".join(f"  {v}" for v in extra)
        best_mark = " ◀" if abs(d_base) < 0.001 else "  "
        print(
            f"  {label:<30} {lt:>7.3f} {d_base:>+7.3f} {d_ref:>+8.3f}s ({pct:>+5.2f}%)  "
            f"{flag}{best_mark}{extra_str}"
        )

    print(sep)
    # Delta totale tra primo e ultimo
    valid = [(lt, d_base) for _, lt, d_base, *_ in rows_data if lt is not None]
    if len(valid) >= 2:
        gap = valid[-1][0] - valid[0][0]
        print(f"\n    Δ primo → ultimo:  {gap:+.3f}s  ({gap / valid[0][0] * 100:+.2f}%)")

    return results


# ──────────────────────────────────────────────────────────────────────────────
# BATTERIA 1 — AERO + SOSPENSIONI
# ──────────────────────────────────────────────────────────────────────────────
def battery_aero(circuit_id: str, defaults: Dict, soft: str, ref_time: float):
    """
    Ali e sospensioni variano insieme su 5 livelli.
    Base: DefaultSetups del circuito.
    Fisso: SOFT, 20 kg, ERS quali_deploy.
    """
    fw = defaults["front_wing"]
    rw = defaults["rear_wing"]
    sf = defaults["front_suspension"]
    sr = defaults["rear_suspension"]
    af = defaults["front_arb"]
    ar = defaults["rear_arb"]
    rh = defaults["ride_height"]
    bb = defaults["brake_bias"]

    def p(label, dfw, drw, dsf, dsr, daf, dar, drh):
        return {
            "label": label,
            "sim_params": dict(
                front_wing   = max(1, fw + dfw),
                rear_wing    = max(1, rw + drw),
                spring_front = max(1, sf + dsf),
                spring_rear  = max(1, sr + dsr),
                arb_front    = max(0.5, af + daf),
                arb_rear     = max(0.5, ar + dar),
                ride_height  = max(20, rh + drh),
                brake_bias   = bb,
                compound     = soft,
                fuel_kg      = 20.0,
                ers_mode     = "quali_deploy",
            ),
        }

    entries = [
        p("1 · Ali min / Susp. rigide",  -4,  -4, +4, +4, +1.5, +1.5, -10),
        p("2 · Default circuito",          0,   0,  0,  0,  0,   0,     0),
        p("3 · Ali +6° / Susp. medie",   +6,  +6, -3, -3, -1,  -1,    +5),
        p("4 · Ali +14° / Susp. morbide",+14, +14, -7, -7, -2,  -2,   +15),
        p("5 · Ali +24° / Susp. min",    +24, +24,-14,-14, -3,  -3,   +25),
    ]

    def row_fn(e, res):
        aero = res.get("setup", {}).get("aero", {})
        sp   = e["sim_params"]
        return [
            f"FW={sp['front_wing']:.0f}° RW={sp['rear_wing']:.0f}°",
            f"Sp={sp['spring_front']:.0f}/{sp['spring_rear']:.0f}",
            f"ARB={sp['arb_front']:.1f}/{sp['arb_rear']:.1f}",
            f"CLA={aero.get('cla_total', 0):.3f}",
            f"CDA={aero.get('cda_total', 0):.3f}",
        ]

    _run_battery(
        "BATTERIA 1 — ALI + SOSPENSIONI  (compound=SOFT, fuel=20kg, ERS=Q10)",
        entries, ref_time, circuit_id,
        col_headers=["FW/RW", "Spring", "ARB", "CLA", "CDA"],
        row_fn=row_fn,
    )


# ──────────────────────────────────────────────────────────────────────────────
# BATTERIA 2 — PESO / CARBURANTE
# ──────────────────────────────────────────────────────────────────────────────
def battery_fuel(circuit_id: str, defaults: Dict, soft: str, ref_time: float):
    """
    Carburante varia da 5 kg (qualifica pura) a 110 kg (gara piena).
    Fisso: DefaultSetups aero, SOFT, ERS quali_deploy.
    """
    fw = defaults["front_wing"]
    rw = defaults["rear_wing"]
    sf = defaults["front_suspension"]
    sr = defaults["rear_suspension"]
    af = defaults["front_arb"]
    ar = defaults["rear_arb"]
    rh = defaults["ride_height"]
    bb = defaults["brake_bias"]

    def p(label, fuel_kg):
        return {
            "label": label,
            "sim_params": dict(
                front_wing   = fw,
                rear_wing    = rw,
                spring_front = sf,
                spring_rear  = sr,
                arb_front    = af,
                arb_rear     = ar,
                ride_height  = rh,
                brake_bias   = bb,
                compound     = soft,
                fuel_kg      = fuel_kg,
                ers_mode     = "quali_deploy",
            ),
        }

    entries = [
        p("1 · Qualifica pura    (5 kg)",    5.0),
        p("2 · Qualifica std    (20 kg)",   20.0),
        p("3 · Sprint / leggero (45 kg)",   45.0),
        p("4 · Gara media       (75 kg)",   75.0),
        p("5 · Gara piena      (110 kg)",  110.0),
    ]

    def row_fn(e, res):
        fuel = e["sim_params"]["fuel_kg"]
        mass = 798 + 80 + fuel  # massa approssimativa
        return [f"Fuel={fuel:.0f}kg", f"Massa≈{mass:.0f}kg"]

    _run_battery(
        "BATTERIA 2 — CARBURANTE / PESO  (compound=SOFT, aero=Default, ERS=Q10)",
        entries, ref_time, circuit_id,
        col_headers=["Fuel", "Massa"],
        row_fn=row_fn,
    )


# ──────────────────────────────────────────────────────────────────────────────
# BATTERIA 3 — MESCOLE GOMME
# ──────────────────────────────────────────────────────────────────────────────
def battery_tyres(circuit_id: str, defaults: Dict,
                  hard: str, medium: str, soft: str,
                  ref_time: float):
    """
    Compound varia su 5 livelli: C1 (assoluto duro) → Hard circuito → Medium → Soft → C6.
    Fisso: DefaultSetups aero, 20 kg, ERS quali_deploy.
    """
    fw = defaults["front_wing"]
    rw = defaults["rear_wing"]
    sf = defaults["front_suspension"]
    sr = defaults["rear_suspension"]
    af = defaults["front_arb"]
    ar = defaults["rear_arb"]
    rh = defaults["ride_height"]
    bb = defaults["brake_bias"]

    def p(label, compound):
        return {
            "label": label,
            "sim_params": dict(
                front_wing   = fw,
                rear_wing    = rw,
                spring_front = sf,
                spring_rear  = sr,
                arb_front    = af,
                arb_rear     = ar,
                ride_height  = rh,
                brake_bias   = bb,
                compound     = compound,
                fuel_kg      = 20.0,
                ers_mode     = "quali_deploy",
            ),
        }

    # Build 5 entries: C1 (estremo), Hard circuito, Medium, Soft, C6 (estremo)
    entries = [
        p(f"1 · C1  (mescola + dura)",   "C1"),
        p(f"2 · {hard}  (HARD circuito)", hard),
        p(f"3 · {medium}  (MEDIUM circuito)", medium),
        p(f"4 · {soft}  (SOFT circuito) ★", soft),
        p(f"5 · C6  (mescola + morbida)", "C6"),
    ]

    from lap_simulator.physics_v4.core.constants import MU_BASE
    def row_fn(e, res):
        compound = e["sim_params"]["compound"]
        mu = MU_BASE.get(compound, "?")
        return [f"μ={mu}"]

    _run_battery(
        f"BATTERIA 3 — MESCOLE GOMME  (aero=Default, fuel=20kg, ERS=Q10)  "
        f"[HARD={hard} MEDIUM={medium} SOFT={soft}]",
        entries, ref_time, circuit_id,
        col_headers=["μ base"],
        row_fn=row_fn,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
def run(circuit_key: str = "monza", battery: str = "all"):
    if circuit_key not in CIRCUITS:
        print(f"Circuito '{circuit_key}' non trovato. Disponibili: {list(CIRCUITS)}")
        sys.exit(1)

    circuit_id, circuit_name = CIRCUITS[circuit_key]
    ref_time, ref_driver      = get_ref_lap(circuit_id)
    hard, medium, soft        = get_compounds(circuit_id)
    defaults = DefaultSetups().get_default_setup(
        circuit_id, weather="dry", tire_compound=soft
    )

    # ── header ───────────────────────────────────────────────────────────────
    print()
    print("╔" + "═" * 104 + "╗")
    print(f"║  CIRCUIT BATTERY TEST ─ {circuit_name:<20}  McLaren / Lando Norris{' ' * 23} ║")
    print("╚" + "═" * 104 + "╝")
    print(f"\n  Circuito:     {circuit_name}")
    print(f"  Riferimento:  {ref_driver}  {ref_time:.3f}s  (telemetria)")
    print(f"  Compounds:    HARD={hard}  MEDIUM={medium}  SOFT={soft}")
    print(f"  DefaultSetup: FW={defaults['front_wing']}° RW={defaults['rear_wing']}°  "
          f"Spring F={defaults['front_suspension']} R={defaults['rear_suspension']}  "
          f"ARB F={defaults['front_arb']} R={defaults['rear_arb']}")

    run_all = (battery == "all")

    if run_all or battery == "aero":
        battery_aero(circuit_id, defaults, soft, ref_time)

    if run_all or battery == "fuel":
        battery_fuel(circuit_id, defaults, soft, ref_time)

    if run_all or battery == "tyres":
        battery_tyres(circuit_id, defaults, hard, medium, soft, ref_time)

    print()


if __name__ == "__main__":
    circuit_key = sys.argv[1] if len(sys.argv) > 1 else "monza"
    battery     = sys.argv[2] if len(sys.argv) > 2 else "all"
    run(circuit_key, battery)
