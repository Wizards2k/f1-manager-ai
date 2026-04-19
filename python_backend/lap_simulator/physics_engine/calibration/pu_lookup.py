"""
Physics Engine V5.0 - PU Lookup Loader

Carica le lookup table della Power Unit generate da `scripts/sync_telemetry_2025.py`
e salvate in `data/circuits/pu_lookup/<circuit_id>_pu_lookup.json`.

Ogni file contiene:
  - entries: lista di {speed_kph, rpm, gear, throttle_pct, f_engine_estimated}
  - gear_summary: range RPM/speed per marcia

La lookup table fornisce la forza motrice reale stimata dalla telemetria
per ogni punto di velocità, permettendo al simulatore di usare dati reali
invece del modello generico ICE+ERS costante.
"""

from __future__ import annotations

from bisect import bisect_left
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json


_REPO_ROOT = Path(__file__).resolve().parents[4]
_PU_LOOKUP_DIR = _REPO_ROOT / "python_backend" / "data" / "circuits" / "pu_lookup"

# Fallback directories
_FALLBACK_DIRS = [
    Path(__file__).resolve().parents[2] / "data" / "circuits" / "pu_lookup",
]


def normalize_circuit_id(circuit_id: Optional[str]) -> str:
    """Normalizza l'ID del circuito per il lookup file-system."""
    return (circuit_id or "").strip().lower()


def _resolve_pu_lookup_path(circuit_id: str) -> Optional[Path]:
    """Trova il file PU Lookup per il circuito richiesto."""
    circuit_key = normalize_circuit_id(circuit_id)
    if not circuit_key:
        return None

    # Cerca in tutte le directory possibili
    search_dirs = [_PU_LOOKUP_DIR] + _FALLBACK_DIRS
    for search_dir in search_dirs:
        # Prova match esatto
        candidate = search_dir / f"{circuit_key}_pu_lookup.json"
        if candidate.exists():
            return candidate

        # Prova match parziale (glob)
        matches = sorted(search_dir.glob(f"*{circuit_key}*_pu_lookup.json"))
        if matches:
            return matches[0]

    return None


@lru_cache(maxsize=None)
def load_pu_lookup(circuit_id: str) -> Optional[Dict[str, Any]]:
    """
    Carica la PU Lookup table per il circuito richiesto.

    Returns:
        Dict con 'entries' (lista di dict) e 'gear_summary', oppure None.
    """
    path = _resolve_pu_lookup_path(circuit_id)
    if path is None:
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) == 0:
        return None

    return payload


class PULookupInterpolator:
    """
    Interpolatore per la PU Lookup table.

    Permette di ottenere f_engine_estimated per qualsiasi velocità
    interpolando linearmente tra i punti della lookup table.
    """

    def __init__(self, pu_lookup: Dict[str, Any]):
        """
        Inizializza l'interpolatore con i dati della PU Lookup.

        Args:
            pu_lookup: Dict con 'entries' dalla PU Lookup JSON
        """
        entries = pu_lookup["entries"]
        # Ordina per velocità
        sorted_entries = sorted(entries, key=lambda e: e["speed_kph"])

        self._speeds = [e["speed_kph"] for e in sorted_entries]
        self._forces = [e["f_engine_estimated"] for e in sorted_entries]
        self._rpms = [e["rpm"] for e in sorted_entries]
        self._gears = [e["gear"] for e in sorted_entries]
        self._throttles = [e["throttle_pct"] for e in sorted_entries]

        # Pre-calcola speed min/max per clamp
        self._speed_min = self._speeds[0]
        self._speed_max = self._speeds[-1]

    def get_f_engine(self, speed_kph: float) -> float:
        """
        Interpola f_engine_estimated per una data velocità.

        Args:
            speed_kph: velocità in km/h

        Returns:
            Forza motrice stimata in Newton, interpolata dalla lookup table.
            Per velocità fuori range, usa il valore più vicino (clamp).
        """
        # Clamp ai limiti della lookup
        if speed_kph <= self._speed_min:
            return self._forces[0]
        if speed_kph >= self._speed_max:
            return self._forces[-1]

        # Trova indice per interpolazione lineare
        idx = bisect_left(self._speeds, speed_kph)

        # Interpolazione lineare tra idx-1 e idx
        if idx == 0:
            return self._forces[0]

        s0 = self._speeds[idx - 1]
        s1 = self._speeds[idx]
        f0 = self._forces[idx - 1]
        f1 = self._forces[idx]

        if s1 == s0:
            return f0

        t = (speed_kph - s0) / (s1 - s0)
        return f0 + t * (f1 - f0)

    def get_rpm(self, speed_kph: float) -> float:
        """Interpola RPM per una data velocità."""
        if speed_kph <= self._speed_min:
            return self._rpms[0]
        if speed_kph >= self._speed_max:
            return self._rpms[-1]

        idx = bisect_left(self._speeds, speed_kph)
        if idx == 0:
            return self._rpms[0]

        s0 = self._speeds[idx - 1]
        s1 = self._speeds[idx]
        r0 = self._rpms[idx - 1]
        r1 = self._rpms[idx]

        if s1 == s0:
            return r0

        t = (speed_kph - s0) / (s1 - s0)
        return r0 + t * (r1 - r0)

    def get_throttle(self, speed_kph: float) -> float:
        """Interpola throttle_pct per una data velocità."""
        if speed_kph <= self._speed_min:
            return self._throttles[0]
        if speed_kph >= self._speed_max:
            return self._throttles[-1]

        idx = bisect_left(self._speeds, speed_kph)
        if idx == 0:
            return self._throttles[0]

        s0 = self._speeds[idx - 1]
        s1 = self._speeds[idx]
        t0 = self._throttles[idx - 1]
        t1 = self._throttles[idx]

        if s1 == s0:
            return t0

        t = (speed_kph - s0) / (s1 - s0)
        return t0 + t * (t1 - t0)

    def get_gear(self, speed_kph: float) -> float:
        """Interpola gear per una data velocità."""
        if speed_kph <= self._speed_min:
            return self._gears[0]
        if speed_kph >= self._speed_max:
            return self._gears[-1]

        idx = bisect_left(self._speeds, speed_kph)
        if idx == 0:
            return self._gears[0]

        s0 = self._speeds[idx - 1]
        s1 = self._speeds[idx]
        g0 = self._gears[idx - 1]
        g1 = self._gears[idx]

        if s1 == s0:
            return g0

        t = (speed_kph - s0) / (s1 - s0)
        return g0 + t * (g1 - g0)

    @property
    def speed_range(self) -> Tuple[float, float]:
        """Range di velocità coperto dalla lookup table (km/h)."""
        return (self._speed_min, self._speed_max)

    @property
    def num_entries(self) -> int:
        """Numero di punti nella lookup table."""
        return len(self._speeds)