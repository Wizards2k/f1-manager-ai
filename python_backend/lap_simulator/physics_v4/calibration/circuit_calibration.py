"""
Physics Engine V4 - Circuit Calibration Parameters

Parametri di calibrazione per circuiti F1 2025.
Questi parametri permettono di ottenere tempi realistici per ogni circuito.

Usage:
    from lap_simulator.physics_v4.calibration.circuit_calibration import get_circuit_calibration
    
    cal = get_circuit_calibration("mc-1929_monaco")
    result = integrate_lap_hd(
        circuit_id="mc-1929_monaco",
        mu_override=cal["mu_override"],
        max_brake_decel_g_override=cal["max_brake_decel_g"],
        max_lateral_g_override=cal["max_lateral_g"]
    )
"""

from typing import Dict, Any, Optional


# Calibrazioni per circuito
CIRCUIT_CALIBRATIONS: Dict[str, Dict[str, Any]] = {
    # MONACO - High Downforce
    # Calibrato il: 2026-04-10 (V4.15: ridotto mu per permettere downforce coupling)
    # Target: ~70.0s con setup Monaco ottimale (FW=38, RW=42, C6)
    # V4.15: mu_override ridotto da +20% a +8% sopra base.
    # Il grip meccanico troppo alto rendeva il downforce marginale.
    # Ora il downforce è il vincolo attivo → setup carico è premiato.
    "mc-1929_monaco": {
        "mu_override": {"C6": 2.33, "C5": 2.26, "C4": 2.10, "C3": 1.96},  # +8% grip
        "max_brake_decel_g": 4.8,  # -26% frenata più dolce
        "max_lateral_g": 8.0,  # +45% più carico laterale
        "notes": "V5.5: brake state commitment (anti-chatter) elimina oscillazione frenata senza bisogno di telemetria. V4.15: mu ridotto per rendere downforce premiante.",
        "accuracy_pct": 0.5,
    },
    
    # MONZA - Low Downforce
    # Calibrato il: 2026-04-04
    # Target: 79.5s, Risultato: 81.2s (+2.1%) - ACCETTABILE
    "it-1922_monza": {
        "mu_override": None,  # Usa default (1.80 C5)
        "max_brake_decel_g": None,  # Usa default (6.5g)
        "max_lateral_g": None,  # Usa default (5.5g)
        "notes": "Calibrazione base accettabile, da affinare",
        "accuracy_pct": 2.1,
    },
    
    # SUZUKA - Balanced
    # Target: 88.5s, Attuale: 83.8s (-5.3%) - DA CALIBRARE
    "jp-1962_suzuka": {
        "mu_override": None,
        "max_brake_decel_g": None,
        "max_lateral_g": None,
        "notes": "Da calibrare: ridurre grip per aumentare tempo",
        "accuracy_pct": -5.3,
    },
}


def get_circuit_calibration(circuit_id: str) -> Optional[Dict[str, Any]]:
    """
    Ottieni parametri di calibrazione per un circuito.
    
    Args:
        circuit_id: ID circuito (es. "mc-1929_monaco")
    
    Returns:
        Dizionario con parametri o None se non calibrato
    """
    return CIRCUIT_CALIBRATIONS.get(circuit_id)


def is_circuit_calibrated(circuit_id: str) -> bool:
    """Verifica se un circuito è calibrato."""
    cal = get_circuit_calibration(circuit_id)
    if cal is None:
        return False
    
    # Considera calibrato se accuracy < 5%
    return abs(cal.get("accuracy_pct", 999)) < 5.0


def get_calibrated_circuits() -> list:
    """Restituisce lista circuiti calibrati."""
    return [cid for cid in CIRCUIT_CALIBRATIONS if is_circuit_calibrated(cid)]


def get_calibration_summary() -> str:
    """Restituisce riepilogo calibrazioni."""
    lines = ["=" * 60, "CIRCUIT CALIBRATION SUMMARY", "=" * 60]
    
    for cid, cal in CIRCUIT_CALIBRATIONS.items():
        status = "✅" if is_circuit_calibrated(cid) else "⚠️"
        acc = cal.get("accuracy_pct", 0)
        lines.append(f"{status} {cid:25s}: {acc:+.1f}%")
        if cal.get("notes"):
            lines.append(f"   {cal['notes']}")
    
    calibrated = get_calibrated_circuits()
    lines.append("")
    lines.append(f"Calibrated: {len(calibrated)}/{len(CIRCUIT_CALIBRATIONS)}")
    lines.append("=" * 60)
    
    return "\n".join(lines)
