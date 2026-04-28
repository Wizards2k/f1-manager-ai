"""
session_bridge_v2.py - Session Bridge Parallelo per Validazione Physics Engine v2

Questo modulo implementa una versione parallela di SessionBridge che usa
il nuovo motore fisico v2 (update_section_v2) invece del motore v1 (update_section).

Il motore v2 ├¿ completamente indipendente da v1 e viene usato SOLO per:
1. Confronto con v1 microsettore per microsettore
2. Validazione contro telemetria Q3
3. Verifica che setup diversi producano tempi diversi in modo fisicamente coerente

USO:
- session_bridge.py = motore v1 (produzione)
- session_bridge_v2.py = motore v2 (validazione parallela)
- scripts/compare_engines.py = confronto v1 vs v2

Reference: docs/lap-physics-spec-v0.5.md, docs/lap-physics-v2-analysis.md
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from lap_simulator.ai_data_types import (
    AIDriverConfig,
    AITeamConfig,
    RunProgram,
    RUN_PROGRAM_DEFAULTS,
    SessionType,
)
from utils.ai_setup_search import AISetupState
from lap_simulator.ai_driver_engine import AIDriverEngine
from lap_simulator.config_loader import load_circuit_config
from lap_simulator.data_types import (
    AeroSetup,
    CarState as SimCarState,
    CircuitConfig,
    EnvContext,
    SectionContext,
    SectionResult,
    TyreCompound,
    EngineMapName,
)
from lap_simulator.update_section_v2 import update_section_v2  # Fisica v2 pura
# from lap_simulator.update_section import update_section  # Fallback a v1 per ora
from lap_simulator.battle_resolver import (
    BattleEvent,
    BattleOutcome,
    BattleResolver,
    BattleResult,
)
from lap_simulator.practice_session import (
    CarPhase,
    PracticeEventType,
    PracticeSessionOrchestrator,
    SessionFlag,
)
from utils.qualifying_session import DEFAULT_QUALIFYING_PHASE_DURATIONS_S

from utils.adapter import (
    game_compound_to_sim,
    pilot_to_driver_skills,
    racecar_to_car_entry,
    set_racecar_phase,
    sim_compound_to_game,
)
from utils.microsector_logger import log_microsector
from utils.pu_telemetry_logger import log_pu_section
from utils.driver_feedback import (
    get_driver_feedback,
    should_trigger_feedback,
    emit_thermal_feedback,
)
from config import get_current_circuit_profile
from services.tyre_inventory_service import TyreInventoryService
from models.models import TireCompound as GameTireCompound
from debug_log import log_debug_event

logger = logging.getLogger(__name__)

# Flag per abilitare/disabilitare v2
ENABLE_V2_ENGINE = False  # Default: v1 in produzione, v2 in validazione

if ENABLE_V2_ENGINE:
    logger.warning("ÔÜá´©Å  session_bridge_v2.py: V2 ENGINE ABILITATO - USARE SOLO PER VALIDAZIONE")
else:
    logger.info("Ôä╣´©Å  session_bridge_v2.py: V2 ENGINE DISABILITATO - USARE session_bridge.py PER PRODUZIONE")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_DURATION_S = 3600
OUT_LAP_SPEED_FACTOR = 0.65     # out lap ~65% of reference speed
IN_LAP_SPEED_FACTOR = 0.70      # in lap ~70% of reference speed
SLOW_LAP_SPEED_FACTOR = 0.75    # slow/cooldown lap
