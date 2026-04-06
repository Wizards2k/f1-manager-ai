"""
Team & Driver Data Loader per Physics Engine V4

Carica i dati reali di team e driver dal simulatore esistente
e li fornisce al Physics Engine V4 per simulazioni realistiche.

Dati caricati:
- Team: aero modifiers, suspension efficiency, PU provider
- Driver: skill, preferenze setup, driving style
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TeamAeroParams:
    """Parametri aerodinamici specifici del team."""
    front_wing_df_modifier: float = 1.0
    front_wing_drag_modifier: float = 1.0
    rear_wing_df_modifier: float = 1.0
    rear_wing_drag_modifier: float = 1.0
    floor_df_modifier: float = 1.0
    floor_drag_modifier: float = 1.0
    sidepods_df_modifier: float = 1.0
    sidepods_drag_modifier: float = 1.0


@dataclass
class DriverSkill:
    """Skill e preferenze di un driver."""
    name: str
    quali_skill: float = 1.0  # moltiplicatore (1.0 = medio, 1.05 = +5%)
    race_skill: float = 1.0
    braking_skill: float = 1.0
    cornering_skill: float = 1.0
    throttle_skill: float = 1.0
    consistency: float = 1.0
    # Preferenze setup
    front_wing_offset: int = 0
    rear_wing_offset: int = 0
    brake_bias_offset: float = 0.0


@dataclass
class TeamData:
    """Dati completi di un team F1."""
    team_id: str
    name: str
    aero: TeamAeroParams
    suspension_efficiency: float = 0.9
    pu_provider: str = "mercedes"


class TeamDriverLoader:
    """
    Carica e gestisce dati team e driver per Physics V4.
    
    Usage:
        loader = TeamDriverLoader()
        mclaren = loader.get_team("mclaren")
        norris = loader.get_driver("Lando Norris")
        
        # Usa in simulazione V4
        result = integrate_lap_hd(
            circuit_id="it-1922_monza",
            team_data=mclaren,
            driver_data=norris,
            aero_setup={"front_wing": 14.0, "rear_wing": 12.0},
            ...
        )
    """
    
    def __init__(self):
        self.teams_data = {}
        self.drivers_data = {}
        self._load_teams()
        self._load_drivers()
    
    def _load_teams(self):
        """Carica dati team da teams_2025.json."""
        # Path corretto: python_backend/data/teams_2025.json
        teams_file = Path(__file__).parent.parent.parent / "data" / "teams_2025.json"
        
        if not teams_file.exists():
            # Fallback: prova path alternativo
            teams_file = Path(__file__).parent.parent.parent.parent / "data" / "teams_2025.json"
        
        if not teams_file.exists():
            print(f"Warning: teams file not found: {teams_file}")
            return
        
        with open(teams_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for team_json in data.get("teams", []):
            team_id = team_json["team_id"]
            aero_json = team_json.get("base_aero", {})
            
            aero = TeamAeroParams(
                front_wing_df_modifier=aero_json.get("front_wing_df_modifier", 1.0),
                front_wing_drag_modifier=aero_json.get("front_wing_drag_modifier", 1.0),
                rear_wing_df_modifier=aero_json.get("rear_wing_df_modifier", 1.0),
                rear_wing_drag_modifier=aero_json.get("rear_wing_drag_modifier", 1.0),
                floor_df_modifier=aero_json.get("floor_df_modifier", 1.0),
                floor_drag_modifier=aero_json.get("floor_drag_modifier", 1.0),
                sidepods_df_modifier=aero_json.get("sidepods_df_modifier", 1.0),
                sidepods_drag_modifier=aero_json.get("sidepods_drag_modifier", 1.0),
            )
            
            team = TeamData(
                team_id=team_id,
                name=team_json.get("name", team_id),
                aero=aero,
                suspension_efficiency=team_json.get("suspension_efficiency", 0.9),
                pu_provider=team_json.get("pu_provider", "mercedes"),
            )
            
            self.teams_data[team_id] = team
    
    def _load_drivers(self):
        """Carica dati driver da team_offsets.json."""
        offsets_file = Path(__file__).parent.parent.parent.parent.parent / "config" / "setup" / "team_offsets.json"
        
        if not offsets_file.exists():
            print(f"Warning: offsets file not found: {offsets_file}")
            return
        
        with open(offsets_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Estrai driver da ogni team
        for team_name, team_data in data.items():
            if team_name == "metadata":
                continue
            
            drivers_json = team_data.get("drivers", {})
            team_offsets = team_data.get("team", {})
            
            for driver_name, driver_offsets in drivers_json.items():
                # Skill base (da migliorare con dati reali)
                skill = 1.0
                if "Norris" in driver_name:
                    skill = 1.05  # Norris è top driver
                elif "Verstappen" in driver_name:
                    skill = 1.08
                elif "Hamilton" in driver_name:
                    skill = 1.04
                
                driver = DriverSkill(
                    name=driver_name,
                    quali_skill=skill,
                    race_skill=skill,
                    braking_skill=skill,
                    cornering_skill=skill,
                    throttle_skill=skill,
                    consistency=1.0,
                    front_wing_offset=driver_offsets.get("front_wing", 0),
                    rear_wing_offset=driver_offsets.get("rear_wing", 0),
                    brake_bias_offset=driver_offsets.get("brake_bias", 0.0),
                )
                
                self.drivers_data[driver_name] = driver
    
    def get_team(self, team_id: str) -> Optional[TeamData]:
        """
        Ottieni dati di un team.
        
        Args:
            team_id: ID team (es. "mclaren", "ferrari", "red_bull")
        
        Returns:
            TeamData o None se non trovato
        """
        return self.teams_data.get(team_id)
    
    def get_driver(self, driver_name: str) -> Optional[DriverSkill]:
        """
        Ottieni dati di un driver.
        
        Args:
            driver_name: Nome completo (es. "Lando Norris")
        
        Returns:
            DriverSkill o None se non trovato
        """
        return self.drivers_data.get(driver_name)
    
    def get_team_by_driver(self, driver_name: str) -> Optional[TeamData]:
        """
        Ottieni il team di un driver.
        
        Args:
            driver_name: Nome completo del driver
        
        Returns:
            TeamData del team o None
        """
        # Cerca in team_offsets.json
        offsets_file = Path(__file__).parent.parent.parent.parent.parent / "config" / "setup" / "team_offsets.json"
        
        if not offsets_file.exists():
            return None
        
        with open(offsets_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for team_name, team_data in data.items():
            if team_name == "metadata":
                continue
            
            if driver_name in team_data.get("drivers", {}):
                # Trovato! Ora cerca team_id corrispondente
                team_id_map = {
                    "McLaren": "mclaren",
                    "Ferrari": "ferrari",
                    "Red Bull": "red_bull",
                    "Mercedes": "mercedes",
                    "Aston Martin": "aston_martin",
                    "Alpine": "alpine",
                }
                team_id = team_id_map.get(team_name, team_name.lower())
                return self.get_team(team_id)
        
        return None


# Singleton instance
_loader_instance = None


def get_loader() -> TeamDriverLoader:
    """Ottieni istanza singleton del loader."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = TeamDriverLoader()
    return _loader_instance


def get_team_data(team_id: str) -> Optional[TeamData]:
    """Convenience function: ottieni dati team."""
    return get_loader().get_team(team_id)


def get_driver_data(driver_name: str) -> Optional[DriverSkill]:
    """Convenience function: ottieni dati driver."""
    return get_loader().get_driver(driver_name)
