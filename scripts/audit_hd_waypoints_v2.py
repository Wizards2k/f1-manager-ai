#!/usr/bin/env python3
"""
Audit completo HD waypoints F1 2025 - Versione Corretta

Gestisce correttamente:
- Raggi rettilinei (999999.0m) → esclusi dalle statistiche curve
- Curve reali (radius < 1000m)
- Verifica circuiti critici (Monaco, Suzuka, Monza)
"""

import json
from pathlib import Path
from typing import Dict, List, Any

CIRCUITS_DIR = Path("/Users/wizards/Sviluppo/F1 Manager AI/python_backend/data/circuits/2025")

# Circuiti con verifiche critiche
CRITICAL_CHECKS = {
    "mc-1929_monaco": {"type": "Hairpin", "min_radius": 11.0, "max_radius": 18.0, "check": "min"},
    "jp-1962_suzuka": {"type": "130R", "min_radius": 750.0, "max_radius": 900.0, "check": "max"},
    "it-1922_monza": {"type": "Parabolica", "min_radius": 350.0, "max_radius": 550.0, "check": "max"},
}

# Nomi circuiti per display
CIRCUIT_NAMES = {
    "mc-1929_monaco": "Monaco",
    "jp-1962_suzuka": "Suzuka",
    "it-1922_monza": "Monza",
    "gb-1948_silverstone": "Silverstone",
    "be-1925_spa_francorchamps": "Spa",
    "sa-2021_jeddah": "Jeddah",
}


def analyze_circuit(hd_file: Path) -> Dict[str, Any]:
    """Analizza un circuito HD."""
    circuit_id = hd_file.stem.replace("_HD", "")
    
    with open(hd_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    waypoints = data.get("waypoints", [])
    
    # Separa curve da rettilinei
    corner_radii = []
    straight_count = 0
    
    for wp in waypoints:
        radius = wp.get("radius_m", 0)
        if radius and radius > 0:
            if radius >= 1000.0:  # Rettilineo
                straight_count += 1
            else:  # Curva reale
                corner_radii.append(radius)
    
    if not corner_radii:
        return {
            "circuit_id": circuit_id,
            "status": "NO_CORNERS",
            "waypoints": len(waypoints),
        }
    
    # Statistiche curve
    min_radius = min(corner_radii)
    max_radius = max(corner_radii)
    avg_radius = sum(corner_radii) / len(corner_radii)
    
    # Trova waypoint con raggio minimo
    min_wp = min(waypoints, key=lambda wp: wp.get("radius_m", 999999) if wp.get("radius_m", 0) < 1000 else 999999)
    max_wp = max(waypoints, key=lambda wp: wp.get("radius_m", 0) if wp.get("radius_m", 0) < 1000 else 0)
    
    result = {
        "circuit_id": circuit_id,
        "status": "OK",
        "waypoints": len(waypoints),
        "corners": len(corner_radii),
        "straights": straight_count,
        "radius_stats": {
            "min": min_radius,
            "max": max_radius,
            "avg": avg_radius,
        },
        "tightest_corner": {
            "radius": min_radius,
            "dist_m": min_wp.get("dist_m"),
            "speed_kph": min_wp.get("v_ref_kph"),
            "section_kind": min_wp.get("section_kind"),
        },
        "fastest_corner": {
            "radius": max_radius,
            "dist_m": max_wp.get("dist_m"),
            "speed_kph": max_wp.get("v_ref_kph"),
            "section_kind": max_wp.get("section_kind"),
        }
    }
    
    # Verifica critica se presente
    if circuit_id in CRITICAL_CHECKS:
        check = CRITICAL_CHECKS[circuit_id]
        actual_value = min_radius if check["check"] == "min" else max_radius
        
        if actual_value < check["min_radius"]:
            result["critical_check"] = {
                "type": check["type"],
                "expected_min": check["min_radius"],
                "expected_max": check["max_radius"],
                "actual": actual_value,
                "status": "WARNING",
                "message": f"{check['type']} troppo {'stretto' if check['check'] == 'min' else 'largo'}: {actual_value:.1f}m (dovrebbe essere {check['min_radius']}-{check['max_radius']}m)"
            }
        elif actual_value > check["max_radius"]:
            result["critical_check"] = {
                "type": check["type"],
                "expected_min": check["min_radius"],
                "expected_max": check["max_radius"],
                "actual": actual_value,
                "status": "WARNING",
                "message": f"{check['type']} troppo {'largo' if check['check'] == 'min' else 'stretto'}: {actual_value:.1f}m (dovrebbe essere {check['min_radius']}-{check['max_radius']}m)"
            }
        else:
            result["critical_check"] = {
                "type": check["type"],
                "expected_min": check["min_radius"],
                "expected_max": check["max_radius"],
                "actual": actual_value,
                "status": "OK",
                "message": f"{check['type']} corretto: {actual_value:.1f}m"
            }
    
    return result


def generate_report(results: List[Dict[str, Any]]) -> str:
    """Genera report testuale."""
    lines = []
    lines.append("=" * 80)
    lines.append("AUDIT HD WAYPOINTS - F1 2025")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary
    ok_count = sum(1 for r in results if r["status"] == "OK")
    warning_count = sum(1 for r in results if r.get("critical_check", {}).get("status") == "WARNING")
    
    lines.append("📊 RIEPILOGO:")
    lines.append(f"  Circuiti totali: {len(results)}")
    lines.append(f"  ✅ OK: {ok_count}")
    lines.append(f"  ⚠️  Con avvisi: {warning_count}")
    lines.append("")
    
    # Circuiti critici
    if warning_count > 0:
        lines.append("🚨 CIRCUITI CON PROBLEMI:")
        lines.append("-" * 80)
        for r in results:
            if r.get("critical_check", {}).get("status") == "WARNING":
                lines.append(f"  {r['circuit_id']} ({CIRCUIT_NAMES.get(r['circuit_id'], 'Unknown')})")
                lines.append(f"    {r['critical_check']['message']}")
        lines.append("")
    
    # Dettaglio circuiti
    lines.append("📋 DETTAGLIO CIRCUITI:")
    lines.append("-" * 80)
    
    for r in sorted(results, key=lambda x: x["circuit_id"]):
        circuit_id = r["circuit_id"]
        name = CIRCUIT_NAMES.get(circuit_id, "")
        
        if r["status"] == "NO_CORNERS":
            lines.append(f"\n⚠️  {circuit_id} ({name}): NESSUNA CURVA TROVATA")
            continue
        
        stats = r["radius_stats"]
        tightest = r["tightest_corner"]
        fastest = r["fastest_corner"]
        
        lines.append(f"\n✅ {circuit_id} ({name})")
        lines.append(f"    Waypoints: {r['waypoints']} (curve: {r['corners']}, rettilinei: {r['straights']})")
        lines.append(f"    Curve: min={stats['min']:.1f}m, max={stats['max']:.1f}m, avg={stats['avg']:.1f}m")
        lines.append(f"    Curva + stretta: {tightest['radius']:.1f}m @ {tightest['speed_kph']:.1f} kph ({tightest['section_kind']})")
        lines.append(f"    Curva + veloce: {fastest['radius']:.1f}m @ {fastest['speed_kph']:.1f} kph ({fastest['section_kind']})")
        
        if "critical_check" in r:
            check = r["critical_check"]
            icon = "✅" if check["status"] == "OK" else "⚠️"
            lines.append(f"    {icon} {check['message']}")
    
    lines.append("")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    """Esegui audit su tutti i circuiti."""
    print("🔍 Avvio audit HD waypoints F1 2025...")
    print("")
    
    hd_files = sorted(CIRCUITS_DIR.glob("*_HD.json"))
    
    results = []
    for hd_file in hd_files:
        circuit_id = hd_file.stem.replace("_HD", "")
        print(f"  Analizzando {circuit_id}...", end=" ")
        
        result = analyze_circuit(hd_file)
        results.append(result)
        
        if result["status"] == "OK":
            print(f"✅ OK ({result['corners']} curve)")
        else:
            print(f"⚠️  {result['status']}")
    
    print("")
    
    # Genera report
    report = generate_report(results)
    print(report)
    
    # Salva report
    reports_dir = Path("/Users/wizards/Sviluppo/F1 Manager AI/reports")
    reports_dir.mkdir(exist_ok=True)
    
    report_file = reports_dir / "hd_waypoints_audit_v2.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n💾 Report salvato: {report_file}")
    
    # Salva JSON
    json_file = reports_dir / "hd_waypoints_audit_v2.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Dati JSON salvati: {json_file}")
    
    # Exit code
    warning_count = sum(1 for r in results if r.get("critical_check", {}).get("status") == "WARNING")
    return 1 if warning_count > 0 else 0


if __name__ == "__main__":
    exit(main())
