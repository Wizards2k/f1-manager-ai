"""
lap_simulator_v2.py - LapSimulator Parallelo per Validazione Physics Engine v2

Questo modulo implementa una versione parallela di LapSimulator che usa
il nuovo motore fisico v2 (update_section_v2) invece del motore v1 (update_section).

Il motore v2 è completamente indipendente da v1 e viene usato SOLO per:
1. Confronto con v1 microsettore per microsettore
2. Validazione contro telemetria Q3
3. Verifica che setup diversi producano tempi diversi in modo fisicamente coerente

USO:
- lap_simulator.py = motore v1 (produzione)
- lap_simulator_v2.py = motore v2 (validazione parallela)
- scripts/compare_engines.py = confronto v1 vs v2

Reference: docs/lap-physics-spec-v0.5.md, docs/lap-physics-v2-analysis.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lap_simulator.ai_data_types import AIDriverConfig, AITeamConfig, RunProgram
from lap_simulator.data_types import (
    AeroSetup,
    CarEntry,
    CarState,
    CircuitConfig,
    EnvContext,
    LapResult,
    SectionContext,
    SectionResult,
    TyreCompound,
)
from lap_simulator.update_section_v2 import update_section_v2

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------   
# Data Classes for V2
# ---------------------------------------------------------------------------   

@dataclass
class CarEntryV2:
    """Car entry for v2 engine"""
    driver_config: AIDriverConfig
    team_config: AITeamConfig
    aero_setup: AeroSetup
    tyre_compound: TyreCompound
    fuel_load_kg: float
    starting_position: int


@dataclass  
class LapResultV2:
    """Lap result from v2 engine"""
    lap_time_ms: float
    sectors: List[SectionResult]
    microsectors: List[Dict[str, Any]]
    tyre_wear: Dict[str, float]
    fuel_consumption: float
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------   
# LapSimulatorV2 Class
# ---------------------------------------------------------------------------   

class LapSimulatorV2:
    """
    LapSimulator v2 - Physics engine v2 per validazione
    
    Questo motore usa update_section_v2 per calcolare i tempi microsettore
    con fisica pura (senza baseline telemetry come target).
    """
    
    def __init__(self, circuit_config: CircuitConfig, env_context: EnvContext):
        self.circuit_config = circuit_config
        self.env_context = env_context
        self.logger = logger
        
    def run_lap(
        self,
        car_entry: CarEntryV2,
        start_position: int = 0,
        start_fuel: Optional[float] = None,
    ) -> LapResultV2:
        """
        Run a complete lap with v2 physics engine
        
        Args:
            car_entry: Car configuration
            start_position: Starting position on track
            start_fuel: Starting fuel load (default: max fuel)
            
        Returns:
            LapResultV2 with lap time, sectors, and microsectors
        """
        # ===================================================================
        # STEP 1 – Initialize state
        # ===================================================================
        car_state = CarState(
            car_id=car_entry.driver_config.entry_id,
            tyres={},
            brakes=None,
            pu=None,
            damage=None,
            driver_mental=None,
            aero_forces=None,
            ers_mode="STANDARD",
            current_section_idx=0,
            section_progress=0.0,
            lap_time_acc_s=0.0,
            lap_number=1,
            v_current_ms=0.0,
        )
        
        # Initialize tyres
        from lap_simulator.data_types import WheelPosition, TyreState
        for wp in [WheelPosition.LF, WheelPosition.RF, WheelPosition.LR, WheelPosition.RR]:
            car_state.tyres[wp] = TyreState(
                wheel_pos=wp,
                compound=car_entry.tyre_compound,
                surface_temp_c=100.0,  # Start at optimal temp
                core_temp_c=95.0,
                wear_pct=0.0,
            )
        
        # Initialize brakes
        from lap_simulator.data_types import BrakeState
        car_state.brakes = BrakeState(
            temp_front_c=400.0,
            temp_rear_c=350.0,
            wear_front_pct=0.0,
            wear_rear_pct=0.0,
            fade_level=0.0,
            duct_opening=0.5,
            bias_front_pct=55.0,
        )
        
        # Initialize PU
        from lap_simulator.data_types import PUState
        car_state.pu = PUState(
            active_map="RACE",
            ers_mode="STANDARD",
            ice_temp_c=95.0,
            ice_wear_pct=0.0,
            ice_power_kw=450.0,
            ice_derating=False,
            ers_temp_c=55.0,
            ers_wear_pct=0.0,
            ers_energy_mj=4.0,
            ers_output_kw=120.0,
            ers_derating=False,
            fuel_kg=car_entry.fuel_load_kg,
            fuel_burn_rate_kg_per_s=0.0,
        )
        
        # Initialize damage
        from lap_simulator.data_types import DamageState
        car_state.damage = DamageState(
            suspension_damage=0.0,
            floor_damage=0.0,
            gearbox_damage=0.0,
            steering_damage=0.0,
        )
        
        # Initialize driver mental
        from lap_simulator.data_types import DriverMentalState
        car_state.driver_mental = DriverMentalState(
            confidence=0.5,
            fatigue=0.0,
            pressure=0.0,
            focus=1.0,
        )
        
        # Initialize aero forces
        from lap_simulator.data_types import AeroForces
        car_state.aero_forces = AeroForces(
            df_front_eff=0.0,
            df_rear_eff=0.0,
            df_total=0.0,
            drag_eff=0.0,
            aero_balance=0.5,
            handling_penalty=0.0,
            understeer_level=0.0,
            oversteer_level=0.0,
            bump_penalty=0.0,
            kerb_impact=0.0,
            kerb_severity=0.0,
            cooling_capacity=0.0,
            cooling_margin=0.0,
            airflow_penalty=0.0,
            drag_ref=30.0,
        )
        
        # ===================================================================
        # STEP 2 – Run all sections
        # ===================================================================
        all_sections: List[SectionResult] = []
        all_microsectors: List[Dict[str, Any]] = []
        
        for section_ctx in self.circuit_config.sections:
            # Run section with v2 physics
            section_result, car_state = update_section_v2(
                section_context=section_ctx,
                initial_state=car_state,
                aero_setup=car_entry.aero_setup,
                tyre_compound=car_entry.tyre_compound,
                env_context=self.env_context,
                circuit_config=self.circuit_config,
                driver_skills=car_entry.driver_config.skills,
                push_level=10,  # Full push
            )
            
            all_sections.append(section_result)
            
            # Log microsector data
            microsector_data = {
                "section_id": section_result.section_id,
                "dt_s": section_result.dt_s,
                "v_entry_kph": section_result.v_entry_kph,
                "v_exit_kph": section_result.v_exit_kph,
                "handling_penalty": section_result.handling_penalty,
                "drag_eff": section_result.drag_eff,
                "effective_grip_front": section_result.effective_grip_front,
                "effective_grip_rear": section_result.effective_grip_rear,
            }
            all_microsectors.append(microsector_data)
            
            # Update car state for next section
            car_state.current_section_idx += 1
            car_state.section_progress = 0.0
        
        # ===================================================================
        # STEP 3 – Calculate total lap time
        # ===================================================================
        total_lap_time_s = sum(s.dt_s for s in all_sections)
        
        # ===================================================================
        # STEP 4 – Calculate tyre wear and fuel consumption
        # ===================================================================
        tyre_wear = {
            "front": sum(s.effective_grip_front for s in all_sections) / len(all_sections),
            "rear": sum(s.effective_grip_rear for s in all_sections) / len(all_sections),
        }
        
        fuel_consumption = car_entry.fuel_load_kg - car_state.pu.fuel_kg
        
        # ===================================================================
        # STEP 5 – Return result
        # ===================================================================
        return LapResultV2(
            lap_time_ms=total_lap_time_s * 1000,
            sectors=all_sections,
            microsectors=all_microsectors,
            tyre_wear=tyre_wear,
            fuel_consumption=fuel_consumption,
            errors=[],
        )
    
    def run_microsector(
        self,
        car_entry: CarEntryV2,
        section_context: SectionContext,
        initial_state: CarState,
    ) -> Tuple[SectionResult, CarState]:
        """
        Run a single microsector with v2 physics
        
        Args:
            car_entry: Car configuration
            section_context: Microsector configuration
            initial_state: Starting state
            
        Returns:
            Tuple of (section_result, final_state)
        """
        # Run section with v2 physics
        section_result, final_state = update_section_v2(
            section_context=section_context,
            initial_state=initial_state,
            aero_setup=car_entry.aero_setup,
            tyre_compound=car_entry.tyre_compound,
            env_context=self.env_context,
            circuit_config=self.circuit_config,
            driver_skills=car_entry.driver_config.skills,
            push_level=10,  # Full push
        )
        
        return section_result, final_state
