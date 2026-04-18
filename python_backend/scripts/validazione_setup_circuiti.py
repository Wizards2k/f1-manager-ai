#!/usr/bin/env python3
"""
Validazione Setup Circuiti - Physics V4

Per ogni macro-settore confronta:
  - Tempo telemetria reale (dt_ref_s dal JSON HD)
  - Tempo calcolato dal motore fisico
  - Delta assoluto e percentuale
  - Velocità ingresso/uscita

Simula con setup completo: aero + sospensioni + gomme + benzina + ERS + McLaren/Norris.

Uso:
    python validazione_setup_circuiti.py                        # Monza + standard
    python validazione_setup_circuiti.py monza                  # solo circuito
    python validazione_setup_circuiti.py monaco high_wing       # circuito + preset assetto
"""

import sys
import json
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from lap_simulator.physics_v4.core.car_setup import PhysicsV4Setup
from lap_simulator.physics_v4.core.team_driver_data import get_team_data, get_driver_data
from lap_simulator.physics_v4.setup.default_setups import DefaultSetups


# ──────────────────────────────────────────────────
# MAPPA CIRCUITI
# ──────────────────────────────────────────────────
CIRCUITS = {
    "monza":       ("it-1922_monza",             "Monza"),
    "monaco":      ("mc-1929_monaco",            "Monaco"),
    "suzuka":      ("jp-1962_suzuka",            "Suzuka"),
    "silverstone": ("gb-1948_silverstone",       "Silverstone"),
    "spa":         ("be-1925_spa_francorchamps", "Spa"),
    "barcelona":   ("es-1991_barcelona",         "Barcelona"),
    "baku":        ("az-2016_baku",              "Baku"),
    "singapore":   ("sg-2008_singapore",         "Singapore"),
}

# ──────────────────────────────────────────────────
# PRESET ASSETTI
# Ogni preset definisce i parametri da passare a PhysicsV4Setup
# ──────────────────────────────────────────────────
SETUPS = {
    "standard": {
        "label":          "Standard (McLaren / Norris)",
        "front_wing":     20.0,
        "rear_wing":      22.0,
        "spring_front":   15.0,
        "spring_rear":    18.0,
        "arb_front":       4.0,
        "arb_rear":        6.0,
        "compound":       "C2",
        "pressure_front":  2.3,
        "pressure_rear":   2.1,
        "fuel_kg":        20.0,   # qualifica: poco carburante
        "ers_mode":       "quali_deploy",   # spinta 10 — ERS massimo
    },
    "low_wing": {
        "label":          "Ali Basse (Monza-style)",
        "front_wing":      8.0,
        "rear_wing":      10.0,
        "spring_front":   15.0,
        "spring_rear":    18.0,
        "arb_front":       4.0,
        "arb_rear":        6.0,
        "compound":       "C2",
        "pressure_front":  2.3,
        "pressure_rear":   2.1,
        "fuel_kg":        20.0,
        "ers_mode":       "quali_deploy",
    },
    "high_wing": {
        "label":          "Ali Alte (Monaco-style)",
        "front_wing":     38.0,
        "rear_wing":      40.0,
        "spring_front":   15.0,
        "spring_rear":    18.0,
        "arb_front":       4.0,
        "arb_rear":        6.0,
        "compound":       "C3",
        "pressure_front":  2.2,
        "pressure_rear":   2.0,
        "fuel_kg":        20.0,
        "ers_mode":       "quali_deploy",
    },
    "soft_susp": {
        "label":          "Sospensioni Morbide",
        "front_wing":     20.0,
        "rear_wing":      22.0,
        "spring_front":    5.0,
        "spring_rear":     8.0,
        "arb_front":       1.0,
        "arb_rear":        2.0,
        "compound":       "C2",
        "pressure_front":  2.3,
        "pressure_rear":   2.1,
        "fuel_kg":        20.0,
        "ers_mode":       "quali_deploy",
    },
    "terrible": {
        "label":          "Setup Terribile",
        "front_wing":      5.0,
        "rear_wing":       8.0,
        "spring_front":    5.0,
        "spring_rear":     8.0,
        "arb_front":       1.0,
        "arb_rear":        2.0,
        "compound":       "C6",
        "pressure_front":  1.8,
        "pressure_rear":   1.6,
        "fuel_kg":        80.0,   # gara: molto carburante
        "ers_mode":       "race_save",
    },
}


# ──────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────
def load_circuit_hd(circuit_id: str) -> Dict:
    base = Path(__file__).resolve().parent.parent / "data" / "circuits" / "2025"
    path = base / f"{circuit_id}_HD.json"
    if not path.exists():
        raise FileNotFoundError(f"File HD non trovato: {path}")
    with open(path) as f:
        return json.load(f)


def load_circuit_telemetry(circuit_id: str) -> Dict:
    """Carica il file Telemetry del circuito (geometry.sections come riferimento)."""
    base = Path(__file__).resolve().parent.parent / "data" / "circuits" / "2025"
    path = base / f"{circuit_id}_Telemetry.json"
    if not path.exists():
        raise FileNotFoundError(f"File Telemetry non trovato: {path}")
    with open(path) as f:
        return json.load(f)


def get_soft_compound(circuit_id: str) -> str:
    """Legge la mescola SOFT dal file telemetria del circuito."""
    base = Path(__file__).resolve().parent.parent / "data" / "circuits" / "2025"
    path = base / f"{circuit_id}_Telemetry.json"
    if not path.exists():
        return "C3"  # fallback generico
    with open(path) as f:
        data = json.load(f)
    return data.get("tyre_allocation", {}).get("dry_compounds", {}).get("soft", "C3")


def _interpolate_metric(trace: List[Dict], distance_m: float, key: str) -> float:
    """Interpola un valore dalla traccia telemetria a una distanza specifica."""
    if distance_m <= trace[0]["distance_m"]:
        return float(trace[0][key])
    if distance_m >= trace[-1]["distance_m"]:
        return float(trace[-1][key])

    for left, right in zip(trace, trace[1:]):
        left_d = left["distance_m"]
        right_d = right["distance_m"]
        if distance_m > right_d:
            continue
        span = right_d - left_d
        if span <= 0.0:
            return float(right[key])
        fraction = (distance_m - left_d) / span
        return float(left[key]) + fraction * (float(right[key]) - float(left[key]))

    return float(trace[-1][key])


def compute_sector_times_from_telemetry(
    macro_sectors: List[Dict],
    telemetry: List[Dict],
) -> List[Dict]:
    """
    Per ogni macro-settore calcola tempo e velocità dalla telemetria simulata.
    Usa interpolazione ai punti start_m/end_m (come monza_q_benchmark).
    """
    results = []
    for sec in macro_sectors:
        start_m = sec["start_m"]
        end_m = sec["end_m"]

        try:
            sim_start_t = _interpolate_metric(telemetry, start_m, "time_s")
            sim_end_t = _interpolate_metric(telemetry, end_m, "time_s")
            sim_dt = max(sim_end_t - sim_start_t, 0.0)
            sim_v_entry = _interpolate_metric(telemetry, start_m, "velocity_kph")
            sim_v_exit = _interpolate_metric(telemetry, end_m, "velocity_kph")

            # Min/max velocità dai waypoint nel range
            section_speeds = [
                wp["velocity_kph"]
                for wp in telemetry
                if start_m <= wp["distance_m"] <= end_m
            ]
            if not section_speeds:
                section_speeds = [sim_v_entry, sim_v_exit]
            sim_v_min = min(section_speeds)
            sim_v_max = max(section_speeds)

            results.append({
                "id":          sec["id"],
                "dt_sim_s":    sim_dt,
                "v_entry_sim": sim_v_entry,
                "v_exit_sim":  sim_v_exit,
                "v_min_sim":   sim_v_min,
                "v_max_sim":   sim_v_max,
            })
        except (IndexError, KeyError):
            results.append({"id": sec["id"], "dt_sim_s": None,
                            "v_entry_sim": None, "v_exit_sim": None,
                            "v_min_sim": None, "v_max_sim": None})
    return results


def error_flag(delta_pct: float) -> str:
    if   abs(delta_pct) >= 8.0: return "🔴"
    elif abs(delta_pct) >= 5.0: return "🟠"
    elif abs(delta_pct) >= 2.0: return "🟡"
    else:                       return "✅"


def kind_icon(kind: str) -> str:
    return "⚡" if "Straight" in kind else "↩️ "


# ──────────────────────────────────────────────────
# SIMULAZIONE CON SETUP COMPLETO
# ──────────────────────────────────────────────────
def simulate_with_setup(circuit_key: str, preset: Dict) -> tuple:
    """
    Simula usando PhysicsV4Setup completo (McLaren + Norris).
    La mescola SOFT viene letta dal file telemetria del circuito.
    Uses DefaultSetups for aero, suspension, and brakes (same as monza_q_benchmark).
    Returns: (result, soft_compound)
    """
    team_data   = get_team_data("mclaren")
    driver_data = get_driver_data("Lando Norris")

    circuit_id = CIRCUITS[circuit_key][0]

    # Mescola SOFT dal file telemetria
    soft_compound = get_soft_compound(circuit_id)

    # Get default setup from DefaultSetups (circuit + weather + compound merge)
    defaults = DefaultSetups().get_default_setup(
        circuit_id,
        weather="dry",
        tire_compound=soft_compound,
    )

    cfg = PhysicsV4Setup(
        team_data   = team_data,
        driver_data = driver_data,
        circuit     = circuit_id,
        session     = "qualifying",
    )

    # Aero: use DefaultSetups values (e.g., Monza = 10/12)
    cfg.set_aero(
        front_wing = defaults["front_wing"],
        rear_wing  = defaults["rear_wing"],
    )

    # Sospensioni: use DefaultSetups values (slider 1-30 / 1-10)
    cfg.set_suspension(
        spring_front = defaults["front_suspension"],
        spring_rear  = defaults["rear_suspension"],
        ARB_front    = defaults["front_arb"],
        ARB_rear     = defaults["rear_arb"],
        ride_height_front = defaults["ride_height"],
        ride_height_rear  = defaults["ride_height"],
    )

    # Brakes: use DefaultSetups values
    cfg.set_brakes(bias_front=defaults["brake_bias"])

    # Gomme: usa sempre la SOFT del circuito (qualifica)
    cfg.set_tyres(compound=soft_compound)

    # Fuel + ERS: già configurati da session="qualifying" (20kg, quali_deploy)

    return cfg.simulate_lap(verbose=False), soft_compound


# ──────────────────────────────────────────────────
# REPORT PRINCIPALE
# ──────────────────────────────────────────────────
def run_validation(circuit_key: str = "monza", setup_key: str = "standard"):
    if circuit_key not in CIRCUITS:
        print(f"Circuito '{circuit_key}' non trovato. Disponibili: {list(CIRCUITS)}")
        sys.exit(1)
    if setup_key not in SETUPS:
        print(f"Setup '{setup_key}' non trovato. Disponibili: {list(SETUPS)}")
        sys.exit(1)

    circuit_id, circuit_name = CIRCUITS[circuit_key]
    preset = SETUPS[setup_key]

    # Get default setup values for aero
    defaults = DefaultSetups().get_default_setup(
        circuit_id,
        weather="dry",
        tire_compound=get_soft_compound(circuit_id),
    )

    print()
    print("╔" + "═" * 108 + "╗")
    print(f"║  VALIDAZIONE SETUP ─ {circuit_name:<20}  Assetto: DefaultSetups (dry + SOFT){' ' * 14} ║")
    print("╚" + "═" * 108 + "╝")

    # Carica dati circuito (Telemetry per riferimenti, HD per waypoints)
    circuit_data  = load_circuit_hd(circuit_id)
    telemetry_data = load_circuit_telemetry(circuit_id)
    macro_sectors = telemetry_data["geometry"]["sections"]
    ref_lap_time  = telemetry_data["reference_lap"]["lap_time"]
    ref_driver    = telemetry_data["reference_lap"]["driver"]

    print(f"\n  Circuito:     {circuit_name}  ({circuit_data['total_length_m']:.0f} m)")
    print(f"  Telemetria:   {ref_driver}  ─  {ref_lap_time:.3f}s")
    print(f"  Team / Pilota: McLaren  /  Lando Norris")
    print(f"  Aero:         FW={defaults['front_wing']}°  RW={defaults['rear_wing']}°  (DefaultSetups)")
    print(f"  Sospensioni:  Spring F={defaults['front_suspension']} R={defaults['rear_suspension']}   ARB F={defaults['front_arb']} R={defaults['rear_arb']}  (DefaultSetups)")
    print(f"  Brakes:       Bias={defaults['brake_bias']}°  Ride Height={defaults['ride_height']}mm  (DefaultSetups)")
    print(f"  Benzina:      20 kg (qualifying)   ERS: quali_deploy")

    # Simula
    result, soft_compound = simulate_with_setup(circuit_key, preset)

    telemetry    = result["telemetry"]
    sim_lap_time = result["lap_time_s"]
    lap_delta    = sim_lap_time - ref_lap_time
    lap_delta_pct = lap_delta / ref_lap_time * 100

    # Recupera CLA/CDA effettivi usati (post modificatori McLaren + offset Norris)
    actual_setup = result.get("setup", {}).get("aero", {})
    print(f"  Gomma:        {soft_compound} (SOFT da tyre_allocation)")
    print(f"  CLA eff.:     {actual_setup.get('cla_total', '?'):.3f}   CDA eff.: {actual_setup.get('cda_total', '?'):.3f}  (incl. mod. McLaren + offset Norris)")

    # Calcola tempi settori dalla telemetria simulata
    sim_sectors = compute_sector_times_from_telemetry(macro_sectors, telemetry)
    sim_map = {s["id"]: s for s in sim_sectors}

    # ──────────────────────────────────────────────
    # TABELLA SETTORI
    # ──────────────────────────────────────────────
    print()
    hdr = (
        f"  {'ID':<7} {'T':<2} {'Nome':<22} {'Lung':>5}m │"
        f" {'dt_ref':>7}s │"
        f" {'dt_sim':>7}s │"
        f" {'Δ':>7}s │"
        f" {'Δ%':>6} │"
        f" {'vIn ref':>7} {'vIn sim':>7} │"
        f" {'vOut ref':>8} {'vOut sim':>8} │"
        f" {'vMin':>6} {'vMax':>6}  "
    )
    print(hdr)
    print("  " + "─" * 105)

    sector_ok = sector_warn = sector_bad = 0
    total_ref = total_sim = 0.0

    for sec in macro_sectors:
        sid  = sec["id"]
        sim  = sim_map.get(sid, {})
        dt_ref = sec["dt_ref_s"]
        dt_sim = sim.get("dt_sim_s")

        total_ref += dt_ref
        if dt_sim is not None:
            total_sim += dt_sim
            delta     = dt_sim - dt_ref
            delta_pct = delta / dt_ref * 100
            flag      = error_flag(delta_pct)

            if   abs(delta_pct) < 2: sector_ok   += 1
            elif abs(delta_pct) < 5: sector_warn  += 1
            else:                    sector_bad   += 1

            row = (
                f"  {sid:<7} {kind_icon(sec['kind']):<2} {sec['name']:<22} {sec['length_m']:>5.0f}m │"
                f" {dt_ref:>7.3f}s │"
                f" {dt_sim:>7.3f}s │"
                f" {delta:>+7.3f}s │"
                f" {delta_pct:>+6.2f}% │"
                f" {sec['v_entry_kph']:>7.1f} {sim['v_entry_sim']:>7.1f} │"
                f" {sec['v_exit_kph']:>8.1f} {sim['v_exit_sim']:>8.1f} │"
                f" {sim['v_min_sim']:>6.1f} {sim['v_max_sim']:>6.1f}  {flag}"
            )
        else:
            row = (
                f"  {sid:<7} {kind_icon(sec['kind']):<2} {sec['name']:<22} {sec['length_m']:>5.0f}m │"
                f" {dt_ref:>7.3f}s │  {'N/A':>7}  │  {'N/A':>7}  │  {'N/A':>6}  │"
                f" {'':>15} │ {'':>18} │ {'':>14}  ❓"
            )
        print(row)

    # ──────────────────────────────────────────────
    # RIGA TOTALI
    # ──────────────────────────────────────────────
    print("  " + "─" * 105)
    total_delta     = total_sim - total_ref
    total_delta_pct = total_delta / total_ref * 100

    print(
        f"  {'TOTALE':<7}    {'':22} {circuit_data['total_length_m']:>5.0f}m │"
        f" {total_ref:>7.3f}s │"
        f" {total_sim:>7.3f}s │"
        f" {total_delta:>+7.3f}s │"
        f" {total_delta_pct:>+6.2f}% │"
    )

    # ──────────────────────────────────────────────
    # SOMMARIO
    # ──────────────────────────────────────────────
    lap_flag   = error_flag(lap_delta_pct)
    total_secs = sector_ok + sector_warn + sector_bad

    print(f"\n  Tempo giro:   Telemetria {ref_lap_time:.3f}s  ─  Simulato {sim_lap_time:.3f}s  "
          f"  Δ {lap_delta:+.3f}s  ({lap_delta_pct:+.2f}%)  {lap_flag}")
    print(f"\n  Qualità:  ✅ {sector_ok}/{total_secs} (<2%)   🟡 {sector_warn}/{total_secs} (2-5%)   "
          f"🟠/🔴 {sector_bad}/{total_secs} (>5%)")

    # Top 5 peggiori settori
    worst = []
    for sec in macro_sectors:
        sim = sim_map.get(sec["id"], {})
        if sim.get("dt_sim_s") is not None:
            pct = (sim["dt_sim_s"] - sec["dt_ref_s"]) / sec["dt_ref_s"] * 100
            if abs(pct) >= 2.0:
                worst.append((abs(pct), pct, sec["id"], sec["name"]))

    if worst:
        worst.sort(reverse=True)
        print("\n  Settori con errore ≥ 2%:")
        for _, pct, sid, name in worst[:5]:
            print(f"    {error_flag(pct)}  {sid}  {name:<22}  {pct:+.2f}%")

    print()


# ──────────────────────────────────────────────────
if __name__ == "__main__":
    circuit_key = sys.argv[1] if len(sys.argv) > 1 else "monza"
    setup_key   = sys.argv[2] if len(sys.argv) > 2 else "standard"
    run_validation(circuit_key, setup_key)
