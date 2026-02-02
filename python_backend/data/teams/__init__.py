"""Roster ufficiale delle scuderie con forza auto e piloti titolari."""

from models import Team, Nazionalita
from data.pilots import PILOTS

TEAMS = [
    Team(
        nome_scuderia="Oracle Red Bull Racing",
        sigla_scuderia="RBR",
        nazionalita=Nazionalita.AUSTRIA,
        colore_team="#0600EF",
        forza_auto=91,
        power_unit="Honda RBPT",
        piloti_titolari=[PILOTS["VERSTAPPEN"], PILOTS["PEREZ"]],
    ),
    Team(
        nome_scuderia="Scuderia Ferrari",
        sigla_scuderia="FER",
        nazionalita=Nazionalita.ITALIA,
        colore_team="#DC0000",
        forza_auto=87,
        power_unit="Ferrari 066/10",
        piloti_titolari=[PILOTS["LECLERC"], PILOTS["SAINZ"]],
    ),
    Team(
        nome_scuderia="Mercedes-AMG PETRONAS",
        sigla_scuderia="MER",
        nazionalita=Nazionalita.GERMANIA,
        colore_team="#00A19C",
        forza_auto=85,
        power_unit="Mercedes-AMG F1 M14",
        piloti_titolari=[PILOTS["HAMILTON"], PILOTS["RUSSELL"]],
    ),
    Team(
        nome_scuderia="McLaren F1 Team",
        sigla_scuderia="MCL",
        nazionalita=Nazionalita.REGNO_UNITO,
        colore_team="#FF8700",
        forza_auto=95,
        power_unit="Mercedes-AMG",
        piloti_titolari=[PILOTS["NORRIS"], PILOTS["PIASTRI"]],
    ),
    Team(
        nome_scuderia="Aston Martin Aramco",
        sigla_scuderia="AMR",
        nazionalita=Nazionalita.REGNO_UNITO,
        colore_team="#006F62",
        forza_auto=82,
        power_unit="Mercedes-AMG",
        piloti_titolari=[PILOTS["ALONSO"], PILOTS["STROLL"]],
    ),
    Team(
        nome_scuderia="BWT Alpine F1 Team",
        sigla_scuderia="ALP",
        nazionalita=Nazionalita.FRANCIA,
        colore_team="#0090FF",
        forza_auto=79,
        power_unit="Renault E-Tech",
        piloti_titolari=[PILOTS["OCON"], PILOTS["GASLY"]],
    ),
    Team(
        nome_scuderia="Williams Racing",
        sigla_scuderia="WIL",
        nazionalita=Nazionalita.REGNO_UNITO,
        colore_team="#00A0DE",
        forza_auto=76,
        power_unit="Mercedes-AMG",
        piloti_titolari=[PILOTS["ALBON"], PILOTS["SARGEANT"]],
    ),
    Team(
        nome_scuderia="Visa Cash App RB",
        sigla_scuderia="RB",
        nazionalita=Nazionalita.ITALIA,
        colore_team="#1E2C5C",
        forza_auto=77,
        power_unit="Honda RBPT",
        piloti_titolari=[PILOTS["TSUNODA"], PILOTS["RICCIARDO"]],
    ),
    Team(
        nome_scuderia="Stake F1 Team Kick Sauber",
        sigla_scuderia="SAU",
        nazionalita=Nazionalita.SVIZZERA,
        colore_team="#00FF87",
        forza_auto=73,
        power_unit="Ferrari 066/10",
        piloti_titolari=[PILOTS["BOTTAS"], PILOTS["ZHOU"]],
    ),
    Team(
        nome_scuderia="MoneyGram Haas F1 Team",
        sigla_scuderia="HAA",
        nazionalita=Nazionalita.USA,
        colore_team="#B6BABD",
        forza_auto=71,
        power_unit="Ferrari 066/10",
        piloti_titolari=[PILOTS["HULKENBERG"], PILOTS["MAGNUSSEN"]],
    ),
]

for idx, team in enumerate(TEAMS, start=1):
    setattr(team, "team_id", idx)

__all__ = ["TEAMS"]
