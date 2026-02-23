from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Componenti aero e meccaniche
# ---------------------------------------------------------------------------

@dataclass
class AeroSurface:
    surface_id: str
    nome: str  # nome tecnico componente
    df_coeff: float  # coefficiente downforce base
    drag_coeff: float  # coefficiente drag base
    peso_kg: float
    posizione: str  # "anteriore" | "posteriore"
    angolo_inclinazione: Optional[float] = None  # 1-100 per ali / b-wing


@dataclass
class AeroPackage:
    package_id: str
    nome: str
    ala_anteriore: AeroSurface
    ala_posteriore: AeroSurface
    sidepods: Optional[AeroSurface] = None
    fondo_anteriore: Optional[AeroSurface] = None
    fondo_posteriore: Optional[AeroSurface] = None
    cofano_motore: Optional[AeroSurface] = None
    b_wing: Optional[AeroSurface] = None
    notes: Optional[str] = None


@dataclass
class Suspension:
    suspension_id: str
    nome: str
    stiffness_front: float
    stiffness_rear: float
    antiroll_front: float
    antiroll_rear: float


@dataclass
class RideHeight:
    ride_height_id: str
    nome: str
    front_mm: float
    rear_mm: float


# ---------------------------------------------------------------------------
# Auto wrapper
# ---------------------------------------------------------------------------

@dataclass
class Auto:
    auto_id: str
    nome: str
    anno: int
    spec_version: str
    aero_package: AeroPackage
    suspension: Suspension
    ride_height: RideHeight
    mech_grip_id: str
    grip_base: float
    notes: Optional[str] = None

    def base_setup(self) -> dict:
        """Restituisce un setup base descrittivo (non integrato nel simulatore esistente)."""
        return {
            "ride_height": {
                "front_mm": self.ride_height.front_mm,
                "rear_mm": self.ride_height.rear_mm,
            },
            "suspension": {
                "stiffness_front": self.suspension.stiffness_front,
                "stiffness_rear": self.suspension.stiffness_rear,
                "antiroll_front": self.suspension.antiroll_front,
                "antiroll_rear": self.suspension.antiroll_rear,
            },
            "mechanical_grip": {
                "mech_grip_id": self.mech_grip_id,
                "grip_base": self.grip_base,
            },
            "aero_package": {
                "package_id": self.aero_package.package_id,
                "nome": self.aero_package.nome,
                "ala_anteriore": self.aero_package.ala_anteriore.surface_id,
                "ala_posteriore": self.aero_package.ala_posteriore.surface_id,
                "sidepods": self.aero_package.sidepods.surface_id if self.aero_package.sidepods else None,
                "fondo_anteriore": self.aero_package.fondo_anteriore.surface_id if self.aero_package.fondo_anteriore else None,
                "fondo_posteriore": self.aero_package.fondo_posteriore.surface_id if self.aero_package.fondo_posteriore else None,
                "cofano_motore": self.aero_package.cofano_motore.surface_id if self.aero_package.cofano_motore else None,
                "b_wing": self.aero_package.b_wing.surface_id if self.aero_package.b_wing else None,
            },
        }
