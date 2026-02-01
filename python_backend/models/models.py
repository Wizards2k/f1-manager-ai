# Models F1 Manager AI - Solo classi, senza logica di posizione
import time
import random
import math
from enum import Enum, auto
from typing import Any, Dict, List, Optional

try:
    import config
except ImportError:  # pragma: no cover - fallback per contesti standalone
    config = None

print("MODELS: Caricate classi base (senza logica posizione)")


class CarState(Enum):
    """Stati possibili per le auto durante la sessione."""
    BOX = "BOX"
    OUT_LAP = "OUT LAP"
    HOT_LAP = "HOT LAP"
    IN_LAP = "IN LAP"


class MathUtils:
    @staticmethod
    def clamp(value, min_value, max_value):
        return max(min_value, min(max_value, value))


class Nazionalita(Enum):
    ITALIA = "ITA"
    REGNO_UNITO = "GBR"
    GERMANIA = "GER"
    SPAGNA = "ESP"
    FRANCIA = "FRA"
    PAESI_BASSI = "NED"
    AUSTRALIA = "AUS"
    GIAPPONE = "JPN"
    USA = "USA"
    BRASILE = "BRA"
    CANADA = "CAN"
    FINLANDIA = "FIN"
    MONACO = "MON"
    MESSICO = "MEX"
    THAILANDIA = "THA"
    DANIMARCA = "DNK"
    CINA = "CHN"
    AUSTRIA = "AUT"
    SVIZZERA = "CHE"


class TireCompound(Enum):
    """Tipi di gomme F1"""
    SOFT = "soft"
    MEDIUM = "medium"
    HARD = "hard"
    INTERMEDIATE = "intermediate"
    WET = "wet"


class Pilota:
    F1_OFFICIAL_ABBREVIATIONS = {
        "Charles Leclerc": "LEC",
        "Carlos Sainz": "SAI",
        "Max Verstappen": "VER",
        "Sergio Perez": "PER",
        "Lewis Hamilton": "HAM",
        "George Russell": "RUS",
        "Lando Norris": "NOR",
        "Oscar Piastri": "PIA",
        "Fernando Alonso": "ALO",
        "Lance Stroll": "STR",
        "Esteban Ocon": "OCO",
        "Pierre Gasly": "GAS",
        "Alexander Albon": "ALB",
        "Logan Sargeant": "SAR",
        "Valtteri Bottas": "BOT",
        "Zhou Guanyu": "ZHO",
        "Kevin Magnussen": "MAG",
        "Nico Hulkenberg": "HUL",
        "Yuki Tsunoda": "TSU",
        "Daniel Ricciardo": "RIC",
        "Liam Lawson": "LAW",
        "Nyck de Vries": "DEV",
        "Antonio Giovinazzi": "GIO",
        "Robert Kubica": "KUB",
    }

    def __init__(
        self,
        nome: str,
        cognome: str,
        nazionalita: Nazionalita,
        eta: int,
        numero_di_gara: int,
        punti_mondiale_attuale: int = 0,
        punti_mondiale_carriera: int = 0,
        campionati_vinti: int = 0,
        giri_veloci: int = 0,
        gp_disputati: int = 0,
        gp_vinti: int = 0,
        pole_position: int = 0,
        abbreviazione: Optional[str] = None,
        velocita: int = 50,
        consumo_gomme: int = 50,
        qualifica: int = 50,
        sorpasso: int = 50,
        aggressivita: int = 50,
        ricerca_assetto: int = 50,
        stile_sottosterzo: int = 50,
        stile_sovrasterzo: int = 50,
        costanza: int = 50,
        gara: int = 50,
        gestione_carburante: int = 50,
    ):
        self.nome = nome
        self.cognome = cognome
        self.nazionalita = nazionalita
        self.eta = eta
        self.numero_di_gara = numero_di_gara
        self.punti_mondiale_attuale = punti_mondiale_attuale
        self.punti_mondiale_carriera = punti_mondiale_carriera
        self.campionati_vinti = campionati_vinti
        self.giri_veloci = giri_veloci
        self.gp_disputati = gp_disputati
        self.gp_vinti = gp_vinti
        self.pole_position = pole_position

        self._velocita = 50
        self._consumo_gomme = 50
        self._qualifica = 50
        self._sorpasso = 50
        self._aggressivita = 50
        self._ricerca_assetto = 50
        self._stile_sottosterzo = 50
        self._stile_sovrasterzo = 50
        self._costanza = 50
        self._gara = 50
        self._gestione_carburante = 50

        self.velocita = velocita
        self.consumo_gomme = consumo_gomme
        self.qualifica = qualifica
        self.sorpasso = sorpasso
        self.aggressivita = aggressivita
        self.ricerca_assetto = ricerca_assetto
        self.stile_sottosterzo = stile_sottosterzo
        self.stile_sovrasterzo = stile_sovrasterzo
        self.costanza = costanza
        self.gara = gara
        self.gestione_carburante = gestione_carburante

        nome_completo = f"{self.nome} {self.cognome}"
        self.abbreviazione = (
            abbreviazione
            or self.F1_OFFICIAL_ABBREVIATIONS.get(nome_completo)
            or (self.nome[0] + self.cognome[:2]).upper()
        )

    @property
    def nome_completo(self) -> str:
        return f"{self.nome} {self.cognome}"

    @property
    def iniziali(self) -> str:
        return f"{self.nome[0]}{self.cognome[0]}".upper()

    @property
    def velocita(self) -> int:
        return self._velocita

    @velocita.setter
    def velocita(self, value: int):
        self._velocita = MathUtils.clamp(value, 1, 100)

    @property
    def consumo_gomme(self) -> int:
        return self._consumo_gomme

    @consumo_gomme.setter
    def consumo_gomme(self, value: int):
        self._consumo_gomme = MathUtils.clamp(value, 1, 100)

    @property
    def qualifica(self) -> int:
        return self._qualifica

    @qualifica.setter
    def qualifica(self, value: int):
        min_q = max(1, self.velocita - 10)
        max_q = min(100, self.velocita + 10)
        self._qualifica = MathUtils.clamp(value, min_q, max_q)

    @property
    def sorpasso(self) -> int:
        return self._sorpasso

    @sorpasso.setter
    def sorpasso(self, value: int):
        self._sorpasso = MathUtils.clamp(value, 1, 100)

    @property
    def aggressivita(self) -> int:
        return self._aggressivita

    @aggressivita.setter
    def aggressivita(self, value: int):
        self._aggressivita = MathUtils.clamp(value, 1, 100)

    @property
    def ricerca_assetto(self) -> int:
        return self._ricerca_assetto

    @ricerca_assetto.setter
    def ricerca_assetto(self, value: int):
        self._ricerca_assetto = MathUtils.clamp(value, 1, 100)

    @property
    def stile_sottosterzo(self) -> int:
        return self._stile_sottosterzo

    @stile_sottosterzo.setter
    def stile_sottosterzo(self, value: int):
        self._stile_sottosterzo = MathUtils.clamp(value, 1, 100)

    @property
    def stile_sovrasterzo(self) -> int:
        return self._stile_sovrasterzo

    @stile_sovrasterzo.setter
    def stile_sovrasterzo(self, value: int):
        self._stile_sovrasterzo = MathUtils.clamp(value, 1, 100)

    @property
    def costanza(self) -> int:
        return self._costanza

    @costanza.setter
    def costanza(self, value: int):
        self._costanza = MathUtils.clamp(value, 1, 100)

    @property
    def gara(self) -> int:
        return self._gara

    @gara.setter
    def gara(self, value: int):
        self._gara = MathUtils.clamp(value, 1, 100)

    @property
    def gestione_carburante(self) -> int:
        return self._gestione_carburante

    @gestione_carburante.setter
    def gestione_carburante(self, value: int):
        self._gestione_carburante = MathUtils.clamp(value, 1, 100)


class Gomma:
    BONUS_LAP_TIME = {
        TireCompound.SOFT: 1.5,
        TireCompound.MEDIUM: 0.7,
        TireCompound.HARD: 0.2,
    }

    DEGRADO_BASE = {
        TireCompound.SOFT: 0.08,
        TireCompound.MEDIUM: 0.05,
        TireCompound.HARD: 0.03,
    }

    MALUS_COEFF = {
        TireCompound.SOFT: 2.2,
        TireCompound.MEDIUM: 1.8,
        TireCompound.HARD: 1.4,
    }

    def __init__(self, mescola: TireCompound, percentuale_vita: float = 1.0):
        if mescola not in (TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD):
            raise ValueError("Questa classe gestisce solo mescole slick S/M/H")

        self.mescola = mescola
        self.percentuale_vita = MathUtils.clamp(percentuale_vita, 0.0, 1.0)

    def aggiorna_degrado(self, delta: Optional[float] = None):
        consumo = delta if delta is not None else self.DEGRADO_BASE[self.mescola]
        self.percentuale_vita = MathUtils.clamp(self.percentuale_vita - consumo, 0.0, 1.0)

    def impatto_su_laptime(self) -> float:
        grip = self.percentuale_vita
        bonus_base = self.BONUS_LAP_TIME[self.mescola]

        if grip >= 0.9:
            return -bonus_base
        if grip >= 0.5:
            ratio = (grip - 0.5) / 0.4
            return -(bonus_base * ratio)

        malus_coeff = self.MALUS_COEFF[self.mescola]
        malus = (0.5 - grip) * malus_coeff
        return malus


class Team:
    def __init__(
        self,
        nome_scuderia: str,
        sigla_scuderia: str,
        nazionalita: Nazionalita,
        colore_team: str,
        forza_auto: int,
        power_unit: str = "",
        sponsor_principale: str = "",
        piloti_titolari: Optional[List[Pilota]] = None,
    ):
        self.nome_scuderia = nome_scuderia
        self.sigla_scuderia = sigla_scuderia
        self.nazionalita = nazionalita
        self.colore_team = colore_team
        self.power_unit = power_unit
        self.sponsor_principale = sponsor_principale
        self.piloti_titolari = piloti_titolari or []

        self.forza_auto = MathUtils.clamp(forza_auto, 0, 100)
        self.affidabilita = 75
        self.aerodinamica = 70
        self.meccanica = 70
        self.efficienza_pit = 80

    def aggiungi_pilota(self, pilota: Pilota):
        self.piloti_titolari.append(pilota)

    @property
    def bonus_prestazione(self) -> float:
        return self.forza_auto * 0.1


class RaceCar:
    def __init__(self, pilot: Pilota, team: Team, initial_compound: TireCompound = TireCompound.MEDIUM):
        self.pilot = pilot
        self.team = team
        self.driver_number = pilot.numero_di_gara
        self.driver_name = pilot.nome_completo
        self.team_name = team.nome_scuderia
        self.team_color = team.colore_team
        
        # Posizione e movimento
        self.distance_traveled = 0
        self.speed = random.uniform(15, 25)  # m/s
        self.target_speed = 0
        
        # Stato della sessione
        self.state = CarState.BOX
        self.current_lap_start = None
        self.lap_count = 0
        self.total_laps = 0
        self.total_session_laps = 0
        self.last_lap_type = None
        
        # Tempi e performance
        self.lap_times = []
        self.sector_times = []
        self.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.last_sector_times = {'sector1': None, 'sector2': None, 'sector3': None}
        self.best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.current_lap_debug: Optional[Dict[str, Any]] = None
        
        # Gestione stint
        self.stint_target_laps = random.randint(8, 15)
        self.stint_laps_remaining = self.stint_target_laps
        self.box_time_until = 0
        self.session_start_time = None
        self.sector3_start_time = None
        
        # Gestione gomme
        self.current_tire = initial_compound
        self.current_gomma = Gomma(initial_compound, percentuale_vita=1.0)
        self.tire_age = 0
        self.tire_wear = 0.0

        # Player control & configurazioni
        self.is_player_controlled = False
        self.max_fuel_laps_at_100 = 12
        self.fuel_percent = 100
        self.pace_level = 5
        self.ice_mode = "Standard"
        self.ers_mode = "Neutral"
        self.player_config: Dict[str, Any] = {
            "tyre_compound": self.current_tire.value,
            "fuel_percent": self.fuel_percent,
            "pace_level": self.pace_level,
            "ice_mode": self.ice_mode,
            "ers_mode": self.ers_mode,
            "stint_target_laps": self.stint_target_laps,
        }
        self.setup_feedback: Optional[Dict[str, Any]] = None

    def set_tire_compound(self, compound, percentuale_vita: float = 1.0):
        """Imposta il compound di gomme"""
        self.current_tire = compound
        self.current_gomma = Gomma(compound, percentuale_vita=percentuale_vita)
        self.tire_age = 0
        self.tire_wear = 0.0
        self.player_config["tyre_compound"] = self.current_tire.value

    def update_tire_wear(self):
        """Aggiorna l'usura delle gomme"""
        if self.state == CarState.HOT_LAP:
            self.tire_age += 1
            if self.current_tire in (TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD):
                self.current_gomma.aggiorna_degrado()
                self.tire_wear = 1.0 - self.current_gomma.percentuale_vita
            else:
                # Mantieni logica semplice per intermedie/wet finché non modellate
                wear_increment = 0.04 if self.current_tire == TireCompound.INTERMEDIATE else 0.02
                self.tire_wear = min(1.0, self.tire_wear + wear_increment)

    def get_position(self):
        """Restituisce coordinate attuali lungo il circuito"""
        # La logica di posizione rimane in app.py per evitare import circolari
        return None  # Sarà gestito dall'esterno
        
    def exit_box(self):
        """Auto esce dai box per nuova stint"""
        self.state = CarState.OUT_LAP
        self.stint_laps_remaining = self.stint_target_laps
        self.current_lap_start = time.time()
        self.distance_traveled = 0
        
        # Resetta settori per nuovo stint
        self.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.sector3_start_time = None
        
        if not self.is_player_controlled:
            # AI: scegli gomme casuali per la nuova stint
            available_compounds = [TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD]
            new_tire = random.choice(available_compounds)
            self.set_tire_compound(new_tire)
        
    def enter_box(self):
        """Auto rientra ai box"""
        self.state = CarState.BOX
        if self.is_player_controlled:
            self.box_time_until = float("inf")
        else:
            # Tempo ai box per la prossima uscita (5-20 minuti)
            self.box_time_until = time.time() - self.session_start_time + random.uniform(300, 1200)
        self.distance_traveled = 0
        
    def complete_lap(self, lap_type):
        """Registra tempo sul giro in base al tipo (tempi reali non influenzati da velocità gioco)"""
        lap_time = time.time() - self.current_lap_start
        
        # Tempi realistici in base al tipo di giro (sempre basati su velocità reale)
        if lap_type == CarState.OUT_LAP:
            # Out lap più lento
            realistic_lap_time = 85.0 + random.uniform(-2.0, 2.0)
            realistic_lap_time += 30.0  # delta pit lane per il primo settore
        elif lap_type == CarState.HOT_LAP:
            # Hot lap con tempi migliori
            # Se abbiamo i 3 settori, rendi il lap time coerente con la somma dei settori
            s1 = self.current_lap_sectors.get('sector1')
            s2 = self.current_lap_sectors.get('sector2')
            s3 = self.current_lap_sectors.get('sector3')
            if s1 is not None and s2 is not None and s3 is not None:
                realistic_lap_time = (s1 + s2 + s3) + random.uniform(-0.15, 0.15)
            else:
                realistic_lap_time = 79.5 + random.uniform(-2.5, 2.5)
        elif lap_type == CarState.IN_LAP:
            # In lap più lento
            realistic_lap_time = 88.0 + random.uniform(-3.0, 3.0)
        else:
            realistic_lap_time = 80.0 + random.uniform(-3.0, 3.0)
            
        self.lap_times.append(realistic_lap_time)
        self.total_laps += 1
        self.total_session_laps += 1
        self.last_lap_type = lap_type
        
        # Aggiorna usura gomme
        self.update_tire_wear()
        self.consume_fuel(lap_type)
        
        # Aggiorna miglior tempo in sessione
        if not hasattr(self, 'best_lap_time') or realistic_lap_time < self.best_lap_time:
            self.best_lap_time = realistic_lap_time
            # Snapshot dei settori del best lap (stesso giro) per delta coerenti
            self.best_lap_sectors = {
                'sector1': self.current_lap_sectors.get('sector1'),
                'sector2': self.current_lap_sectors.get('sector2'),
                'sector3': self.current_lap_sectors.get('sector3')
            }
            # Aggiorna session bests
            from utils.game_logic import update_session_bests
            update_session_bests(self)

        self._persist_lap_debug(lap_type, realistic_lap_time)

    def compute_max_stint_laps(self, fuel_percent: int) -> int:
        """Calcola il numero massimo di giri consentiti dal fuel percentuale."""
        fuel_percent = MathUtils.clamp(fuel_percent, 1, 100)
        estimated = math.floor((fuel_percent / 100.0) * self.max_fuel_laps_at_100)
        return max(1, estimated)

    def consume_fuel(self, lap_type: CarState):
        if not self.is_player_controlled:
            return
        base_burn = 100.0 / max(1, self.max_fuel_laps_at_100)
        if lap_type == CarState.HOT_LAP:
            factor = 1.0
        elif lap_type == CarState.OUT_LAP or lap_type == CarState.IN_LAP:
            factor = 0.8
        else:
            factor = 0.5
        self.fuel_percent = max(1.0, self.fuel_percent - base_burn * factor)
        self.player_config['fuel_percent'] = int(round(self.fuel_percent))

    def _persist_lap_debug(self, lap_type, lap_time: float):
        bucket = getattr(self, 'current_lap_debug', None)
        if not bucket:
            bucket = {
                'lap_sequence': self.total_laps,
                'sectors': [],
            }
            self.current_lap_debug = bucket

        bucket.setdefault('sectors', [])

        try:
            from utils.performance import compute_projected_lap_time

            _, model_debug = compute_projected_lap_time(self)
        except Exception:  # pragma: no cover
            model_debug = {}

        circuit_id = getattr(config, "current_circuit", None) if config else None
        try:
            circuit_profile = config.get_current_circuit_profile() if config else None
        except Exception:  # pragma: no cover
            circuit_profile = None
        circuit_name = circuit_profile.get("name") if circuit_profile else None

        bucket.update({
            'pilot': self.driver_name,
            'team': self.team_name,
            'driver_number': self.driver_number,
            'lap_type': lap_type.value if isinstance(lap_type, CarState) else str(lap_type),
            'lap_time_realistic': lap_time,
            'lap_time_sectors_sum': sum(
                sector.get('time', 0.0) for sector in bucket['sectors']
            ) if bucket['sectors'] else None,
            'tire_compound': getattr(self.current_tire, 'value', str(self.current_tire)),
            'tire_grip': self.current_gomma.percentuale_vita if self.current_gomma else None,
            'tire_age_laps': self.tire_age,
            'stint_laps_remaining': self.stint_laps_remaining,
            'stint_target_laps': self.stint_target_laps,
            'sector_snapshot': self.current_lap_sectors.copy(),
            'circuit_id': circuit_id,
            'circuit_name': circuit_name,
            **model_debug,
        })

        try:
            from utils.lap_telemetry import log_lap_debug, is_lap_debug_enabled

            if is_lap_debug_enabled():
                log_lap_debug(bucket)
        except Exception:
            pass
        finally:
            self.current_lap_debug = None
