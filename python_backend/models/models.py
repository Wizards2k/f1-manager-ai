# Models F1 Manager AI - Solo classi, senza logica di posizione
import time
import random
import math
from enum import Enum, auto
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    import config
except ImportError:  # pragma: no cover - fallback per contesti standalone
    config = None

from debug_log import log_debug_event

if TYPE_CHECKING:  # pragma: no cover
    from models.tyre_inventory import TyreSet

print("MODELS: Caricate classi base (senza logica posizione)")


class CarState(Enum):
    """Stati possibili per le auto durante la sessione."""
    BOX = "BOX"
    OUT_LAP = "OUT LAP"
    HOT_LAP = "HOT LAP"
    IN_LAP = "IN LAP"


class CarPhase(str, Enum):
    """Where the car is in the session lifecycle."""
    IN_GARAGE = "in_garage"
    PIT_QUEUE = "pit_queue"
    PIT_EXIT = "pit_exit"
    ON_TRACK = "on_track"
    PIT_ENTRY = "pit_entry"
    PIT_WORK = "pit_work"


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
    ARGENTINA = "ARG"
    NUOVA_ZELANDA = "NZL"


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
        "Andrea Kimi Antonelli": "ANT",
        "Oliver Bearman": "BEA",
        "Gabriel Bortoleto": "BOR",
        "Franco Colapinto": "COL",
        "Isack Hadjar": "HAD",
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
        perfezionismo: int = 50,
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
        self._perfezionismo = 50

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
        self.perfezionismo = perfezionismo

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

    @property
    def perfezionismo(self) -> int:
        return self._perfezionismo

    @perfezionismo.setter
    def perfezionismo(self, value: int):
        self._perfezionismo = MathUtils.clamp(value, 1, 100)


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
        power_unit=None,
        auto=None,
        pilota1: Optional[Pilota] = None,
        pilota2: Optional[Pilota] = None,
        pilota_riserva: Optional[Pilota] = None,
        sponsor_principale: str = "",
        simulator_quality: int = 70,
    ):
        self.nome_scuderia = nome_scuderia
        self.sigla_scuderia = sigla_scuderia
        self.nazionalita = nazionalita
        self.colore_team = colore_team
        self.power_unit = power_unit
        self.auto = auto
        self.pilota1 = pilota1
        self.pilota2 = pilota2
        self.pilota_riserva = pilota_riserva
        self.sponsor_principale = sponsor_principale

        self.simulator_quality = MathUtils.clamp(simulator_quality, 1, 100)


DEFAULT_SETUP_CONFIG = {
    'front_wing': 50,
    'rear_wing': 50,
    'beam_wing': 50,
    'ride_height_front': 50,
    'ride_height_rear': 50,
    'suspension_front': 50,
    'suspension_rear': 50,
    'antiroll_front': 50,
    'antiroll_rear': 50,
    'brake_balance': 50,
    'brake_duct': 50,
}

AI_SETUP_PROGRESS_TARGET = 120.0
AI_PROGRESS_GAIN_PER_RUN = 42.0
AI_PROGRESS_PENALTY_PER_SLIDER = 3.5
AI_PROGRESS_PENALTY_PER_DELTA = 0.3  # per absolute slider delta point
AI_PROGRESS_MAX_PENALTY = 40.0

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
        self.has_completed_hot_lap = False
        self.setup_info_points = 0.0
        self.setup_baseline: Optional[Dict[str, int]] = None
        self.setup_info_target = self._compute_setup_info_target()
        
        # Tempi e performance
        self.lap_times = []
        self.sector_times = []
        self.current_lap_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.last_sector_times = {'sector1': None, 'sector2': None, 'sector3': None}
        self.best_sectors = {'sector1': None, 'sector2': None, 'sector3': None}
        self.current_lap_debug: Optional[Dict[str, Any]] = None
        # Telemetry/diagnostics exposed to frontend & tools
        self.pu_stats: Dict[str, Any] = {}
        self.brake_diagnostics: Dict[str, Any] = {}
        
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
        self.tire_temp_window = self.get_tire_temp_window(initial_compound)
        self.tire_temps = {
            'fl': sum(self.tire_temp_window) / 2,
            'fr': sum(self.tire_temp_window) / 2,
            'rl': sum(self.tire_temp_window) / 2,
            'rr': sum(self.tire_temp_window) / 2,
        }
        self.current_tyre_condition_pct: float = 100.0
        self.current_tyre_heat_cycles: int = 0
        self.current_tyre_laps_completed: int = 0
        self.current_tyre_laps_at_install: int = 0
        self.current_tyre_set: Optional['TyreSet'] = None
        self.tyre_states: Dict[str, Dict[str, Any]] = {}

        # Player control & configurazioni
        self.is_player_controlled = False
        self.max_fuel_laps_at_100 = 12
        self.fuel_percent = 100
        self.pace_level = 5
        self.ice_mode = "PRACTICE"
        self.ers_mode = "STANDARD"
        self.player_config: Dict[str, Any] = {
            "tyre_compound": self.current_tire.value,
            "fuel_percent": self.fuel_percent,
            "pace_level": self.pace_level,
            "ice_mode": self.ice_mode,
            "ers_mode": self.ers_mode,
            "stint_target_laps": self.stint_target_laps,
            "setup": {**DEFAULT_SETUP_CONFIG},
        }
        self.setup_feedback: Optional[Dict[str, Any]] = {
            'message': 'Baseline setup ready.',
            'tone': 'info',
            'fields': {key: {
                'status': 'missing',
                'delta_label': 'Awaiting evaluation',
                'range': None,
            } for key in DEFAULT_SETUP_CONFIG.keys()},
            'categories': None,  # Populated by evaluate_setup_categories
        }
        # Driver live feedback state
        self.last_driver_feedback: Optional[str] = None
        self.driver_feedback_timestamp: float = 0.0
        self.driver_feedback_cooldown: float = 5.0  # Seconds between messages
        self.feedback_count_this_lap: int = 0
        self.feedback_zones_used_this_lap: set = set()
        self.current_lap_for_feedback: int = 0

    def set_tire_compound(
        self,
        compound,
        percentuale_vita: float = 1.0,
        *,
        laps_completed: int = 0,
        preserve_temps: bool = False,
    ):
        """Imposta il compound di gomme"""
        previous_temps = dict(self.tire_temps) if preserve_temps and isinstance(getattr(self, 'tire_temps', None), dict) else None
        self.current_tire = compound
        self.current_gomma = Gomma(compound, percentuale_vita=percentuale_vita)
        self.tire_age = max(0, int(laps_completed or 0))
        self.tire_wear = max(0.0, min(1.0, 1.0 - float(percentuale_vita)))
        self.current_tyre_condition_pct = max(0.0, min(100.0, float(percentuale_vita) * 100.0))
        self.current_tyre_laps_completed = max(0, int(laps_completed or 0))
        self.tire_temp_window = self.get_tire_temp_window(compound)
        if previous_temps is not None:
            self.tire_temps = previous_temps
        else:
            target_temp = sum(self.tire_temp_window) / 2
            self.tire_temps = {
                'fl': target_temp,
                'fr': target_temp,
                'rl': target_temp,
                'rr': target_temp,
            }
        self.player_config["tyre_compound"] = self.current_tire.value

    def get_tire_temp_window(self, compound: TireCompound) -> tuple[float, float]:
        windows = {
            TireCompound.SOFT: (92.0, 105.0),
            TireCompound.MEDIUM: (88.0, 101.0),
            TireCompound.HARD: (84.0, 97.0),
            TireCompound.INTERMEDIATE: (72.0, 86.0),
            TireCompound.WET: (65.0, 80.0),
        }
        return windows.get(compound, (85.0, 100.0))

    def update_tire_temps(self, dt: float):
        min_temp, max_temp = self.tire_temp_window
        target = (min_temp + max_temp) / 2
        if self.state == CarState.HOT_LAP:
            target += 4 + (self.tire_wear * 12)
        elif self.state == CarState.OUT_LAP:
            target -= 6
        elif self.state == CarState.IN_LAP:
            target -= 8
        else:
            target = min_temp - 5

        smoothing = min(1.0, dt * 1.2)
        for key in self.tire_temps.keys():
            current = self.tire_temps[key]
            self.tire_temps[key] = current + (target - current) * smoothing

    def update_tire_wear(self):
        """Aggiorna l'usura delle gomme con factor pace_level."""
        if self.state == CarState.HOT_LAP:
            self.tire_age += 1
            # Pace factor: 1-10 scale -> 0.5 to 1.5 multiplier
            # pace_level 5 = neutral (1.0), 1 = conservative (0.6), 10 = aggressive (1.4)
            pace_factor = 0.6 + (self.pace_level - 1) * 0.088  # 0.6 to ~1.4
            
            if self.current_tire in (TireCompound.SOFT, TireCompound.MEDIUM, TireCompound.HARD):
                # Apply pace factor to base degradation
                base_degradation = self.current_gomma.DEGRADO_BASE[self.current_tire]
                adjusted_degradation = base_degradation * pace_factor
                self.current_gomma.aggiorna_degrado(adjusted_degradation)
                self.tire_wear = 1.0 - self.current_gomma.percentuale_vita
                self.current_tyre_condition_pct = max(0.0, min(100.0, self.current_gomma.percentuale_vita * 100.0))
            else:
                # Mantieni logica semplice per intermedie/wet
                wear_increment = 0.04 if self.current_tire == TireCompound.INTERMEDIATE else 0.02
                wear_increment *= pace_factor
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
        self.has_completed_hot_lap = False
        
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
        if self.is_player_controlled and self.setup_feedback_ready:
            self._generate_setup_feedback(trigger='box_entry')

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
        if lap_type == CarState.HOT_LAP:
            self.has_completed_hot_lap = True
        if self.is_player_controlled:
            self._accumulate_setup_info(lap_type)
        if self.is_player_controlled:
            log_debug_event(
                'lap_complete',
                driver=self.driver_number,
                lap_type=lap_type.value if isinstance(lap_type, CarState) else str(lap_type),
                total_laps=self.total_laps,
                stint_laps_remaining=self.stint_laps_remaining,
                state=str(self.state),
            )
        
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

    @staticmethod
    def _resolve_game_compound(compound_label: Optional[str]) -> TireCompound:
        if not compound_label:
            return TireCompound.MEDIUM
        label = str(compound_label).strip().upper()
        try:
            return TireCompound[label]
        except KeyError:
            return TireCompound.MEDIUM

    def apply_tyre_set(
        self,
        tyre_set: 'TyreSet',
        *,
        compound: Optional[TireCompound] = None,
        preserve_temps: bool = False,
    ) -> None:
        """Attach a TyreSet object to this car and sync runtime telemetry."""

        if tyre_set is None:
            self.current_tyre_set = None
            return

        tyre_set.is_available = False
        self.current_tyre_set = tyre_set
        resolved_compound = compound or self._resolve_game_compound(tyre_set.compound)
        tyre_life = max(0.0, min(1.0, tyre_set.condition / 100.0))
        self.set_tire_compound(
            resolved_compound,
            percentuale_vita=tyre_life,
            laps_completed=tyre_set.laps_completed,
            preserve_temps=preserve_temps,
        )
        self.current_tyre_condition_pct = tyre_set.condition
        self.current_tyre_heat_cycles = tyre_set.heat_cycles
        self.current_tyre_laps_completed = tyre_set.laps_completed
        self.current_tyre_laps_at_install = tyre_set.laps_completed

        snapshot = tyre_set.get_runtime_snapshot()
        if snapshot:
            self.tyre_states = snapshot
            # Update tyre temps if snapshot contains richer data
            temps = {}
            for wheel, state in snapshot.items():
                temps[wheel] = state.get('surface_temp', self.tire_temps.get(wheel, sum(self.tire_temp_window) / 2))
            if temps:
                self.tire_temps.update(temps)

        if hasattr(self, 'player_config') and isinstance(self.player_config, dict):
            self.player_config['tyre_set_id'] = tyre_set.set_id
            self.player_config['tyre_compound'] = tyre_set.compound

    @property
    def setup_feedback_ready(self):
        return self.setup_info_points >= self.setup_info_target

    @property
    def setup_info_percent(self):
        if self.setup_info_target <= 0:
            return 100.0
        return min(100.0, (self.setup_info_points / self.setup_info_target) * 100.0)

    def update_ai_setup_snapshot(
        self,
        setup_snapshot: Optional[Dict[str, int]] = None,
        *,
        reset_progress: bool = False,
        force_complete: bool = False,
    ):
        """Sync AI setup data and optionally reset/complete progress."""
        if setup_snapshot:
            setup_store = self.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
            setup_store.update(setup_snapshot)
        if force_complete:
            # Consider setup fully learned
            self.setup_info_points = max(self.setup_info_target, 1.0)
            return
        if reset_progress:
            self.reset_setup_info()
            return

    def apply_ai_progress_result(
        self,
        slider_changes: Optional[Dict[str, float]] = None,
        *,
        setup_complete: bool = False,
        score_before: Optional[float] = None,
        score_after: Optional[float] = None,
        score_threshold: Optional[float] = None,
    ) -> None:
        """Update AI-only data chip metric after each setup run."""
        if self.is_player_controlled:
            return

        self.setup_info_target = AI_SETUP_PROGRESS_TARGET
        current = max(0.0, self.setup_info_points)
        percent_before = self.setup_info_percent

        derived_percent = None
        if score_after is not None and score_threshold:
            threshold = max(1e-3, score_threshold)
            derived_percent = MathUtils.clamp((score_after / threshold) * 100.0, 0.0, 100.0)

        if setup_complete:
            percent_after = 100.0
            outcome = 'complete'
        elif derived_percent is not None:
            percent_after = derived_percent
            outcome = 'score'
        else:
            # Fallback to legacy heuristic when no score info is available
            slider_changes = slider_changes or {}
            if slider_changes:
                change_count = len(slider_changes)
                delta_sum = sum(abs(delta) for delta in slider_changes.values())
                penalty = change_count * AI_PROGRESS_PENALTY_PER_SLIDER + delta_sum * AI_PROGRESS_PENALTY_PER_DELTA
                penalty = min(AI_PROGRESS_MAX_PENALTY, penalty)
                percent_after = max(0.0, percent_before - (penalty / self.setup_info_target * 100.0))
                outcome = 'penalty'
            else:
                gain = AI_PROGRESS_GAIN_PER_RUN
                percent_after = min(100.0, percent_before + (gain / self.setup_info_target * 100.0))
                outcome = 'gain'

        self.setup_info_points = (percent_after / 100.0) * self.setup_info_target
        delta_points = self.setup_info_points - current

        log_debug_event(
            'ai_chip_progress',
            driver=self.driver_number,
            outcome=outcome,
            slider_changes=slider_changes,
            setup_complete=setup_complete,
            score_before=score_before,
            score_after=score_after,
            score_threshold=score_threshold,
            points_before=round(current, 2),
            points_after=round(self.setup_info_points, 2),
            delta=round(delta_points, 2),
            percent_before=round(percent_before, 1),
            percent_after=round(self.setup_info_percent, 1),
            target=round(self.setup_info_target, 1),
        )

    def apply_ai_setup_progress(
        self,
        percent: float,
        setup_snapshot: Optional[Dict[str, int]] = None,
    ) -> None:
        """Legacy helper used by SessionBridge to map AI convergence to progress."""
        percent = max(0.0, min(100.0, percent))
        if setup_snapshot:
            setup_store = self.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
            setup_store.update(setup_snapshot)

        target = max(1.0, self.setup_info_target or 1.0)
        if percent <= 0.0:
            self.setup_info_points = 0.0
        elif percent >= 100.0:
            self.setup_info_points = target
        else:
            self.setup_info_points = (percent / 100.0) * target

    def _compute_setup_info_target(self):
        """Calcola la soglia di info necessarie.
        Dipende dal numero di slider modificati rispetto al baseline:
        - 1 slider cambiato → ~30 punti (1 giro con pilota bravo)
        - tutti 11 → ~150 punti (4-5 giri)
        Più un piccolo bonus per setup molto estremi."""
        current_setup = getattr(self, 'player_config', {}).get('setup', {})
        baseline = getattr(self, 'setup_baseline', None)
        if baseline is None:
            # Session start: no data collected yet, all fields need analysis
            changed = len(DEFAULT_SETUP_CONFIG)  # 11
            total_delta = 0
        else:
            # Count how many fields changed (threshold > 2 to ignore micro-adjustments)
            changed = 0
            total_delta = 0
            for key in DEFAULT_SETUP_CONFIG:
                cur = current_setup.get(key, 50)
                base = baseline.get(key, 50)
                diff = abs(cur - base)
                if diff > 2:
                    changed += 1
                    total_delta += diff
        # Base: 30 points per changed field, minimum 30 (at least 1 field worth)
        fields_target = max(30.0, changed * 30.0)
        # Small bonus for extreme total delta (all sliders moved a lot)
        extreme_bonus = min(30.0, total_delta * 0.15) if total_delta > 50 else 0
        return fields_target + extreme_bonus

    def _compute_setup_info_gain(self):
        """Calcola quanti info_points vengono raccolti in un hot lap.
        Dipende dalla skill ricerca_assetto del pilota."""
        base_gain = 35.0
        # Skill bonus: ricerca_assetto 1-100 → multiplier 0.6x to 1.4x
        skill = getattr(self.pilot, 'ricerca_assetto', 50)
        skill_mult = 0.6 + (skill / 100.0) * 0.8  # 1→0.608, 50→1.0, 100→1.4
        return base_gain * skill_mult

    def _accumulate_setup_info(self, lap_type):
        """Accumula info_points solo durante HOT LAP."""
        if lap_type != CarState.HOT_LAP:
            return
        gain = self._compute_setup_info_gain()
        self.setup_info_points = min(self.setup_info_points + gain, self.setup_info_target * 1.5)
        if self.is_player_controlled:
            log_debug_event(
                'setup_info_accumulated',
                driver=self.driver_number,
                lap_type=lap_type.value if isinstance(lap_type, CarState) else str(lap_type),
                gain=round(gain, 1),
                total=round(self.setup_info_points, 1),
                target=round(self.setup_info_target, 1),
                percent=round(self.setup_info_percent, 1),
                ready=self.setup_feedback_ready,
            )

    def reset_setup_info(self):
        """Azzera i punti info e ricalcola il target. Chiamato su Apply/save setup."""
        self.setup_info_points = 0.0
        self.setup_info_target = self._compute_setup_info_target()
        # Snapshot current setup as new baseline for next change detection
        self.setup_baseline = dict(self.player_config.get('setup', {**DEFAULT_SETUP_CONFIG}))
        self.setup_feedback = None
        self.has_completed_hot_lap = False

    def _generate_setup_feedback(self, trigger='manual'):
        """Calcola e salva il feedback setup corrente"""
        if not self.is_player_controlled:
            return
        current_setup = self.player_config.setdefault('setup', {**DEFAULT_SETUP_CONFIG})
        try:
            from utils.setup_engine import evaluate_setup, evaluate_setup_categories
        except Exception:  # pragma: no cover
            log_debug_event(
                'setup_feedback_error',
                driver=self.driver_number,
                trigger=trigger,
                reason='import_error',
            )
            return

        try:
            recommendation = evaluate_setup(current_setup)
            categories = evaluate_setup_categories(current_setup)
        except Exception as exc:  # pragma: no cover
            log_debug_event(
                'setup_feedback_error',
                driver=self.driver_number,
                trigger=trigger,
                reason=str(exc),
            )
            return

        recommendation['categories'] = categories
        self.setup_feedback = recommendation
        log_debug_event(
            'setup_feedback_generated',
            driver=self.driver_number,
            trigger=trigger,
            has_completed_hot_lap=self.has_completed_hot_lap,
            total_laps=self.total_laps,
        )

    def compute_max_stint_laps(self, fuel_percent: int) -> int:
        """Calcola il numero massimo di giri consentiti dal fuel percentuale."""
        fuel_percent = MathUtils.clamp(fuel_percent, 1, 100)
        estimated = math.floor((fuel_percent / 100.0) * self.max_fuel_laps_at_100)
        return max(1, estimated)

    def consume_fuel(self, lap_type: CarState):
        if not self.is_player_controlled:
            return
        base_burn = 100.0 / max(1, self.max_fuel_laps_at_100)
        
        # Lap type factor
        if lap_type == CarState.HOT_LAP:
            lap_factor = 1.0
        elif lap_type == CarState.OUT_LAP or lap_type == CarState.IN_LAP:
            lap_factor = 0.8
        else:
            lap_factor = 0.5
        
        # Pace factor: 1-10 scale -> 0.8 to 1.25 multiplier
        # pace_level 5 = neutral (1.0), 1 = efficient (0.8), 10 = thirsty (1.25)
        pace_factor = 0.8 + (self.pace_level - 1) * 0.05  # 0.8 to 1.25
        
        total_burn = base_burn * lap_factor * pace_factor
        self.fuel_percent = max(1.0, self.fuel_percent - total_burn)
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
