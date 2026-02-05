"""Elenco piloti ufficiali con attributi base per la simulazione lap-time."""
from typing import Optional

from models import Pilota, Nazionalita


def _pilot(
    nome: str,
    cognome: str,
    naz: Nazionalita,
    eta: int,
    numero: int,
    velocita: int,
    consumo: int,
    qualifica: int,
    gara: int,
    aggressivita: int,
    gestione_carburante: int,
    ricerca_assetto: Optional[int] = None,
    stile_sottosterzo: Optional[int] = None,
    stile_sovrasterzo: Optional[int] = None,
    costanza: Optional[int] = None,
):
    return Pilota(
        nome=nome,
        cognome=cognome,
        nazionalita=naz,
        eta=eta,
        numero_di_gara=numero,
        velocita=velocita,
        consumo_gomme=consumo,
        qualifica=qualifica,
        gara=gara,
        costanza=costanza if costanza is not None else gara,
        aggressivita=aggressivita,
        gestione_carburante=gestione_carburante,
        ricerca_assetto=ricerca_assetto if ricerca_assetto is not None else 50,
        stile_sottosterzo=stile_sottosterzo if stile_sottosterzo is not None else 50,
        stile_sovrasterzo=stile_sovrasterzo if stile_sovrasterzo is not None else 50,
    )


PILOTS = {
    "LECLERC": _pilot("Charles", "Leclerc", Nazionalita.MONACO, 27, 16, 92, 78, 94, 90, 70, 70, ricerca_assetto=85),
    "SAINZ": _pilot("Carlos", "Sainz", Nazionalita.SPAGNA, 30, 55, 90, 80, 88, 85, 72, 72),
    "VERSTAPPEN": _pilot("Max", "Verstappen", Nazionalita.PAESI_BASSI, 27, 1, 98, 82, 99, 97, 68, 68),
    "PEREZ": _pilot("Sergio", "Perez", Nazionalita.MESSICO, 35, 11, 88, 84, 86, 80, 77, 77),
    "HAMILTON": _pilot("Lewis", "Hamilton", Nazionalita.REGNO_UNITO, 40, 44, 94, 79, 95, 86, 75, 75),
    "RUSSELL": _pilot("George", "Russell", Nazionalita.REGNO_UNITO, 27, 63, 91, 81, 90, 83, 73, 73),
    "NORRIS": _pilot("Lando", "Norris", Nazionalita.REGNO_UNITO, 25, 4, 93, 80, 92, 88, 70, 70),
    "PIASTRI": _pilot("Oscar", "Piastri", Nazionalita.AUSTRALIA, 24, 81, 90, 79, 89, 82, 69, 69),
    "ALONSO": _pilot("Fernando", "Alonso", Nazionalita.SPAGNA, 43, 14, 89, 83, 87, 84, 80, 80),
    "STROLL": _pilot("Lance", "Stroll", Nazionalita.CANADA, 26, 18, 80, 78, 78, 72, 74, 74),
    "OCON": _pilot("Esteban", "Ocon", Nazionalita.FRANCIA, 29, 31, 85, 80, 84, 76, 76, 76),
    "GASLY": _pilot("Pierre", "Gasly", Nazionalita.FRANCIA, 29, 10, 86, 79, 83, 78, 75, 75),
    "ALBON": _pilot("Alexander", "Albon", Nazionalita.THAILANDIA, 28, 23, 84, 77, 82, 77, 78, 78),
    "SARGEANT": _pilot("Logan", "Sargeant", Nazionalita.USA, 25, 2, 76, 74, 75, 70, 73, 73),
    "TSUNODA": _pilot("Yuki", "Tsunoda", Nazionalita.GIAPPONE, 25, 22, 84, 75, 82, 83, 71, 71),
    "RICCIARDO": _pilot("Daniel", "Ricciardo", Nazionalita.AUSTRALIA, 36, 3, 82, 78, 80, 74, 74, 74),
    "BOTTAS": _pilot("Valtteri", "Bottas", Nazionalita.FINLANDIA, 36, 77, 82, 80, 81, 72, 79, 79),
    "ZHOU": _pilot("Zhou", "Guanyu", Nazionalita.CINA, 26, 24, 78, 76, 76, 70, 75, 75),
    "HULKENBERG": _pilot("Nico", "Hülkenberg", Nazionalita.GERMANIA, 38, 27, 81, 78, 80, 74, 78, 78),
    "MAGNUSSEN": _pilot("Kevin", "Magnussen", Nazionalita.DANIMARCA, 32, 20, 80, 75, 79, 78, 72, 72),
    "LAWSON": _pilot("Liam", "Lawson", Nazionalita.NUOVA_ZELANDA, 23, 30, 83, 76, 82, 79, 72, 72),
    "ANTONELLI": _pilot("Andrea Kimi", "Antonelli", Nazionalita.ITALIA, 19, 12, 88, 76, 85, 80, 70, 70),
    "BEARMAN": _pilot("Oliver", "Bearman", Nazionalita.REGNO_UNITO, 20, 87, 82, 77, 80, 78, 68, 68),
    "BORTOLETO": _pilot("Gabriel", "Bortoleto", Nazionalita.BRASILE, 21, 5, 79, 75, 78, 76, 69, 69),
    "COLAPINTO": _pilot("Franco", "Colapinto", Nazionalita.ARGENTINA, 22, 43, 81, 76, 80, 78, 70, 70),
    "HADJAR": _pilot("Isack", "Hadjar", Nazionalita.FRANCIA, 21, 6, 80, 75, 79, 77, 71, 71),
}

__all__ = ["PILOTS"]
