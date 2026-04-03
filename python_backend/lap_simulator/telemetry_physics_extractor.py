"""
Telemetry Physics Extractor — Estrai i parametri fisici reali da telemetria F1 2025

Source of Truth: Dati reali telemetria F1 2025 da più circuiti
Obiettivo: Identificare i pattern fisici reali per calibrare il motore

Approccio:
1. Carica telemetria da N circuiti diversi
2. Per ogni sezione, calcola parametri fisici derivati (accelerazione, drag, grip, etc.)
3. Identifica pattern per tipo di sezione (curva lenta, veloce, rettilineo, etc.)
4. Usa questi pattern come "vincoli" per calibrare il modello fisico
"""

import json
import os
from typing import Dict, List, Any, Optional
import math

# Circuiti disponibili in telemetria
CIRCUITS = [
    "it-1922_monza",
    "mc-1929_monaco",
    "jp-1962_suzuka",
    "gb-1950_silverstone",
    "be-1925_spa",
    "au-1953_albert_park",
    "us-2000_austin",
    "br-1972_interlagos",
    "ae-2009_yas_marina",
]

# Costanti fisiche
MASS_KG = 798.0
G = 9.81
RHO = 1.225
ROLLING_RESISTANCE_COEFF = 0.011
DRIVETRAIN_EFFICIENCY = 0.895


def load_telemetry(circuit_id: str) -> Optional[Dict[str, Any]]:
    """Carica telemetria JSON da circuito."""
    path = f"python_backend/data/circuits/2025/{circuit_id}_Telemetry.json"
    if not os.path.exists(path):
        print(f"⚠️  {path} non trovato")
        return None

    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Errore caricamento {circuit_id}: {e}")
        return None


def classify_section(section: Dict[str, Any]) -> str:
    """Classifica una sezione per tipo."""
    kind = section.get('kind', 'Unknown').lower()

    if 'straight' in kind:
        length = section.get('length_m', 0)
        if length < 200:
            return 'straight_short'
        elif length < 500:
            return 'straight_medium'
        else:
            return 'straight_long'

    if 'very_slow' in kind or 'slow' in kind:
        return 'corner_slow'
    elif 'medium' in kind:
        return 'corner_medium'
    elif 'fast' in kind or 'ultra_fast' in kind:
        return 'corner_fast'

    return 'unknown'


def extract_physics_params(section: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estrai parametri fisici da una sezione.

    Calcola (derivato da telemetria):
    - Accelerazione media (Δv / Δt)
    - G laterali (v²/R)
    - Drag stimato
    - Grip utilizzato
    - Potenza media richiesta
    """

    v_entry_kph = section.get('v_entry_kph', 0)
    v_exit_kph = section.get('v_exit_kph', 0)
    v_min_kph = section.get('v_min_kph', 0)
    v_max_kph = section.get('v_max_kph', 0)
    radius_m = section.get('radius_m', 0)
    length_m = section.get('length_m', 0)
    dt_ref_s = section.get('dt_ref_s', 0)
    braking_energy_mj = section.get('braking_energy_mj', 0)

    # Conversione a m/s
    v_entry_ms = v_entry_kph / 3.6
    v_exit_ms = v_exit_kph / 3.6
    v_min_ms = v_min_kph / 3.6
    v_max_ms = v_max_kph / 3.6

    # --- ACCELERAZIONE MEDIA ---
    if dt_ref_s > 0:
        dv_ms = v_exit_ms - v_entry_ms
        a_mean_ms2 = dv_ms / dt_ref_s
        a_mean_g = a_mean_ms2 / G
    else:
        a_mean_ms2 = 0.0
        a_mean_g = 0.0

    # --- G LATERALI (in curva) ---
    if radius_m and radius_m > 0.1 and v_min_ms > 0.1:
        # A velocità minima (apex), la laterale è massima
        a_lateral_apex_g = (v_min_ms ** 2) / (radius_m * G)
    else:
        a_lateral_apex_g = 0.0

    # --- DRAG STIMATO ---
    # Assumiamo drag medio sulla sezione
    # F_drag ≈ 0.5 * rho * v_avg² * CDA
    # Ma non sappiamo CDA, quindi stimiamo il drag totale da energia/lavoro
    if dt_ref_s > 0 and length_m > 0:
        # Potenza media = lavoro / tempo
        # Lavoro ≈ energia per mantener velocità contro drag
        avg_speed_ms = (v_entry_ms + v_exit_ms) / 2
        if avg_speed_ms > 1:
            # Stima drag da equazione movimento
            # a_net = (F_drive - F_drag) / m
            # F_drag ≈ F_drive - m * a_net

            # Se è un rettilineo, tutta la potenza va a vincere drag
            # Se è una curva, serve grip laterale

            power_required_estimated_w = braking_energy_mj * 1e6 / dt_ref_s if braking_energy_mj > 0 else 0
        else:
            power_required_estimated_w = 0
    else:
        power_required_estimated_w = 0

    # --- VELOCITÀ MEDIE ---
    if dt_ref_s > 0:
        # Stima velocità media da entry/exit (assumendo accel/decel lineare)
        v_avg_linear_ms = (v_entry_ms + v_exit_ms) / 2
    else:
        v_avg_linear_ms = 0

    params = {
        'section_name': section.get('name', 'Unknown'),
        'kind': section.get('kind', 'Unknown'),
        'section_type': classify_section(section),
        'length_m': length_m,
        'dt_s': dt_ref_s,
        'v_entry_kph': v_entry_kph,
        'v_exit_kph': v_exit_kph,
        'v_min_kph': v_min_kph,
        'v_max_kph': v_max_kph,
        'v_avg_kph': v_avg_linear_ms * 3.6,
        'dv_kph': v_exit_kph - v_entry_kph,
        'a_mean_g': a_mean_g,
        'a_mean_ms2': a_mean_ms2,
        'radius_m': radius_m,
        'a_lateral_apex_g': a_lateral_apex_g,
        'braking_energy_mj': braking_energy_mj,
        'power_required_w': power_required_estimated_w,
        'drs_active': section.get('drs_active', False),
    }

    return params


def main():
    print("="*100)
    print("TELEMETRY PHYSICS EXTRACTOR - Estrai parametri fisici reali")
    print("="*100)

    all_sections = []

    # Carica da tutti i circuiti
    for circuit_id in CIRCUITS:
        print(f"\n[Loading] {circuit_id}...")
        telemetry = load_telemetry(circuit_id)

        if not telemetry:
            continue

        sections = telemetry.get('geometry', {}).get('sections', [])
        print(f"  ✓ Caricati {len(sections)} sezioni")

        for section in sections:
            params = extract_physics_params(section)
            params['circuit_id'] = circuit_id
            all_sections.append(params)

    print(f"\n✓ Totale sezioni caricate: {len(all_sections)}")

    # --- ANALISI PER TIPO DI SEZIONE ---
    print("\n" + "="*100)
    print("ANALISI PER TIPO DI SEZIONE")
    print("="*100)

    section_types = {}
    for section in all_sections:
        stype = section['section_type']
        if stype not in section_types:
            section_types[stype] = []
        section_types[stype].append(section)

    for stype in sorted(section_types.keys()):
        sections = section_types[stype]
        print(f"\n[{stype.upper()}] - {len(sections)} sezioni")
        print("-" * 100)
        print(f"{'Circuit':<20} {'v_entry':<10} {'v_exit':<10} {'Δv':<8} {'a_mean':<10} {'a_lat':<10} {'radius':<10} {'drs':<5}")
        print("-" * 100)

        for s in sections[:10]:  # Primi 10 di ogni tipo
            drs = "✓" if s['drs_active'] else ""
            print(
                f"{s['section_name']:<20} "
                f"{s['v_entry_kph']:<10.1f} "
                f"{s['v_exit_kph']:<10.1f} "
                f"{s['dv_kph']:<8.1f} "
                f"{s['a_mean_g']:<10.2f}g "
                f"{s['a_lateral_apex_g']:<10.2f}g "
                f"{s['radius_m']:<10.1f} "
                f"{drs:<5}"
            )

        # Stats
        avg_a_mean = sum(s['a_mean_g'] for s in sections) / len(sections) if sections else 0
        avg_a_lat = sum(s['a_lateral_apex_g'] for s in sections) / len(sections) if sections else 0
        avg_dv = sum(s['dv_kph'] for s in sections) / len(sections) if sections else 0

        print(f"\n  Stats:")
        print(f"    Δv medio:        {avg_dv:+.1f} km/h")
        print(f"    a_mean medio:    {avg_a_mean:.2f}g")
        print(f"    a_lat medio:     {avg_a_lat:.2f}g (se curva)")

    # --- SEZIONI CRITICHE PER CALIBRAZIONE ---
    print("\n" + "="*100)
    print("SEZIONI CRITICHE PER CALIBRAZIONE")
    print("="*100)

    # 1. Rettilineo lungo con DRS (velocità massima)
    straights_long_drs = [s for s in all_sections if s['section_type'] == 'straight_long' and s['drs_active']]
    if straights_long_drs:
        print("\n[1] RETTILINEO LUNGO + DRS (test potenza massima)")
        s = max(straights_long_drs, key=lambda x: x['v_exit_kph'])
        print(f"    Circuito: {s['circuit_id']} - {s['section_name']}")
        print(f"    v_entry: {s['v_entry_kph']:.1f} km/h")
        print(f"    v_exit:  {s['v_exit_kph']:.1f} km/h")
        print(f"    Δv:      {s['dv_kph']:+.1f} km/h in {s['dt_s']:.2f}s")
        print(f"    Lunghezza: {s['length_m']:.0f} m")
        print(f"    a_mean:  {s['a_mean_g']:.3f}g")

    # 2. Curva lenta (test grip massimo)
    corners_slow = [s for s in all_sections if s['section_type'] == 'corner_slow']
    if corners_slow:
        print("\n[2] CURVA LENTA (test grip massimo)")
        s = max(corners_slow, key=lambda x: x['a_lateral_apex_g'])
        print(f"    Circuito: {s['circuit_id']} - {s['section_name']}")
        print(f"    v_entry: {s['v_entry_kph']:.1f} km/h")
        print(f"    v_min:   {s['v_min_kph']:.1f} km/h (apex)")
        print(f"    v_exit:  {s['v_exit_kph']:.1f} km/h")
        print(f"    radius:  {s['radius_m']:.1f} m")
        print(f"    a_lat:   {s['a_lateral_apex_g']:.3f}g")
        print(f"    Lunghezza: {s['length_m']:.0f} m")

    # 3. Frenata massima
    sections_brake = [s for s in all_sections if s['braking_energy_mj'] > 2.0]
    if sections_brake:
        print("\n[3] FRENATA MASSIMA (test braking)")
        s = max(sections_brake, key=lambda x: abs(x['a_mean_g']))
        print(f"    Circuito: {s['circuit_id']} - {s['section_name']}")
        print(f"    v_entry: {s['v_entry_kph']:.1f} km/h")
        print(f"    v_exit:  {s['v_exit_kph']:.1f} km/h")
        print(f"    a_mean:  {s['a_mean_g']:.3f}g (decelerazione)")
        print(f"    Energia frenata: {s['braking_energy_mj']:.2f} MJ")

    # 4. Curva veloce
    corners_fast = [s for s in all_sections if s['section_type'] == 'corner_fast']
    if corners_fast:
        print("\n[4] CURVA VELOCE (test grip a alta velocità)")
        s = corners_fast[0]
        print(f"    Circuito: {s['circuit_id']} - {s['section_name']}")
        print(f"    v_entry: {s['v_entry_kph']:.1f} km/h")
        print(f"    v_min:   {s['v_min_kph']:.1f} km/h")
        print(f"    a_lat:   {s['a_lateral_apex_g']:.3f}g")

    print("\n" + "="*100)
    print("CONCLUSIONE")
    print("="*100)
    print("\nQueste sezioni critiche devono essere il target di calibrazione:")
    print("- Il modello deve riprodurre ESATTAMENTE questi parametri")
    print("- Se non riesce, c'è un errore nel modello fisico")
    print("- Usa questi dati come vincoli per calibrare power_unit.py e acceleration_profile.py")


if __name__ == "__main__":
    main()
