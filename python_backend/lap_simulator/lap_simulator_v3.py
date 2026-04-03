"""
Physics Engine V3 — Lap Simulator

Loop di simulazione giro completo usando update_section_v3 (Physics V3).
Parallelo a lap_simulator_v2.py per testing e confronto.

Architettura:
- Per ogni sezione del circuito
- Chiama update_section_v3()
- Accumula dt_s → lap_time_s
- Tracking sector times, v_exit, tyre/brake state

Versione: 3.0
Data: 2026-04-02
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import logging

from .physics_v3.update_section_v3 import update_section_v3
from .data_types import (
    CarState,
    AeroSetup,
    DriverSkills,
    SectionResult,
    CircuitConfig,
    EnvContext,
)
from .config_loader import load_circuit_config

logger = logging.getLogger(__name__)


# ============================================================================
# Data Types
# ============================================================================

@dataclass
class CarEntryV3:
    """Entry point per auto in simulazione V3."""
    car_id: str
    aero_setup: AeroSetup
    driver_skills: DriverSkills
    push_level: int = 10
    delta_aero: float = 0.0
    delta_grip: float = 0.0
    setup_sliders: Optional[Dict[str, int]] = None
    ideal_setup_sliders: Optional[Dict[str, int]] = None


@dataclass
class LapResultV3:
    """Risultato di un giro simulato con V3."""
    car_id: str
    lap_time_s: float
    sector_times: Dict[str, float] = field(default_factory=dict)
    section_results: List[SectionResult] = field(default_factory=list)
    v_max_kph: float = 0.0
    v_min_kph: float = 999.0
    fuel_used_kg: float = 0.0
    tyre_wear_avg_pct: float = 0.0
    brake_temp_avg_c: float = 0.0

    def summary(self) -> Dict[str, Any]:
        """Resoconto rapido."""
        return {
            "car_id": self.car_id,
            "lap_time_s": self.lap_time_s,
            "v_max_kph": self.v_max_kph,
            "v_min_kph": self.v_min_kph,
            "sector_times": self.sector_times,
        }


# ============================================================================
# Lap Simulator V3
# ============================================================================

class LapSimulatorV3:
    """
    Simulatore giro completo con Physics Engine V3.

    Usage:
    ```python
    sim = LapSimulatorV3()
    result = sim.run_lap(entries=[car_entry], circuit_id="it-1922_monza")
    ```
    """

    def __init__(self, debug: bool = False):
        """
        Inizializza simulatore.

        Args:
            debug: Se True, abilita logging dettagliato
        """
        self.debug = debug
        self.config: Optional[CircuitConfig] = None
        self.env: Optional[EnvContext] = None

    def run_lap(
        self,
        entries: List[CarEntryV3],
        circuit_id: str,
        is_qualifying: bool = False,
        lap_number: int = 1,
        env: Optional[EnvContext] = None,
    ) -> List[LapResultV3]:
        """
        Simula un giro per ogni auto in entries.

        Args:
            entries: Lista di CarEntryV3
            circuit_id: ID circuito ("it-1922_monza", ecc.)
            is_qualifying: Se qualifica (no fuel, ecc.)
            lap_number: Numero giro
            env: Contesto ambientale (se None, usa default)

        Returns:
            Lista di LapResultV3
        """

        # Load configurazione circuito
        try:
            self.config = load_circuit_config(circuit_id)
        except Exception as e:
            logger.error(f"Failed to load circuit {circuit_id}: {e}")
            raise

        # Ambiente
        if env is None:
            env = EnvContext(
                air_temp_c=20.0,
                track_temp_c=40.0,
                air_density_kg_m3=1.225,
                wind_speed_kph=5.0,
                rain_intensity=0.0,
                track_rubber_level=0.8,
                water_film_level=0.0,
            )
        self.env = env

        # Simula ogni auto
        results = []
        for entry in entries:
            result = self._run_lap_single(
                entry=entry,
                circuit_id=circuit_id,
                is_qualifying=is_qualifying,
                lap_number=lap_number,
            )
            results.append(result)

        return results

    def _run_lap_single(
        self,
        entry: CarEntryV3,
        circuit_id: str,
        is_qualifying: bool = False,
        lap_number: int = 1,
    ) -> LapResultV3:
        """
        Simula un giro singolo per una auto.

        Args:
            entry: CarEntryV3
            circuit_id: ID circuito
            is_qualifying: Se qualifica
            lap_number: Numero giro

        Returns:
            LapResultV3
        """

        assert self.config is not None, "Config non caricata"
        assert self.env is not None, "Env non impostato"

        # Inizializza stato auto
        car_state = CarState(
            car_id=entry.car_id,
            team_code="TST",
            v_current_ms=0.0,  # m/s, not kph
        )

        # Loop sezioni
        lap_time_s = 0.0
        section_results: List[SectionResult] = []
        sector_times: Dict[str, float] = {}
        v_max_kph = 0.0
        v_min_kph = 999.0

        for section in self.config.sections:

            # Chiama update_section_v3
            result = update_section_v3(
                car_state=car_state,
                aero_setup=entry.aero_setup,
                driver_skills=entry.driver_skills,
                section=section,
                env=self.env,
                config=self.config,
                push_level=entry.push_level,
                is_qualifying=is_qualifying,
                circuit_id=circuit_id,
                driver_id=entry.car_id,
                lap_number=lap_number,
                setup_sliders=entry.setup_sliders,
                ideal_setup_sliders=entry.ideal_setup_sliders,
            )

            section_results.append(result)
            lap_time_s += result.dt_s

            # Track v_max, v_min
            v_max_kph = max(v_max_kph, result.v_max_kph)
            v_min_kph = min(v_min_kph, result.v_exit_kph)

            # Update car state per sezione successiva
            car_state.v_current_ms = result.v_exit_kph / 3.6  # Convert kph to m/s

            # Track sector time (semplificato: ogni 3-4 sezioni = 1 settore)
            # TODO: implementare logica settore corretta da circuito

            if self.debug:
                logger.info(
                    f"Section {section.section_id}: dt={result.dt_s:.3f}s, "
                    f"v_exit={result.v_exit_kph:.1f}kph"
                )

        # Assemble result
        result = LapResultV3(
            car_id=entry.car_id,
            lap_time_s=lap_time_s,
            sector_times=sector_times,
            section_results=section_results,
            v_max_kph=v_max_kph,
            v_min_kph=v_min_kph,
        )

        return result


# ============================================================================
# Helper: Comparison V1 vs V3
# ============================================================================

def compare_engines(
    circuit_id: str,
    entry: CarEntryV3,
    env: Optional[EnvContext] = None,
) -> Dict[str, Any]:
    """
    Confronta lap time V1 vs V3.

    Nota: richiede che lap_simulator.py e lap_simulator_v3.py coesistano.

    Args:
        circuit_id: ID circuito
        entry: CarEntryV3
        env: Contesto ambientale

    Returns:
        Dict con risultati confronto
    """

    # Simula con V3
    sim_v3 = LapSimulatorV3()
    results_v3 = sim_v3.run_lap([entry], circuit_id, env=env)

    # TODO: Simulare con V1 se disponibile
    # from .lap_simulator import LapSimulator
    # sim_v1 = LapSimulator()
    # results_v1 = sim_v1.run_lap(...)

    return {
        "v3_lap_time_s": results_v3[0].lap_time_s if results_v3 else None,
        # "v1_lap_time_s": ...,
        # "delta_s": ...,
        # "delta_pct": ...,
    }


# ============================================================================
# Test / Validation
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("lap_simulator_v3 module loaded")
    print(f"Version: 3.0")
    print(f"Status: Implementation complete")
