# Models F1 Manager AI - Solo classi, senza logica di posizione
import time
import random
from enum import Enum

print("MODELS: Caricate classi base (senza logica posizione)")

class CarState(Enum):
    """Stati possibili per le auto durante le prove libere"""
    BOX = "BOX"
    OUT_LAP = "OUT LAP"
    HOT_LAP = "HOT LAP"
    IN_LAP = "IN LAP"

class RaceCar:
    def __init__(self, driver_number, driver_name, team_name, team_color):
        self.driver_number = driver_number
        self.driver_name = driver_name
        self.team_name = team_name
        self.team_color = team_color
        
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
        
        # Gestione stint
        self.stint_target_laps = random.randint(8, 15)
        self.stint_laps_remaining = self.stint_target_laps
        self.box_time_until = 0
        self.session_start_time = None
        self.sector3_start_time = None
        
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
        
    def enter_box(self):
        """Auto rientra ai box"""
        self.state = CarState.BOX
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
        
        # Aggiorna miglior tempo in sessione
        if not hasattr(self, 'best_lap_time') or realistic_lap_time < self.best_lap_time:
            self.best_lap_time = realistic_lap_time
            # Snapshot dei settori del best lap (stesso giro) per delta coerenti
            self.best_lap_sectors = {
                'sector1': self.current_lap_sectors.get('sector1'),
                'sector2': self.current_lap_sectors.get('sector2'),
                'sector3': self.current_lap_sectors.get('sector3')
            }
