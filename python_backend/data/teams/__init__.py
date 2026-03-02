"""Roster ufficiale delle scuderie 2025 con auto e power unit promotati dal sandbox."""

from typing import Dict, List

from models import Team, Nazionalita
from data.pilots import PILOTS
from data.power_units import get_power_unit
from data.cars import get_car


TEAM_METADATA: Dict[str, Dict[str, str]] = {
    "RBR": {
        "nome": "Oracle Red Bull Racing",
        "colore": "#0600EF",
        "sponsor": "Oracle",
        "naz": Nazionalita.AUSTRIA,
    },
    "FER": {
        "nome": "Scuderia Ferrari",
        "colore": "#DC0000",
        "sponsor": "Mission Winnow",
        "naz": Nazionalita.ITALIA,
    },
    "MER": {
        "nome": "Mercedes-AMG PETRONAS",
        "colore": "#00A19C",
        "sponsor": "Petronas",
        "naz": Nazionalita.GERMANIA,
    },
    "MCL": {
        "nome": "McLaren F1 Team",
        "colore": "#FF8700",
        "sponsor": "Gulf",
        "naz": Nazionalita.REGNO_UNITO,
    },
    "AST": {
        "nome": "Aston Martin Aramco",
        "colore": "#006F62",
        "sponsor": "Aramco",
        "naz": Nazionalita.REGNO_UNITO,
    },
    "ALP": {
        "nome": "BWT Alpine F1 Team",
        "colore": "#0090FF",
        "sponsor": "BWT",
        "naz": Nazionalita.FRANCIA,
    },
    "WIL": {
        "nome": "Williams Racing",
        "colore": "#00A0DE",
        "sponsor": "Qatar Airways",
        "naz": Nazionalita.REGNO_UNITO,
    },
    "RB": {
        "nome": "Visa Cash App RB",
        "colore": "#1E2C5C",
        "sponsor": "Visa",
        "naz": Nazionalita.ITALIA,
    },
    "SAU": {
        "nome": "Stake F1 Team Kick Sauber",
        "colore": "#00FF87",
        "sponsor": "Stake",
        "naz": Nazionalita.SVIZZERA,
    },
    "HAAS": {
        "nome": "MoneyGram Haas F1 Team",
        "colore": "#B6BABD",
        "sponsor": "MoneyGram",
        "naz": Nazionalita.USA,
    },
}

TEAM_DRIVERS: Dict[str, List[str]] = {
    "RBR": ["VERSTAPPEN", "TSUNODA"],
    "FER": ["LECLERC", "HAMILTON"],
    "MER": ["RUSSELL", "ANTONELLI"],
    "MCL": ["NORRIS", "PIASTRI"],
    "AST": ["ALONSO", "STROLL"],
    "ALP": ["GASLY", "COLAPINTO"],
    "WIL": ["ALBON", "SAINZ"],
    "RB": ["LAWSON", "HADJAR"],
    "SAU": ["HULKENBERG", "BORTOLETO"],
    "HAAS": ["OCON", "BEARMAN"],
}


def _build_team(team_code: str) -> Team:
    meta = TEAM_METADATA[team_code]
    driver_codes = TEAM_DRIVERS[team_code]

    return Team(
        nome_scuderia=meta["nome"],
        sigla_scuderia=team_code,
        nazionalita=meta["naz"],
        colore_team=meta["colore"],
        power_unit=get_power_unit(team_code),
        auto=get_car(team_code),
        pilota1=PILOTS[driver_codes[0]],
        pilota2=PILOTS[driver_codes[1]],
        sponsor_principale=meta["sponsor"],
        simulator_quality=85,
    )


TEAMS = [_build_team(code) for code in TEAM_METADATA.keys()]

for idx, team in enumerate(TEAMS, start=1):
    setattr(team, "team_id", idx)

__all__ = ["TEAMS"]
