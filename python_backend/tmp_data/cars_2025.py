"""
Car data registry for 2025 season
Generated from race performance gaps (first 3 GPs)
NOT CONNECTED TO GAME - sandbox data only
"""

from dataclasses import dataclass
from typing import Dict, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.auto_models import Auto, AeroPackage, Suspension, RideHeight, AeroSurface


FRONT_SHARE_BY_TEAM = {
    "McLaren": 0.36,
    "Red Bull": 0.35,
    "Ferrari": 0.34,
    "Mercedes": 0.33,
    "Aston Martin": 0.33,
    "Alpine": 0.32,
    "Haas": 0.31,
    "Williams": 0.31,
    "Sauber": 0.30,
    "RB": 0.30,
}

FRONT_FLOOR_SHARE = 0.55  # % del totale anteriore allocato al floor

REAR_AUX_PROFILE = {
    "engine_cover": 0.5,
    "sidepods": 0.3,
    "beam_wing": 0.2,
}

DRAG_PROFILE = {
    "sidepods": 0.26,
    "rear_wing": 0.22,
    "engine_cover": 0.18,
    "front_wing": 0.14,
    "beam_wing": 0.10,
    "front_floor": 0.06,
    "rear_floor": 0.04,
}


def _clamp_score(value: float, lo: float = 60.0, hi: float = 98.0) -> float:
    return max(lo, min(hi, value))


def _component_scores(values: Dict[str, float], base_score: float, spread: float) -> Dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        return {key: base_score for key in values}

    avg_share = 1.0 / len(values)
    scores: Dict[str, float] = {}
    for key, val in values.items():
        share = val / total
        score = base_score + (share - avg_share) * spread
        scores[key] = _clamp_score(score)
    return scores


REAR_PAIR_RATIO = 0.60


def create_car_2025(team_name: str, aero_factor: float, grip_factor: float) -> Auto:
    """
    Create an Auto instance with scaled aero and grip.
    The downforce/drag model now computes each AeroSurface independently and derives the total DF from the sum of the parts.
    """
    # Baseline McLaren specs
    base_downforce_n = 8500  # Newtons at 300 km/h (sum of component loads)
    base_drag_coefficient = 0.85

    front_share_target = FRONT_SHARE_BY_TEAM.get(team_name, 0.32)
    front_share_target = max(0.30, min(0.40, front_share_target))

    front_floor_share = front_share_target * FRONT_FLOOR_SHARE
    front_wing_share = front_share_target - front_floor_share

    total_floor_share = front_floor_share / 0.40
    rear_floor_share = total_floor_share * REAR_PAIR_RATIO

    total_wing_share = front_wing_share / 0.40
    rear_wing_share = total_wing_share * REAR_PAIR_RATIO

    paired_sum = total_floor_share + total_wing_share
    remaining_share = max(1.0 - paired_sum, 0.0)

    component_weights = {
        "front_floor": front_floor_share,
        "rear_floor": rear_floor_share,
        "front_wing": front_wing_share,
        "rear_wing": rear_wing_share,
        "engine_cover": remaining_share * REAR_AUX_PROFILE["engine_cover"],
        "sidepods": remaining_share * REAR_AUX_PROFILE["sidepods"],
        "beam_wing": remaining_share * REAR_AUX_PROFILE["beam_wing"],
    }

    total_weight = sum(component_weights.values())
    if total_weight <= 0:
        total_weight = 1.0
    component_weights = {k: v / total_weight for k, v in component_weights.items()}

    component_drag_shares = DRAG_PROFILE.copy()

    # compute per-component DF & drag
    component_df_n = {
        key: (base_downforce_n * weight) / aero_factor
        for key, weight in component_weights.items()
    }
    component_drag = {
        key: base_drag_coefficient * share * aero_factor
        for key, share in component_drag_shares.items()
    }

    component_score_df = _component_scores(component_df_n, base_score=85.0, spread=42.0)
    component_score_drag = _component_scores(component_drag, base_score=75.0, spread=30.0)

    total_downforce_n = sum(component_df_n.values())

    aero_package = AeroPackage(
        package_id="base",
        nome=f"Aero-{team_name}-2025",
        ala_anteriore=AeroSurface(
            surface_id="fw",
            nome="Front Wing",
            df_coeff=component_df_n["front_wing"] / 1000,
            drag_coeff=component_drag["front_wing"],
            peso_kg=12.0,
            posizione="anteriore",
            angolo_inclinazione=15.0,
            component_score_df=component_score_df["front_wing"],
            component_score_drag=component_score_drag["front_wing"],
        ),
        ala_posteriore=AeroSurface(
            surface_id="rw",
            nome="Rear Wing",
            df_coeff=component_df_n["rear_wing"] / 1000,
            drag_coeff=component_drag["rear_wing"],
            peso_kg=14.0,
            posizione="posteriore",
            angolo_inclinazione=20.0,
            component_score_df=component_score_df["rear_wing"],
            component_score_drag=component_score_drag["rear_wing"],
        ),
        sidepods=AeroSurface(
            surface_id="sp",
            nome="Sidepods",
            df_coeff=component_df_n["sidepods"] / 1000,
            drag_coeff=component_drag["sidepods"],
            peso_kg=32.0,
            posizione="centrale",
            component_score_df=component_score_df["sidepods"],
            component_score_drag=component_score_drag["sidepods"],
        ),
        fondo_anteriore=AeroSurface(
            surface_id="ff",
            nome="Front Floor",
            df_coeff=component_df_n["front_floor"] / 1000,
            drag_coeff=component_drag["front_floor"],
            peso_kg=8.0,
            posizione="anteriore",
            component_score_df=component_score_df["front_floor"],
            component_score_drag=component_score_drag["front_floor"],
        ),
        fondo_posteriore=AeroSurface(
            surface_id="rf",
            nome="Rear Floor",
            df_coeff=component_df_n["rear_floor"] / 1000,
            drag_coeff=component_drag["rear_floor"],
            peso_kg=6.0,
            posizione="posteriore",
            component_score_df=component_score_df["rear_floor"],
            component_score_drag=component_score_drag["rear_floor"],
        ),
        cofano_motore=AeroSurface(
            surface_id="ec",
            nome="Engine Cover",
            df_coeff=component_df_n["engine_cover"] / 1000,
            drag_coeff=component_drag["engine_cover"],
            peso_kg=10.0,
            posizione="posteriore",
            component_score_df=component_score_df["engine_cover"],
            component_score_drag=component_score_drag["engine_cover"],
        ),
        beam_wing=AeroSurface(
            surface_id="bw",
            nome="Beam Wing",
            df_coeff=component_df_n["beam_wing"] / 1000,
            drag_coeff=component_drag["beam_wing"],
            peso_kg=7.0,
            posizione="posteriore",
            angolo_inclinazione=12.0,
            component_score_df=component_score_df["beam_wing"],
            component_score_drag=component_score_drag["beam_wing"],
        ),
        b_wing=None,
    )

    # Suspension setup
    suspension = Suspension(
        suspension_id="base",
        nome=f"Susp-{team_name}-2025",
        stiffness_front=120.0 / grip_factor,
        stiffness_rear=140.0 / grip_factor,
        antiroll_front=120.0 / grip_factor,
        antiroll_rear=140.0 / grip_factor
    )
    
    # Ride height setup
    ride_height = RideHeight(
        ride_height_id="base",
        nome=f"RH-{team_name}-2025",
        front_mm=85.0,
        rear_mm=95.0
    )
    
    # Grip coefficients (simplified placeholder)
    # Note: Grip model not yet defined in auto_models.py; using placeholder values
    grip = None  # Placeholder
    
    return Auto(
        auto_id=1,
        nome=f"Car-{team_name}-2025",
        anno=2025,
        spec_version="v1.0",
        aero_package=aero_package,
        suspension=suspension,
        ride_height=ride_height,
        mech_grip_id="base",
        grip_base=1.0 / grip_factor
    )


# Simple brake system class for completeness
@dataclass
class BremboBrakeSystem:
    brake_balance_front_pct: float
    max_brake_pressure_bar: float
    disc_thickness_mm: int
    caliper_type: str
    pad_compound: str
    cooling_efficiency: float


# Car registry based on 2025 performance gaps
CARS_2025: Dict[str, Auto] = {
    'MCL': create_car_2025('McLaren', 1.0000, 1.0000),  # Baseline
    'RBR': create_car_2025('Red Bull', 1.0032, 1.0028),  # +0.32% aero, +0.28% grip
    'FER': create_car_2025('Ferrari', 1.0048, 1.0042),   # +0.48% aero, +0.42% grip
    'MER': create_car_2025('Mercedes', 1.0072, 1.0063),  # +0.72% aero, +0.63% grip
    'AST': create_car_2025('Aston Martin', 1.0100, 1.0088),  # +1.0% aero, +0.88% grip
    'ALP': create_car_2025('Alpine', 1.0128, 1.0112),    # +1.28% aero, +1.12% grip
    'HAAS': create_car_2025('Haas', 1.0164, 1.0144),     # +1.64% aero, +1.44% grip
    'WIL': create_car_2025('Williams', 1.0192, 1.0168), # +1.92% aero, +1.68% grip
    'SAU': create_car_2025('Sauber', 1.0220, 1.0192),   # +2.2% aero, +1.92% grip
    'RBRB': create_car_2025('RB', 1.0272, 1.0238),      # +2.72% aero, +2.38% grip
}


def get_car(team_code: str) -> Optional[Auto]:
    """Get car for team code"""
    return CARS_2025.get(team_code)


def list_all_cars() -> Dict[str, Auto]:
    """Get all cars"""
    return CARS_2025.copy()


if __name__ == "__main__":
    # Test output
    print("=== CARS 2025 REGISTRY ===")
    for team_code, car in CARS_2025.items():
        front_df = car.aero_package.ala_anteriore.df_coeff
        rear_df = car.aero_package.ala_posteriore.df_coeff
        print(f"{team_code}: {car.nome} - Front DF: {front_df:.1f}kgf, Rear DF: {rear_df:.1f}kgf")
