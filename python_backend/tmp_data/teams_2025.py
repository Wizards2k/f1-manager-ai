"""
Teams data registry for 2025 season
Generated from race performance gaps (first 3 GPs)
NOT CONNECTED TO GAME - sandbox data only
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.models import Team, Pilota
from models import Nazionalita
from tmp_data.power_units_2025 import get_power_unit
from tmp_data.cars_2025 import get_car
from data.pilots import PILOTS


def create_team_2025(team_code: str, team_name: str, driver_names: List[str]) -> Team:
    """
    Create a Team instance with linked power unit, car, and pilots
    """
    
    # Get power unit and car
    power_unit = get_power_unit(team_code)
    car = get_car(team_code)
    
    # Get pilots
    pilots = []
    for driver_name in driver_names:
        # Find pilot by name in PILOTS dict
        pilot = None
        for pilot_code, p in PILOTS.items():
            if f"{p.nome} {p.cognome}" == driver_name:
                pilot = p
                break
        if pilot:
            pilots.append(pilot)
    
    # Team colors
    team_colors = {
        'MCL': '#FF8700',
        'RBR': '#1E41FF', 
        'FER': '#DC0000',
        'MER': '#00D2BE',
        'AST': '#006F62',
        'ALP': '#0090FF',
        'HAAS': '#FFFFFF',
        'WIL': '#005AFF',
        'SAU': '#52E252',
        'RBRB': '#6692FF'
    }
    
    # Team nationalities
    team_nationalities = {
        'MCL': Nazionalita.REGNO_UNITO,
        'RBR': Nazionalita.AUSTRIA,
        'FER': Nazionalita.ITALIA,
        'MER': Nazionalita.GERMANIA,
        'AST': Nazionalita.REGNO_UNITO,
        'ALP': Nazionalita.FRANCIA,
        'HAAS': Nazionalita.USA,
        'WIL': Nazionalita.REGNO_UNITO,
        'SAU': Nazionalita.SVIZZERA,
        'RBRB': Nazionalita.ITALIA
    }
    
    return Team(
        nome_scuderia=team_name,
        sigla_scuderia=team_code,
        nazionalita=team_nationalities.get(team_code, Nazionalita.REGNO_UNITO),
        colore_team=team_colors.get(team_code, '#000000'),
        power_unit=power_unit,
        auto=car,
        pilota1=pilots[0] if len(pilots) > 0 else None,
        pilota2=pilots[1] if len(pilots) > 1 else None,
        pilota_riserva=pilots[2] if len(pilots) > 2 else None,
        sponsor_principale=get_main_sponsor(team_code),
        simulator_quality=85
    )


def get_main_sponsor(team_code: str) -> str:
    """Get main sponsor for team"""
    sponsors = {
        'MCL': 'Shell',
        'RBR': 'Oracle',
        'FER': 'Mission Winnow',
        'MER': 'Petronas',
        'AST': 'Aramco',
        'ALP': 'BWT',
        'HAAS': 'MoneyGram',
        'WIL': 'Qatar',
        'SAU': 'Stake',
        'RBRB': 'Ford'
    }
    return sponsors.get(team_code, 'Unknown')


# Team registry for 2025 season
TEAMS_2025: Dict[str, Team] = {
    'MCL': create_team_2025('MCL', 'McLaren', ['Lando Norris', 'Oscar Piastri']),
    'RBR': create_team_2025('RBR', 'Red Bull Racing', ['Max Verstappen', 'Liam Lawson']),
    'FER': create_team_2025('FER', 'Ferrari', ['Charles Leclerc', 'Carlos Sainz']),
    'MER': create_team_2025('MER', 'Mercedes', ['George Russell', 'Lewis Hamilton']),
    'AST': create_team_2025('AST', 'Aston Martin', ['Fernando Alonso', 'Lance Stroll']),
    'ALP': create_team_2025('ALP', 'Alpine', ['Pierre Gasly', 'Esteban Ocon']),
    'HAAS': create_team_2025('HAAS', 'Haas', ['Nico Hülkenberg', 'Kevin Magnussen']),
    'WIL': create_team_2025('WIL', 'Williams', ['Alex Albon', 'Logan Sargeant']),
    'SAU': create_team_2025('SAU', 'Sauber', ['Valtteri Bottas', 'Zhou Guanyu']),
    'RBRB': create_team_2025('RBRB', 'RB', ['Yuki Tsunoda', 'Daniel Ricciardo'])
}


def get_team(team_code: str) -> Optional[Team]:
    """Get team for team code"""
    return TEAMS_2025.get(team_code)


def list_all_teams() -> Dict[str, Team]:
    """Get all teams"""
    return TEAMS_2025.copy()


def print_team_summary():
    """Print summary of all teams with performance gaps"""
    print("=== TEAMS 2025 REGISTRY ===")
    print("Code | Team Name           | Driver 1           | Driver 2           | Gap vs MCL")
    print("-" * 85)
    
    mclaren_pu = get_power_unit('MCL')
    mclaren_car = get_car('MCL')
    
    for team_code in ['MCL', 'RBR', 'FER', 'MER', 'AST', 'ALP', 'HAAS', 'WIL', 'SAU', 'RBRB']:
        team = TEAMS_2025.get(team_code)
        if not team:
            continue
            
        # Calculate performance gap
        pu = get_power_unit(team_code)
        car = get_car(team_code)
        
        if pu and car and mclaren_pu and mclaren_car:
            power_gap = ((mclaren_pu.ice.max_power_w - pu.ice.max_power_w) / mclaren_pu.ice.max_power_w) * 100
            aero_gap = ((mclaren_car.aero_package.coefficiente_aerodinamico.cz - car.aero_package.coefficiente_aerodinamico.cz) / mclaren_car.aero_package.coefficiente_aerodinamico.cz) * 100
            total_gap = power_gap + aero_gap
        else:
            total_gap = 0.0
            
        driver1_name = team.pilota1.nome_completo if team.pilota1 else "Unknown"
        driver2_name = team.pilota2.nome_completo if team.pilota2 else "Unknown"
        
        print(f"{team_code:4} | {team.nome_scuderia:19} | {driver1_name:18} | {driver2_name:18} | {total_gap:+6.2f}%")


if __name__ == "__main__":
    print_team_summary()
