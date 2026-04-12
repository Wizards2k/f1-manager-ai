"""
Physics V4 - Full Car Setup Interface

Interfaccia completa per configurare l'auto con parametri reali:
- Assetto aero (ali, floor, sidepods)
- Sospensioni (molle, ARB, ride height)
- Power Unit (ICE maps, ERS deploy/harvest)
- Gomme (compound, pressioni, camber)
- Freni (bias, ducts)
- Carburante (fuel load per sessione)

Usage:
    from lap_simulator.physics_v4 import PhysicsV4Setup, TeamDriverLoader
    
    # Carica dati McLaren + Norris
    loader = TeamDriverLoader()
    mclaren = loader.get_team("mclaren")
    norris = loader.get_driver("Lando Norris")
    
    # Configura auto per qualifica Monza
    setup = PhysicsV4Setup(
        team_data=mclaren,
        driver_data=norris,
        circuit="it-1922_monza",
        session="qualifying"
    )
    
    # Assetto basso (Monza style)
    setup.set_aero(front_wing=14.0, rear_wing=12.0)
    setup.set_suspension(ARB_front=3.0, ARB_rear=5.0)
    setup.set_fuels(fuel_kg=20.0)  # Poco carburante per qualifica
    setup.set_tyres(compound="C5", pressure_front=2.3, pressure_rear=2.1)
    setup.set_ers_mode("quali_deploy")  # Massimo deploy
    
    # Simula
    result = setup.simulate_lap()
    print(f"Tempo: {result.lap_time_s:.3f}s")
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .team_driver_data import TeamData, DriverSkill, get_team_data, get_driver_data


@dataclass
class AeroSetup:
    """Configurazione aerodinamica completa."""
    front_wing: float = 20.0  # 1-50
    rear_wing: float = 22.0   # 1-50
    floor: float = 25.0       # 1-50
    sidepods: float = 20.0    # 1-50
    engine_cover: float = 20.0
    bwing: float = 20.0
    
    # Derived
    cla_total: float = field(default=3.2)
    cda_total: float = field(default=1.1)


@dataclass
class SuspensionSetup:
    """Configurazione sospensioni.
    
    I valori sono salvati come SLIDER (unità UI):
    - spring_front/rear: slider 1-50
    - arb_front/rear: slider 1-30
    - ride_height_front/rear: slider 1-30
    
    La conversione a valori fisici reali avviene in slider_to_real().
    """
    spring_front: float = 25.0  # slider 1-50
    spring_rear: float = 33.0   # slider 1-50
    arb_front: float = 11.0     # slider 1-30
    arb_rear: float = 18.0      # slider 1-30
    ride_height_front: float = 7.0   # slider 1-30
    ride_height_rear: float = 14.0   # slider 1-30
    camber_front: float = -3.5      # degrees
    camber_rear: float = -1.5       # degrees
    toe_front: float = 0.1          # degrees
    toe_rear: float = 0.2           # degrees


@dataclass
class PowerUnitSetup:
    """Configurazione Power Unit e ERS."""
    ice_mode: str = "balanced"  # balanced, aggressive, conservative
    ers_deploy_mode: str = "balanced"  # balanced, quali_deploy, race_save
    ers_harvest_mode: str = "balanced"  # balanced, max_harvest, min_harvest
    brake_migration: float = 0.5  # 0-1 (0=front, 1=rear)
    
    # Energy management
    soc_target_start: float = 100.0  # %
    soc_target_end: float = 0.0      # %
    deploy_per_km: float = 0.67      # MJ/km (4 MJ / 6 km)


@dataclass
class TyreSetup:
    """Configurazione gomme."""
    compound: str = "C3"  # C1-C6, INTERMEDIATE, WET
    pressure_front: float = 2.3  # bar
    pressure_rear: float = 2.1   # bar
    camber_front: float = -3.5   # degrees (duplicate from suspension)
    camber_rear: float = -1.5    # degrees
    toe_front: float = 0.1       # degrees
    toe_rear: float = 0.2        # degrees


@dataclass
class BrakeSetup:
    """Configurazione freni."""
    bias_front: float = 57.0  # % (54-60)
    duct_front: int = 3       # 1-5 (1=closed, 5=wide open)
    duct_rear: int = 2        # 1-5
    brake_migration: float = 0.5  # 0-1


@dataclass
class FuelSetup:
    """Configurazione carburante."""
    fuel_kg: float = 100.0    # kg carburante iniziale
    fuel_mix: str = "lean"    # lean, balanced, rich
    
    @property
    def fuel_laps(self) -> float:
        """Stima giri possibili con questo fuel."""
        # Consumo medio: ~2.5 kg/giro
        return self.fuel_kg / 2.5


@dataclass
class CarSetup:
    """Configurazione completa dell'auto."""
    # Identificazione
    team: Optional[TeamData] = None
    driver: Optional[DriverSkill] = None
    circuit: str = ""
    session: str = "qualifying"  # qualifying, race, practice
    
    # Setup
    aero: AeroSetup = field(default_factory=AeroSetup)
    suspension: SuspensionSetup = field(default_factory=SuspensionSetup)
    power_unit: PowerUnitSetup = field(default_factory=PowerUnitSetup)
    tyres: TyreSetup = field(default_factory=TyreSetup)
    brakes: BrakeSetup = field(default_factory=BrakeSetup)
    fuel: FuelSetup = field(default_factory=FuelSetup)
    
    # Massa
    mass_total_kg: float = 883.0  # minimo regolamentare + driver
    
    def update_mass(self):
        """Aggiorna massa totale in base a fuel e setup."""
        # base_mass = 798 (auto) + 80 (driver) + 5 (carburante minimo) = 883 kg
        # Qualsiasi carburante oltre i 5 kg minimi si aggiunge linearmente.
        # Correzione V4.11: soglia era 20.0 (sbagliata), ora corretta a 5.0.
        base_mass = 883.0  # include già 5 kg carburante minimo
        fuel_over_min = max(0.0, self.fuel.fuel_kg - 5.0)
        self.mass_total_kg = base_mass + fuel_over_min


# ─────────────────────────────────────────────────────────────────────────────
# P4: CONVERSIONI SLIDER → VALORI REALI F1
# ─────────────────────────────────────────────────────────────────────────────
# Il motore fisico lavora con unità reali (N/mm, Nm/deg, mm, gradi).
# L'interfaccia UI usa slider user-friendly (1-50 per molle, 1-30 per ARB/RH).
# Queste funzioni centralizzano la conversione.
#
# Valori ottimali F1 (riferimento):
# - Spring Front: ~400 N/mm (slider ≈ 25)
# - Spring Rear:  ~ 556 N/mm (slider ≈ 38)
# - ARB Front:    ~ 200 Nm/deg (slider ≈ 11)
# - ARB Rear:     ~ 305 Nm/deg (slider ≈ 18)
# - Ride Height Front: ~ 26 mm (slider ≈ 7)
# - Ride Height Rear:  ~ 46 mm (slider ≈ 14)
# ─────────────────────────────────────────────────────────────────────────────

def slider_to_real(param: str, slider_value: float) -> float:
    """Converte un valore slider nel corrispondente valore fisico reale.
    
    Args:
        param: nome parametro ('spring_front', 'spring_rear', 'arb_front',
               'arb_rear', 'ride_height_front', 'ride_height_rear',
               'front_wing', 'rear_wing', 'bwing')
        slider_value: valore slider
    
    Returns:
        Valore in unità fisiche reali
    """
    conversions = {
        # Spring: slider 1-50 → N/mm (range F1: 112-700 N/mm front, 114-800 N/mm rear)
        'spring_front':     lambda v: v * 12.0 + 100.0,   # 112-700 N/mm
        'spring_rear':      lambda v: v * 14.0 + 100.0,   # 114-800 N/mm
        # ARB: slider 1-30 → Nm/deg (range F1: 50-485 Nm/deg)
        'arb_front':        lambda v: v * 15.0 + 35.0,    # 50-485 Nm/deg
        'arb_rear':         lambda v: v * 15.0 + 35.0,    # 50-485 Nm/deg
        # Ride Height: slider 1-30 → mm (range F1: 20-49 mm front, 30-65 mm rear)
        'ride_height_front': lambda v: v * 1.0 + 19.0,   # 20-49 mm
        'ride_height_rear':  lambda v: v * 1.2 + 28.8,    # 30-65 mm
        # Wing angles: slider = gradi (nessuna conversione)
        'front_wing':       lambda v: v,                  # 0-45°
        'rear_wing':        lambda v: v,                  # 0-45°
        'bwing':            lambda v: v,                  # 0-20°
    }
    if param not in conversions:
        raise ValueError(f"Parametro sconosciuto: {param}. Validi: {list(conversions.keys())}")
    return conversions[param](slider_value)


def real_to_slider(param: str, real_value: float) -> float:
    """Converte un valore fisico reale nel corrispondente valore slider.
    
    Inverso di slider_to_real(). Utile per l'UI.
    """
    inversions = {
        'spring_front':      lambda v: (v - 100.0) / 12.0,
        'spring_rear':       lambda v: (v - 100.0) / 14.0,
        'arb_front':         lambda v: (v - 35.0) / 15.0,
        'arb_rear':          lambda v: (v - 35.0) / 15.0,
        'ride_height_front': lambda v: (v - 19.0) / 1.0,
        'ride_height_rear':  lambda v: (v - 28.8) / 1.2,
        'front_wing':        lambda v: v,
        'rear_wing':         lambda v: v,
        'bwing':             lambda v: v,
    }
    if param not in inversions:
        raise ValueError(f"Parametro sconosciuto: {param}")
    return inversions[param](real_value)


class PhysicsV4Setup:
    """
    Builder e interfaccia per configurazioni auto realistiche.
    
    Usage:
        setup = PhysicsV4Setup(
            team_data=mclaren,
            driver_data=norris,
            circuit="it-1922_monza",
            session="qualifying"
        )
        
        setup.set_aero(front_wing=14.0, rear_wing=12.0)
        setup.set_suspension(ARB_front=3.0, ARB_rear=5.0)
        setup.set_fuels(fuel_kg=20.0)
        setup.set_tyres(compound="C5")
        setup.set_ers_mode("quali_deploy")
        
        result = setup.simulate_lap()
    """
    
    def __init__(
        self,
        team_data: Optional[TeamData] = None,
        driver_data: Optional[DriverSkill] = None,
        circuit: str = "",
        session: str = "qualifying"
    ):
        """
        Inizializza setup auto.
        
        Args:
            team_data: Dati team (da TeamDriverLoader)
            driver_data: Dati driver (da TeamDriverLoader)
            circuit: ID circuito (es. "it-1922_monza")
            session: Tipo sessione (qualifying, race, practice)
        """
        self.team = team_data
        self.driver = driver_data
        self.circuit = circuit
        self.session = session
        
        # Setup iniziale
        self.car = CarSetup(
            team=team_data,
            driver=driver_data,
            circuit=circuit,
            session=session
        )
        
        # Configura automaticamente in base alla sessione
        self._configure_for_session()
    
    def _configure_for_session(self):
        """Configurazione automatica in base al tipo di sessione."""
        if self.session == "qualifying":
            # Qualifica: massimo performance, poco fuel
            self.car.fuel.fuel_kg = 20.0  # Solo per 1-2 giri
            self.car.fuel.fuel_mix = "rich"
            self.car.power_unit.ers_deploy_mode = "quali_deploy"
            self.car.power_unit.ice_mode = "aggressive"
            self.car.update_mass()
            
        elif self.session == "race":
            # Gara: fuel completo, gestione ERS
            self.car.fuel.fuel_kg = 100.0  # ~100 kg per race start
            self.car.fuel.fuel_mix = "balanced"
            self.car.power_unit.ers_deploy_mode = "balanced"
            self.car.power_unit.ice_mode = "balanced"
            self.car.update_mass()
            
        elif self.session == "practice":
            # Prove: fuel medio, test setup
            self.car.fuel.fuel_kg = 50.0
            self.car.fuel.fuel_mix = "balanced"
            self.car.power_unit.ers_deploy_mode = "balanced"
    
    def set_aero(
        self,
        front_wing: Optional[float] = None,
        rear_wing: Optional[float] = None,
        floor: Optional[float] = None,
        sidepods: Optional[float] = None
    ):
        """Imposta assetto aerodinamico."""
        if front_wing is not None:
            self.car.aero.front_wing = front_wing
        if rear_wing is not None:
            self.car.aero.rear_wing = rear_wing
        if floor is not None:
            self.car.aero.floor = floor
        if sidepods is not None:
            self.car.aero.sidepods = sidepods
        
        # Calcola CLA/CDA totali.
        # FIX V4.13: Wing L/D corretto da 2.57 a 4.36 (reale F1 ≈ 4.0-5.0).
        # Le ali generavano troppo drag per unità di downforce, rendendo
        # gli assetti ad alta deportanza sempre svantaggiosi (anche su Monaco).
        # I coefficienti sono ancorati a FW=10+RW=12 (sum=22°) per preservare
        # la calibrazione Monza: CLA=2.846, CDA=0.874 invariati a quel punto.
        wing_sum_frac = (self.car.aero.front_wing + self.car.aero.rear_wing) / 100.0

        base_cla = 2.076       # floor + corpo
        k_cla    = 3.5         # CLA per grado/100 dalle ali — Wing L/D = 10.0
        self.car.aero.cla_total = base_cla + wing_sum_frac * k_cla

        base_cda = 0.797       # drag corpo base
        k_cda    = 0.35        # CDA per grado/100 dalle ali
        self.car.aero.cda_total = base_cda + wing_sum_frac * k_cda
        
        # Applica team aero modifiers
        if self.team:
            aero = self.team.aero
            self.car.aero.cla_total *= aero.front_wing_df_modifier
            self.car.aero.cla_total *= aero.rear_wing_df_modifier
            self.car.aero.cda_total *= aero.front_wing_drag_modifier
            self.car.aero.cda_total *= aero.rear_wing_drag_modifier
    
    def set_suspension(
        self,
        spring_front: Optional[float] = None,
        spring_rear: Optional[float] = None,
        ARB_front: Optional[float] = None,
        ARB_rear: Optional[float] = None,
        ride_height_front: Optional[float] = None,
        ride_height_rear: Optional[float] = None
    ):
        """Imposta configurazione sospensioni con valori SLIDER.
        
        P4 FIX: I valori sono salvati come slider (1-50 per molle, 1-30 per ARB/RH).
        La conversione a valori fisici reali avviene in slider_to_real() e viene
        applicata nel motore fisico (_compute_suspension_effects, compute_forces).
        
        Prima (BUG): set_suspension() scalava i valori (spring 15→150 N/m)
        ma _compute_suspension_effects() si aspettava slider (opt=15), causando
        penalità del 900% per il setup ottimale.
        
        Ora: i valori rimangono come slider. La conversione è centralizzata.
        """
        if spring_front is not None:
            self.car.suspension.spring_front = spring_front
        if spring_rear is not None:
            self.car.suspension.spring_rear = spring_rear
        if ARB_front is not None:
            self.car.suspension.arb_front = ARB_front
        if ARB_rear is not None:
            self.car.suspension.arb_rear = ARB_rear
        if ride_height_front is not None:
            self.car.suspension.ride_height_front = ride_height_front
        if ride_height_rear is not None:
            self.car.suspension.ride_height_rear = ride_height_rear
    
    def set_fuels(self, fuel_kg: float, fuel_mix: str = "balanced"):
        """Imposta carico carburante."""
        self.car.fuel.fuel_kg = fuel_kg
        self.car.fuel.fuel_mix = fuel_mix
        self.car.update_mass()
    
    def set_tyres(
        self,
        compound: str = "C3",
        pressure_front: Optional[float] = None,
        pressure_rear: Optional[float] = None
    ):
        """Imposta configurazione gomme."""
        self.car.tyres.compound = compound
        if pressure_front is not None:
            self.car.tyres.pressure_front = pressure_front
        if pressure_rear is not None:
            self.car.tyres.pressure_rear = pressure_rear
    
    def set_ers_mode(self, mode: str):
        """
        Imposta modalità ERS.
        
        Modes:
        - quali_deploy: massimo deploy (120kW) per tutto il giro
        - balanced: deploy bilanciato (60-80kW)
        - race_save: risparmio ERS per gara lunga
        """
        self.car.power_unit.ers_deploy_mode = mode
        
        if mode == "quali_deploy":
            self.car.power_unit.deploy_per_km = 0.67  # 4 MJ / 6 km
        elif mode == "balanced":
            self.car.power_unit.deploy_per_km = 0.50
        elif mode == "race_save":
            self.car.power_unit.deploy_per_km = 0.33
    
    def set_brakes(
        self,
        bias_front: float = 57.0,
        duct_front: int = 3,
        duct_rear: int = 2
    ):
        """Imposta configurazione freni."""
        self.car.brakes.bias_front = bias_front
        self.car.brakes.duct_front = duct_front
        self.car.brakes.duct_rear = duct_rear
    
    def apply_driver_preferences(self):
        """Applica preferenze del driver (offsets)."""
        setup = self.get_setup_dict()
        if not self.driver:
            return setup
        
        # Applica offsets alle ali
        setup["aero"]["front_wing"] += self.driver.front_wing_offset
        setup["aero"]["rear_wing"] += self.driver.rear_wing_offset
        
        # Ricalcola CLA/CDA con ali aggiornate (stessi coeff. di set_aero)
        wing_sum_frac = (setup["aero"]["front_wing"] + setup["aero"]["rear_wing"]) / 100.0
        setup["aero"]["cla_total"] = 2.076 + wing_sum_frac * 3.5
        setup["aero"]["cda_total"] = 0.797 + wing_sum_frac * 0.35

        if self.team:
            aero = self.team.aero
            setup["aero"]["cla_total"] *= aero.front_wing_df_modifier
            setup["aero"]["cla_total"] *= aero.rear_wing_df_modifier
            setup["aero"]["cda_total"] *= aero.front_wing_drag_modifier
            setup["aero"]["cda_total"] *= aero.rear_wing_drag_modifier

        return setup
    
    def get_setup_dict(self) -> Dict[str, Any]:
        """Restituisce setup come dizionario per V4 integrator."""
        return {
            "team": self.team.team_id if self.team else "generic",
            "driver": self.driver.name if self.driver else "Unknown",
            "aero": {
                "front_wing": self.car.aero.front_wing,
                "rear_wing": self.car.aero.rear_wing,
                "cla_total": self.car.aero.cla_total,
                "cda_total": self.car.aero.cda_total,
            },
            "suspension": {
                # Valori slider (1-30 per molle, 1-10 per ARB/ride height)
                "spring_front": self.car.suspension.spring_front,
                "spring_rear": self.car.suspension.spring_rear,
                "arb_front": self.car.suspension.arb_front,
                "arb_rear": self.car.suspension.arb_rear,
                "ride_height_front": self.car.suspension.ride_height_front,
                "ride_height_rear": self.car.suspension.ride_height_rear,
                # Valori fisici reali (convertiti con slider_to_real)
                "spring_front_Nmm": slider_to_real('spring_front', self.car.suspension.spring_front),
                "spring_rear_Nmm": slider_to_real('spring_rear', self.car.suspension.spring_rear),
                "arb_front_Nmdeg": slider_to_real('arb_front', self.car.suspension.arb_front),
                "arb_rear_Nmdeg": slider_to_real('arb_rear', self.car.suspension.arb_rear),
                "ride_height_front_mm": slider_to_real('ride_height_front', self.car.suspension.ride_height_front),
                "ride_height_rear_mm": slider_to_real('ride_height_rear', self.car.suspension.ride_height_rear),
                # Ride height in metri (per AeroAssembly.compute_forces)
                "ride_height_front_m": slider_to_real('ride_height_front', self.car.suspension.ride_height_front) / 1000.0,
                "ride_height_rear_m": slider_to_real('ride_height_rear', self.car.suspension.ride_height_rear) / 1000.0,
            },
            "tyres": {
                "compound": self.car.tyres.compound,
                "pressure_front": self.car.tyres.pressure_front,
                "pressure_rear": self.car.tyres.pressure_rear,
            },
            "mass_kg": self.car.mass_total_kg,
            "fuel_kg": self.car.fuel.fuel_kg,
            "ers_mode": self.car.power_unit.ers_deploy_mode,
        }
    
    def simulate_lap(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Simula un giro con questo setup.
        
        Returns:
            Dizionario con risultati:
            - lap_time_s: tempo giro
            - sector_times: [s1, s2, s3]
            - v_max_kph: velocità massima
            - v_min_kph: velocità minima
            - telemetry: punti telemetria
        """
        # Import qui per evitare circular imports
        from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd
        from lap_simulator.physics_v4.calibration.circuit_calibration import get_circuit_calibration
        from lap_simulator.physics_v4.calibration.aero_calibration import get_aero_calibration
        
        # Applica preferenze driver
        setup = self.apply_driver_preferences()
        base_setup = self.get_setup_dict()
        circuit_calibration = get_circuit_calibration(self.circuit)
        aero_calibration = get_aero_calibration(self.circuit)
        
        # Driver skill factor
        driver_skill = self.driver.quali_skill if self.driver else 1.0

        # ERS fraction: 0.0 = solo ICE (race_save), 1.0 = full ERS (quali_deploy)
        # Normalizzato su deploy_per_km massimo = 0.67 MJ/km (4 MJ / ~6 km)
        _ERS_DEPLOY_MAX = 0.67  # MJ/km
        ers_power_fraction = min(1.0, max(0.0,
            self.car.power_unit.deploy_per_km / _ERS_DEPLOY_MAX
        ))

        # Esegui simulazione
        result = integrate_lap_hd(
            circuit_id=self.circuit,
            aero_setup=setup["aero"],
            mass_kg=self.car.mass_total_kg,
            tyre_compound=self.car.tyres.compound,
            driver_skill=driver_skill,
            aero_calibration=aero_calibration,
            suspension_setup=setup.get("suspension"),
            ers_power_fraction=ers_power_fraction,
            verbose=verbose
        )
        
        # Aggiungi metadata
        result["team"] = self.team.name if self.team else "Unknown"
        result["driver"] = self.driver.name if self.driver else "Unknown"
        result["session"] = self.session
        result["setup_base"] = base_setup
        result["setup"] = setup
        result["circuit_calibration"] = circuit_calibration
        result["aero_calibration"] = aero_calibration

        return result
