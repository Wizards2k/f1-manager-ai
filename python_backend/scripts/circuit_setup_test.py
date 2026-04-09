#!/usr/bin/env python3
"""
Circuit Setup Test - Physics V4

Testa 5 preset di assetto (da ottimale a terribile) su un circuito
e mostra una tabella comparativa di tempi giro, delta e parametri chiave.

I preset sono costruiti relativamente ai valori DefaultSetups del circuito:
  1. Ottimale   — DefaultSetups + SOFT + 20 kg + ERS quali_deploy
  2. Buono      — ali +3°       + MEDIUM     + 20 kg + ERS quali_deploy
  3. Medio      — ali +8°       + HARD       + 30 kg + ERS quali_deploy  (susp più morbide)
  4. Sbagliato  — ali +15°      + HARD       + 60 kg + ERS race_balanced (susp morbide)
  5. Terribile  — ali +25°      + HARD       + 80 kg + ERS race_save     (susp morbidissime)

Uso:
    python scripts/circuit_setup_test.py            # default: monza
    python scripts/circuit_setup_test.py monza
    python scripts/circuit_setup_test.py monaco
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ── path setup ──────────────────────────────────────────────────────────────
_HERE            = Path(__file__).resolve().parent          # .../scripts/
_PYTHON_BACKEND  = _HERE.parent                             # .../python_backend/
if str(_PYTHON_BACKEND) not in sys.path:
    sys.path.insert(0, str(_PYTHON_BACKEND))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.core.team_driver_data import get_team_data, get_driver_data
from lap_simulator.physics_v4.setup.default_setups import DefaultSetups


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
# LETTURA DATI CIRCUITO
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
    """Restituisce (hard, medium, soft) dal tyre_allocation del circuito."""
    try:
        data = load_telemetry(circuit_id)
        dry = data.get("tyre_allocation", {}).get("dry_compounds", {})
        hard   = dry.get("hard",   "C3")
        medium = dry.get("medium", "C4")
        soft   = dry.get("soft",   "C5")
    except FileNotFoundError:
        hard, medium, soft = "C3", "C4", "C5"
    return hard, medium, soft


def get_ref_lap_time(circuit_id: str) -> Tuple[float, str]:
    """Restituisce (lap_time_s, driver) dal file telemetria."""
    data = load_telemetry(circuit_id)
    ref  = data.get("reference_lap", {})
    return ref.get("lap_time", 0.0), ref.get("driver", "?")


# ──────────────────────────────────────────────────────────────────────────────
# COSTRUZIONE PRESET
# I preset sono definiti come delta rispetto ai valori DefaultSetups del circuito.
# ──────────────────────────────────────────────────────────────────────────────
def build_presets(defaults: Dict, hard: str, medium: str, soft: str) -> List[Dict]:
    """
    Costruisce 5 preset progressivamente degradanti a partire dal setup ottimale.

    defaults  — risultato di DefaultSetups.get_default_setup()
    hard/medium/soft — compound del circuito (es. C3/C4/C5 per Monza)
    """
    fw  = defaults["front_wing"]
    rw  = defaults["rear_wing"]
    sf  = defaults["front_suspension"]   # slider 1-30
    sr  = defaults["rear_suspension"]
    af  = defaults["front_arb"]          # slider 1-10
    ar  = defaults["rear_arb"]
    rh  = defaults["ride_height"]
    bb  = defaults["brake_bias"]

    return [
        # ── 1. OTTIMALE ───────────────────────────────────────────────────────
        {
            "label":         "1 · Ottimale",
            "description":   f"Default circuito + {soft} (SOFT) + 20 kg + ERS Q10",
            "front_wing":    fw,
            "rear_wing":     rw,
            "spring_front":  sf,
            "spring_rear":   sr,
            "arb_front":     af,
            "arb_rear":      ar,
            "ride_height":   rh,
            "brake_bias":    bb,
            "compound":      soft,
            "fuel_kg":       20.0,
            "ers_mode":      "quali_deploy",
        },
        # ── 2. BUONO ─────────────────────────────────────────────────────────
        {
            "label":         "2 · Buono",
            "description":   f"Ali +3° + {medium} (MEDIUM) + 20 kg + ERS Q10",
            "front_wing":    fw + 3,
            "rear_wing":     rw + 3,
            "spring_front":  sf,
            "spring_rear":   sr,
            "arb_front":     af,
            "arb_rear":      ar,
            "ride_height":   rh,
            "brake_bias":    bb,
            "compound":      medium,
            "fuel_kg":       20.0,
            "ers_mode":      "quali_deploy",
        },
        # ── 3. MEDIO ─────────────────────────────────────────────────────────
        {
            "label":         "3 · Medio",
            "description":   f"Ali +8° + {hard} (HARD) + 30 kg + ERS Q10 + susp -4",
            "front_wing":    fw + 8,
            "rear_wing":     rw + 8,
            "spring_front":  max(sf - 4, 1),
            "spring_rear":   max(sr - 4, 1),
            "arb_front":     max(af - 1.5, 1),
            "arb_rear":      max(ar - 1.5, 1),
            "ride_height":   rh + 10,
            "brake_bias":    bb,
            "compound":      hard,
            "fuel_kg":       30.0,
            "ers_mode":      "quali_deploy",
        },
        # ── 4. SBAGLIATO ─────────────────────────────────────────────────────
        {
            "label":         "4 · Sbagliato",
            "description":   f"Ali +15° + {hard} (HARD) + 60 kg + ERS gara + susp -8",
            "front_wing":    fw + 15,
            "rear_wing":     rw + 15,
            "spring_front":  max(sf - 8, 1),
            "spring_rear":   max(sr - 8, 1),
            "arb_front":     max(af - 2.5, 1),
            "arb_rear":      max(ar - 2.5, 1),
            "ride_height":   rh + 20,
            "brake_bias":    bb + 2,
            "compound":      hard,
            "fuel_kg":       60.0,
            "ers_mode":      "race_balanced",
        },
        # ── 5. TERRIBILE ─────────────────────────────────────────────────────
        {
            "label":         "5 · Terribile",
            "description":   f"Ali +25° + {hard} (HARD) + 80 kg + ERS save + susp min",
            "front_wing":    fw + 25,
            "rear_wing":     rw + 25,
            "spring_front":  max(sf - 14, 1),
            "spring_rear":   max(sr - 14, 1),
            "arb_front":     1.0,
            "arb_rear":      1.0,
            "ride_height":   rh + 35,
            "brake_bias":    bb + 4,
            "compound":      hard,
            "fuel_kg":       80.0,
            "ers_mode":      "race_save",
        },
    ]


# ──────────────────────────────────────────────────────────────────────────────
# SIMULAZIONE
# ──────────────────────────────────────────────────────────────────────────────
def simulate_preset(circuit_id: str, preset: Dict) -> Optional[Dict]:
    """
    Simula un giro con il preset dato su circuit_id.
    Usa sempre McLaren + Lando Norris.
    Ritorna il dizionario result di simulate_lap() o None in caso di errore.
    """
    team_data   = get_team_data("mclaren")
    driver_data = get_driver_data("Lando Norris")

    try:
        cfg = PhysicsV4Setup(
            team_data   = team_data,
            driver_data = driver_data,
            circuit     = circuit_id,
            session     = "qualifying",
        )

        cfg.set_aero(
            front_wing = preset["front_wing"],
            rear_wing  = preset["rear_wing"],
        )
        cfg.set_suspension(
            spring_front      = preset["spring_front"],
            spring_rear       = preset["spring_rear"],
            ARB_front         = preset["arb_front"],
            ARB_rear          = preset["arb_rear"],
            ride_height_front = preset["ride_height"],
            ride_height_rear  = preset["ride_height"],
        )
        cfg.set_brakes(bias_front=preset["brake_bias"])
        cfg.set_tyres(compound=preset["compound"])
        cfg.set_fuels(fuel_kg=preset["fuel_kg"])
        cfg.set_ers_mode(preset["ers_mode"])

        return cfg.simulate_lap(verbose=False)

    except Exception as exc:
        print(f"  ⚠  Errore simulazione [{preset['label']}]: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# REPORT
# ──────────────────────────────────────────────────────────────────────────────
def _flag(delta_pct: float) -> str:
    if   abs(delta_pct) >= 8.0: return "🔴"
    elif abs(delta_pct) >= 5.0: return "🟠"
    elif abs(delta_pct) >= 2.0: return "🟡"
    else:                       return "✅"


def run_test(circuit_key: str = "monza"):
    if circuit_key not in CIRCUITS:
        print(f"Circuito '{circuit_key}' non trovato. Disponibili: {list(CIRCUITS)}")
        sys.exit(1)

    circuit_id, circuit_name = CIRCUITS[circuit_key]

    # ── dati circuito ────────────────────────────────────────────────────────
    ref_time, ref_driver = get_ref_lap_time(circuit_id)
    hard, medium, soft   = get_compounds(circuit_id)
    defaults = DefaultSetups().get_default_setup(
        circuit_id, weather="dry", tire_compound=soft
    )

    # ── costruisci preset ────────────────────────────────────────────────────
    presets = build_presets(defaults, hard, medium, soft)

    # ── header ───────────────────────────────────────────────────────────────
    print()
    print("╔" + "═" * 110 + "╗")
    print(f"║  CIRCUIT SETUP TEST ─ {circuit_name:<20}  McLaren / Lando Norris{' ' * 27} ║")
    print("╚" + "═" * 110 + "╝")
    print(f"\n  Circuito:    {circuit_name}")
    print(f"  Riferimento: {ref_driver}  {ref_time:.3f}s")
    print(f"  Compounds:   HARD={hard}  MEDIUM={medium}  SOFT={soft}")
    print(f"  DefaultSetup: FW={defaults['front_wing']}° RW={defaults['rear_wing']}°  "
          f"Spring F={defaults['front_suspension']} R={defaults['rear_suspension']}  "
          f"ARB F={defaults['front_arb']} R={defaults['rear_arb']}")

    # ── esegui simulazioni ───────────────────────────────────────────────────
    results = []
    print()
    for p in presets:
        print(f"  Simulo {p['label']} ...", end="", flush=True)
        res = simulate_preset(circuit_id, p)
        results.append((p, res))
        if res:
            lt = res["lap_time_s"]
            delta = lt - ref_time
            pct   = delta / ref_time * 100
            print(f"  {lt:.3f}s  ({pct:+.2f}%)")
        else:
            print("  ERRORE")

    # ── tabella comparativa ──────────────────────────────────────────────────
    print()
    print("  " + "─" * 110)
    hdr = (
        f"  {'Setup':<18} {'Compound':<8} {'FW':>4} {'RW':>4} "
        f"{'SpF':>4} {'SpR':>4} {'AF':>4} {'AR':>4} "
        f"{'Fuel':>5} {'ERS':<15} "
        f"{'CLA':>6} {'CDA':>6} "
        f"{'Lap s':>7} {'Δ s':>7} {'Δ%':>7}  "
    )
    print(hdr)
    print("  " + "─" * 110)

    best_time = None
    for p, res in results:
        if res:
            lt = res["lap_time_s"]
            if best_time is None or lt < best_time:
                best_time = lt

    for p, res in results:
        if res is None:
            print(f"  {p['label']:<18}  {'ERRORE'}")
            continue

        lt      = res["lap_time_s"]
        delta   = lt - ref_time
        pct     = delta / ref_time * 100
        flag    = _flag(pct)
        aero    = res.get("setup", {}).get("aero", {})
        cla     = aero.get("cla_total", 0.0)
        cda     = aero.get("cda_total", 0.0)

        # marker tempo migliore
        best_mark = " ◀" if abs(lt - best_time) < 0.001 else "  "

        print(
            f"  {p['label']:<18} {p['compound']:<8} {p['front_wing']:>4.0f} {p['rear_wing']:>4.0f} "
            f"{p['spring_front']:>4.1f} {p['spring_rear']:>4.1f} {p['arb_front']:>4.1f} {p['arb_rear']:>4.1f} "
            f"{p['fuel_kg']:>5.0f} {p['ers_mode']:<15} "
            f"{cla:>6.3f} {cda:>6.3f} "
            f"{lt:>7.3f} {delta:>+7.3f} {pct:>+6.2f}%  {flag}{best_mark}"
        )

    print("  " + "─" * 110)

    # ── delta tra ottimale e terribile ───────────────────────────────────────
    res_ottimale  = results[0][1]
    res_terribile = results[-1][1]
    if res_ottimale and res_terribile:
        gap = res_terribile["lap_time_s"] - res_ottimale["lap_time_s"]
        print(f"\n  Δ Ottimale → Terribile:  {gap:+.3f}s  ({gap / res_ottimale['lap_time_s'] * 100:+.2f}%)")

    print()


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    circuit_key = sys.argv[1] if len(sys.argv) > 1 else "monza"
    run_test(circuit_key)
