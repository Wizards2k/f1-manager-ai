#!/usr/bin/env python3
"""
Audit completo dei waypoints HD per tutti i circuiti F1 2025.

Verifica:
1. Raggi curva realistici (Monaco Hairpin ~11-15m, Suzuka 130R ~800m)
2. Presenza di radius_m in tutti i waypoints
3. Coerenza tra circuiti
4. Waypoints totali per circuito
"""

import json
from pathlib import Path
from typing import Dict, List, Any

# Circuiti F1 2025 con curve critiche di riferimento
CIRCUITS_CRITICAL_RADIUS = {
    "mc-1929_monaco": {"hairpin_min": 11.0, "hairpin_max": 18.0, "name": "Monaco"},
    "jp-1962_suzuka": {"130r_min": 750.0, "130r_max": 900.0, "name": "Suzuka"},
    "it-1922_monza": {"parabolica_min": 350.0, "parabolica_max": 550.0, "name": "Monza"},
    "gb-1948_silverstone": {"copses_min": 250.0, "copses_max": 400.0, "name": "Silverstone"},
    "be-1925_spa_francorchamps": {"eau_rouge_min": 350.0, "eau_rouge_max": 500.0, "name": "Spa"},
    "sa-2021_jeddah": {"fast_corner_min": 400.0, "fast_corner_max": 700.0, "name": "Jeddah"},
}

# Nomi effettivi dei file (alcuni differiscono dalla lista ufficiale)
ALL_2025_CIRCUITS = [
    "ae-2009_yas_marina",
    "at-1969_spielberg",
    "au-1953_melbourne",
    "az-2016_baku",
    "be-1925_spa_francorchamps",  # Nome completo nel file
    "bh-2002_sakhir",
    "br-1940_sao_paulo",
    "ca-1978_montreal",
    "cn-2004_shanghai",
    "es-1991_barcelona",
    "gb-1948_silverstone",
    "hu-1986_budapest",
    "it-1922_monza",
    "it-1953_imola",
    "jp-1962_suzuka",
    "mc-1929_monaco",
    "mx-1962_mexico_city",
    "nl-1948_zandvoort",
    "qa-2004_lusail",
    "sa-2021_jeddah",
    "sg-2008_singapore",
    "us-2012_austin",
    "us-2022_miami",
    "us-2023_las_vegas",
]


def load_hd_waypoints(circuit_id: str) -> List[Dict[str, Any]]:
    """Carica waypoints HD per un circuito."""
    project_root = Path(__file__).resolve().parent.parent
    
    # Percorso corretto: python_backend/data/circuits/2025/
    circuits_dir = project_root / "python_backend" / "data" / "circuits" / "2025"
    hd_file = circuits_dir / f"{circuit_id}_HD.json"
    
    if not hd_file.exists():
        # Debug: stampa il percorso cercato
        print(f"    [DEBUG] Cercando: {hd_file}")
        print(f"    [DEBUG] circuits_dir esiste: {circuits_dir.exists()}")
        if circuits_dir.exists():
            files = list(circuits_dir.glob("*.json"))
            print(f"    [DEBUG] File in circuits_dir: {[f.name for f in files[:5]]}...")
        return []
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get("TelemetryPoints", [])


def analyze_circuit_radius(circuit_id: str) -> Dict[str, Any]:
    """Analizza i raggi delle curve per un circuito."""
    waypoints = load_hd_waypoints(circuit_id)
    
    if not waypoints:
        return {
            "circuit_id": circuit_id,
            "status": "MISSING",
            "error": "File HD non trovato"
        }
    
    # Estrai raggi validi
    radii = []
    for wp in waypoints:
        radius = wp.get("radius_m")
        if radius is not None and radius > 0:
            radii.append(radius)
    
    # Statistiche
    total_waypoints = len(waypoints)
    valid_radii_count = len(radii)
    null_radii_count = total_waypoints - valid_radii_count
    
    if not radii:
        return {
            "circuit_id": circuit_id,
            "status": "NO_RADIUS",
            "total_waypoints": total_waypoints,
            "valid_radii": 0,
            "null_radii": null_radii_count,
            "warning": "NESSUN raggio trovato!"
        }
    
    # Calcola statistiche
    min_radius = min(radii)
    max_radius = max(radii)
    avg_radius = sum(radii) / len(radii)
    
    # Trova il raggio minimo (curva più stretta)
    min_radius_idx = radii.index(min_radius)
    min_radius_wp = waypoints[min_radius_idx]
    
    # Trova il raggio massimo (curva più veloce)
    max_radius_idx = radii.index(max_radius)
    max_radius_wp = waypoints[max_radius_idx]
    
    result = {
        "circuit_id": circuit_id,
        "status": "OK",
        "total_waypoints": total_waypoints,
        "valid_radii": valid_radii_count,
        "null_radii": null_radii_count,
        "radius_stats": {
            "min": min_radius,
            "max": max_radius,
            "avg": avg_radius,
        },
        "tightest_corner": {
            "radius": min_radius,
            "distance_m": min_radius_wp.get("DistanceFromStart"),
            "speed_kph": min_radius_wp.get("Speed"),
        },
        "fastest_corner": {
            "radius": max_radius,
            "distance_m": max_radius_wp.get("DistanceFromStart"),
            "speed_kph": max_radius_wp.get("Speed"),
        }
    }
    
    # Verifica curve critiche se presenti
    if circuit_id in CIRCUITS_CRITICAL_RADIUS:
        critical = CIRCUITS_CRITICAL_RADIUS[circuit_id]
        
        if "hairpin_min" in critical:  # Monaco
            if min_radius > critical["hairpin_max"]:
                result["critical_check"] = {
                    "type": "hairpin",
                    "expected_min": critical["hairpin_min"],
                    "expected_max": critical["hairpin_max"],
                    "actual": min_radius,
                    "status": "WARNING",
                    "message": f"Hairpin troppo largo: {min_radius:.1f}m (dovrebbe essere 11-18m)"
                }
            elif min_radius < critical["hairpin_min"]:
                result["critical_check"] = {
                    "type": "hairpin",
                    "expected_min": critical["hairpin_min"],
                    "expected_max": critical["hairpin_max"],
                    "actual": min_radius,
                    "status": "WARNING",
                    "message": f"Hairpin troppo stretto: {min_radius:.1f}m (dovrebbe essere 11-18m)"
                }
            else:
                result["critical_check"] = {
                    "type": "hairpin",
                    "expected_min": critical["hairpin_min"],
                    "expected_max": critical["hairpin_max"],
                    "actual": min_radius,
                    "status": "OK",
                    "message": f"Hairpin corretto: {min_radius:.1f}m"
                }
        
        elif "130r_min" in critical:  # Suzuka
            if max_radius < critical["130r_min"]:
                result["critical_check"] = {
                    "type": "130R",
                    "expected_min": critical["130r_min"],
                    "expected_max": critical["130r_max"],
                    "actual": max_radius,
                    "status": "WARNING",
                    "message": f"130R troppo stretto: {max_radius:.1f}m (dovrebbe essere 750-900m)"
                }
            elif max_radius > critical["130r_max"]:
                result["critical_check"] = {
                    "type": "130R",
                    "expected_min": critical["130r_min"],
                    "expected_max": critical["130r_max"],
                    "actual": max_radius,
                    "status": "WARNING",
                    "message": f"130R troppo largo: {max_radius:.1f}m (dovrebbe essere 750-900m)"
                }
            else:
                result["critical_check"] = {
                    "type": "130R",
                    "expected_min": critical["130r_min"],
                    "expected_max": critical["130r_max"],
                    "actual": max_radius,
                    "status": "OK",
                    "message": f"130R corretto: {max_radius:.1f}m"
                }
    
    return result


def generate_report(results: List[Dict[str, Any]]) -> str:
    """Genera report testuale dell'audit."""
    report = []
    report.append("=" * 80)
    report.append("AUDIT HD WAYPOINTS - F1 2025")
    report.append("=" * 80)
    report.append("")
    
    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    missing_count = sum(1 for r in results if r["status"] == "MISSING")
    no_radius_count = sum(1 for r in results if r["status"] == "NO_RADIUS")
    warning_count = sum(1 for r in results if r.get("critical_check", {}).get("status") == "WARNING")
    
    report.append("📊 RIEPILOGO:")
    report.append(f"  Circuiti totali: {len(results)}")
    report.append(f"  ✅ OK: {ok_count}")
    report.append(f"  ❌ File mancanti: {missing_count}")
    report.append(f"  ⚠️  Senza raggi: {no_radius_count}")
    report.append(f"  ⚠️  Raggi sospetti: {warning_count}")
    report.append("")
    
    # Circuiti con problemi critici
    if warning_count > 0:
        report.append("🚨 CIRCUITI CON RAGGI SOSPETTI:")
        report.append("-" * 80)
        for r in results:
            if r.get("critical_check", {}).get("status") == "WARNING":
                report.append(f"  {r['circuit_id']} ({CIRCUITS_CRITICAL_RADIUS[r['circuit_id']]['name']})")
                report.append(f"    {r['critical_check']['message']}")
        report.append("")
    
    # Circuito per circuito
    report.append("📋 DETTAGLIO CIRCUITI:")
    report.append("-" * 80)
    
    for r in sorted(results, key=lambda x: x.get("circuit_id", "")):
        circuit_id = r["circuit_id"]
        status = r["status"]
        
        if status == "MISSING":
            report.append(f"\n❌ {circuit_id}: FILE NON TROVATO")
            continue
        
        if status == "NO_RADIUS":
            report.append(f"\n⚠️  {circuit_id}: NESSUN RAGGIO TROVATO")
            report.append(f"    Waypoints: {r['total_waypoints']}")
            continue
        
        # OK
        stats = r["radius_stats"]
        tightest = r["tightest_corner"]
        fastest = r["fastest_corner"]
        
        report.append(f"\n✅ {circuit_id} ({CIRCUITS_CRITICAL_RADIUS.get(circuit_id, {}).get('name', 'Unknown')})")
        report.append(f"    Waypoints: {r['total_waypoints']} (validi: {r['valid_radii']}, nulli: {r['null_radii']})")
        report.append(f"    Raggi: min={stats['min']:.1f}m, max={stats['max']:.1f}m, avg={stats['avg']:.1f}m")
        report.append(f"    Curva più stretta: {tightest['radius']:.1f}m @ {tightest['speed_kph']} kph (dist: {tightest['distance_m']:.1f}m)")
        report.append(f"    Curva più veloce: {fastest['radius']:.1f}m @ {fastest['speed_kph']} kph (dist: {fastest['distance_m']:.1f}m)")
        
        if "critical_check" in r:
            check = r["critical_check"]
            icon = "✅" if check["status"] == "OK" else "⚠️"
            report.append(f"    {icon} {check['message']}")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)


def main():
    """Esegui audit su tutti i circuiti F1 2025."""
    print("🔍 Avvio audit HD waypoints F1 2025...")
    print("")
    
    results = []
    for circuit_id in ALL_2025_CIRCUITS:
        print(f"  Analizzando {circuit_id}...", end=" ")
        result = analyze_circuit_radius(circuit_id)
        results.append(result)
        
        if result["status"] == "OK":
            print(f"✅ OK ({result['valid_radii']} raggi)")
        elif result["status"] == "MISSING":
            print("❌ FILE MANCANTE")
        elif result["status"] == "NO_RADIUS":
            print("⚠️  NESSUN RAGGIO")
        else:
            print(f"❓ {result['status']}")
    
    print("")
    
    # Genera report
    report = generate_report(results)
    print(report)
    
    # Salva report su file
    project_root = Path(__file__).resolve().parent.parent
    reports_dir = project_root / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    report_file = reports_dir / "hd_waypoints_audit.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 Report salvato: {report_file}")
    
    # Salva anche JSON per analisi successiva
    json_file = reports_dir / "hd_waypoints_audit.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Dati JSON salvati: {json_file}")
    
    # Return exit code basato su problemi trovati
    warning_count = sum(1 for r in results if r.get("critical_check", {}).get("status") == "WARNING")
    missing_count = sum(1 for r in results if r["status"] == "MISSING")
    no_radius_count = sum(1 for r in results if r["status"] == "NO_RADIUS")
    
    if warning_count > 0 or missing_count > 0 or no_radius_count > 0:
        print("\n🚨 Audit completato con problemi rilevati!")
        return 1
    else:
        print("\n✅ Audit completato: tutti i circuiti OK!")
        return 0


if __name__ == "__main__":
    exit(main())
