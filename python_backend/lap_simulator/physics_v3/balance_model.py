"""
Physics V3 — Balance Model Module

Simula il trasferimento di carico laterale e longitudinale tra gli assi.
Calcola il grip effettivo (mu_front_eff, mu_rear_eff) in base a:
- Accelerazioni laterali/longitudinali
- Distribuzione del carico
- Rigidità sospensioni (antiroll bars)

Modello:
- Fz_front, Fz_rear: carico verticale per asse
- load_transfer_lat: trasferimento di carico laterale (m * a_lat * H_CG / TRACK)
- Distribuzione tra assi via ARB rigidity
- Riduzione di grip: mu_eff = mu_base * (1 - penalty)

Fonte: spec physics-engine-v3-spec.md Section 4
"""

from dataclasses import dataclass
from typing import Optional
import math

from . import constants
from .aero_mapper import PhysicsAeroParams
from ..data_types import AeroSetup, EnvContext


# ============================================================================
# BalanceState — Output dataclass
# ============================================================================

@dataclass
class BalanceState:
    """Stato di bilanciamento e carico del veicolo."""

    # Grip effettivo per asse [0, mu_base]
    mu_front_eff: float                 # Grip effettivo asse anteriore
    mu_rear_eff: float                  # Grip effettivo asse posteriore

    # Load transfer [N] — componenti vettoriali
    load_transfer_lat: float            # Laterale (in curva)
    load_transfer_long: float           # Longitudinale (frenata/accelerazione)

    # Accelerazioni attuali
    a_lat_g: float                      # g laterali (v²/R)
    a_long_g: float                     # g longitudinali (accelerazione/frenata)

    # Descrizione qualitativa
    balance_label: str                  # "neutral", "understeer", "oversteer", "balanced"

    # Carichi verticali [N]
    Fz_front: float                     # Carico verticale asse anterior
    Fz_rear: float                      # Carico verticale asse posteriore

    # Distribuzione load transfer [%]
    load_transfer_lat_front: float      # % di LT andato all'asse anteriore
    load_transfer_lat_rear: float       # % di LT andato all'asse posteriore


def compute_balance(
    mu_base: float,
    aero: PhysicsAeroParams,
    aero_setup: AeroSetup,
    v_ms: float,
    radius_m: float,
    mass_kg: float,
    env: EnvContext,
    a_long_g: float = 0.0,
) -> BalanceState:
    """
    Calcola lo stato di bilanciamento e il grip effettivo per ogni asse.

    Algoritmo:
    1. Calcola Fz_front, Fz_rear da distribuzione peso + downforce
    2. Calcola a_lat = v²/R (accelerazione centripeta in curva)
    3. Calcola load_transfer_lat = m * a_lat * H_CG / TRACK
    4. Distribuisce LT tra assi via ARB rigidity
    5. Calcola mu_eff = mu_base * (1 - understeer/oversteer_penalty)
    6. Applica load sensitivity su grip (Pacejka effect)

    Args:
        mu_base: Base grip coefficient (da tyre_model.effective_grip)
        aero: PhysicsAeroParams (CLA, aero_balance)
        aero_setup: AeroSetup (antiroll_front/rear_rigidity)
        v_ms: Velocità attuale [m/s]
        radius_m: Raggio curva [m] (0 per rettilineo)
        mass_kg: Massa totale [kg]
        env: Contesto ambientale
        a_long_g: Accelerazione longitudinale [g] (frenata negativa)

    Returns:
        BalanceState con grip effettivo e load transfer
    """

    # ========================================================================
    # STEP 1: Calcola carichi verticali (Fz_front, Fz_rear)
    # ========================================================================
    # Fz = m*g (peso statico) + F_downforce distribuito
    #
    # Distribuzione peso statico (45.5% anteriore, 54.5% posteriore)
    # + downforce da aero distribuito secondo aero_balance

    # Peso statico
    weight_static_n = mass_kg * constants.G
    Fz_static_front = weight_static_n * constants.WEIGHT_DIST_FRONT
    Fz_static_rear = weight_static_n * (1.0 - constants.WEIGHT_DIST_FRONT)

    # Downforce dinamico [N]
    # F_df = 0.5 * rho * v² * CLA
    rho = env.air_density_kg_m3
    dynamic_pressure = 0.5 * rho * (v_ms ** 2)
    F_df_total = dynamic_pressure * aero.CLA
    F_df_front = F_df_total * aero.aero_balance
    F_df_rear = F_df_total * (1.0 - aero.aero_balance)

    # Carico verticale totale per asse
    Fz_front = Fz_static_front + F_df_front
    Fz_rear = Fz_static_rear + F_df_rear

    # ========================================================================
    # STEP 2: Accelerazione laterale (in curva)
    # ========================================================================
    if radius_m > 0.1:
        a_lat_g = (v_ms ** 2) / (radius_m * constants.G)
        a_lat_g = min(constants.MAX_LATERAL_G, a_lat_g)  # Clamp a max fisico
    else:
        a_lat_g = 0.0

    # ========================================================================
    # STEP 3: Trasferimento di carico laterale
    # ========================================================================
    # LT_lat = m * a_lat * H_CG / TRACK
    #
    # Questo è il carico che si trasferisce dalla ruota interna alla esterna
    # in una curva. Riduce il grip del pneumatico interno.

    load_transfer_lat = mass_kg * a_lat_g * constants.G * constants.H_CG / constants.TRACK_WIDTH
    load_transfer_lat = max(0.0, load_transfer_lat)  # Sempre non-negativo

    # ========================================================================
    # STEP 4: Distribuzione load transfer tra assi via ARB
    # ========================================================================
    # La rigidità del sospensione (ARB) determina come il carico è distribuito
    # tra asse anteriore e posteriore.
    #
    # Se ARB_front > ARB_rear:
    #   → asse anteriore più rigido → transfer più al posteriore
    #   → mu_rear ridotto più → oversteer
    #
    # Se ARB_front < ARB_rear:
    #   → asse posteriore più rigido → transfer più all'anteriore
    #   → mu_front ridotto più → understeer

    arb_front = aero_setup.antiroll_front_rigidity
    arb_rear = aero_setup.antiroll_rear_rigidity

    # Normalizza: arb_total = 1.0 per distribuzione proporzionale
    arb_total = arb_front + arb_rear
    arb_total = max(0.1, arb_total)  # Evita divisione per zero

    # Frazionamento transfer (controintuitivo: ARB rigida riduce transfer in quel asse)
    # ARB rigida → la sospensione resiste al transfer → transfer va altrove
    lt_front_frac = (arb_rear / arb_total) if arb_total > 0 else 0.5
    lt_rear_frac = 1.0 - lt_front_frac

    load_transfer_lat_front = load_transfer_lat * lt_front_frac
    load_transfer_lat_rear = load_transfer_lat * lt_rear_frac

    # ========================================================================
    # STEP 5: Riduzione grip da load transfer (Pacejka effect)
    # ========================================================================
    # Quando una ruota è scaricata (per effetto del trasferimento di carico),
    # perde grip proporzionalmente al carico ridotto.
    #
    # Semplificazione:
    #   mu_eff = mu_base * (1 - load_sensitivity * transfer_pct)
    #
    # Interna (caricata): grip quasi invariato
    # Esterna (scaricata): grip ridotto
    # (Il modello V3 è semplificato; in realtà usrebbe ogni ruota singolarmente)

    load_sensitivity = 0.3  # 30% di riduzione grip per carico transfer estremo
    mu_front_reduction = (load_transfer_lat_front / max(Fz_front, 100.0)) * load_sensitivity
    mu_rear_reduction = (load_transfer_lat_rear / max(Fz_rear, 100.0)) * load_sensitivity

    # ========================================================================
    # STEP 6: Applica aero-induced grip penalty (understeer/oversteer da setup)
    # ========================================================================
    # Il setup (ali sbilanciate) introduce perdite di grip addizionali.
    # understeer_grip_penalty: riduce mu_front
    # oversteer_grip_penalty: riduce mu_rear

    mu_front_eff = mu_base * (
        1.0
        - mu_front_reduction
        - aero.understeer_grip_penalty * 0.3  # aero contribuisce 30% della penalità
    )
    mu_rear_eff = mu_base * (
        1.0
        - mu_rear_reduction
        - aero.oversteer_grip_penalty * 0.3
    )

    # Clamp a range fisico
    mu_front_eff = max(0.0, min(mu_base, mu_front_eff))
    mu_rear_eff = max(0.0, min(mu_base, mu_rear_eff))

    # ========================================================================
    # STEP 7: Classifica il bilanciamento
    # ========================================================================
    mu_ratio = mu_rear_eff / max(mu_front_eff, 0.01)

    if mu_ratio < 0.95:
        # Posteriore significativamente meno grip → oversteer
        balance_label = "oversteer"
    elif mu_ratio > 1.05:
        # Anteriore significativamente meno grip → understeer
        balance_label = "understeer"
    else:
        balance_label = "neutral"

    # ========================================================================
    # STEP 8: Trasferimento carico longitudinale (frenata/accelerazione)
    # ========================================================================
    # LT_long = m * a_long_g * G * H_CG / WHEELBASE
    # Riduce il grip dell'asse posteriore in frenata (carico sul davanti)
    # Riduce il grip dell'asse anteriore in accelerazione (carico sul dietro)

    load_transfer_long = mass_kg * a_long_g * constants.G * constants.H_CG / constants.WHEELBASE
    load_transfer_long = max(-constants.WHEELBASE * 50, load_transfer_long)
    load_transfer_long = min(constants.WHEELBASE * 50, load_transfer_long)

    # ========================================================================
    # Assembla BalanceState
    # ========================================================================

    return BalanceState(
        mu_front_eff=mu_front_eff,
        mu_rear_eff=mu_rear_eff,
        load_transfer_lat=load_transfer_lat,
        load_transfer_long=load_transfer_long,
        a_lat_g=a_lat_g,
        a_long_g=a_long_g,
        balance_label=balance_label,
        Fz_front=Fz_front,
        Fz_rear=Fz_rear,
        load_transfer_lat_front=load_transfer_lat_front,
        load_transfer_lat_rear=load_transfer_lat_rear,
    )


# ============================================================================
# Helper: Stime velocità massima in curva (per corner_solver)
# ============================================================================

def estimate_max_corner_speed(
    radius_m: float,
    mu_available: float,
    mass_kg: float,
    aero: PhysicsAeroParams,
    env: EnvContext,
) -> float:
    """
    Stima la velocità massima in una curva data il grip disponibile.

    Usa formula semplificata:
        v_max² = (mu * (m*g + 0.5*rho*v²*CLA) / m) * R

    Risolvendo iterativamente poiché v² appare in entrambi i lati.

    Args:
        radius_m: Raggio della curva [m]
        mu_available: Grip disponibile [0, 2.0]
        mass_kg: Massa [kg]
        aero: PhysicsAeroParams
        env: Contesto ambientale

    Returns:
        Velocità massima in curva [m/s]
    """
    if radius_m < 0.1:
        return 0.0

    rho = env.air_density_kg_m3

    # Iterazione: inizia con stima semplice (ignora downforce)
    v_max = math.sqrt(mu_available * constants.G * radius_m)

    # Refine 5 volte con downforce
    for _ in range(5):
        dynamic_pressure = 0.5 * rho * (v_max ** 2)
        F_df = dynamic_pressure * aero.CLA
        Fz = mass_kg * constants.G + F_df

        v_max_new = math.sqrt(mu_available * Fz / mass_kg * radius_m)

        # Check convergenza
        if abs(v_max_new - v_max) < 0.1:
            break
        v_max = v_max_new

    return v_max


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    from ..data_types import EnvContext

    # Setup test
    test_aero = PhysicsAeroParams(
        CLA=3.20,
        CDA=1.10,
        CLA_front=1.60,
        CLA_rear=1.60,
        aero_balance=0.50,
        ground_effect_bonus=1.0,
        understeer_grip_penalty=0.0,
        oversteer_grip_penalty=0.0,
        CDA_drs_open=1.10,
        setup_quality_score=1.0,
    )
    test_setup = AeroSetup()
    test_env = EnvContext(
        air_temp_c=20.0,
        track_temp_c=40.0,
        air_density_kg_m3=1.225,
        wind_speed_kph=5.0,
        rain_intensity=0.0,
        track_rubber_level=0.8,
        water_film_level=0.0,
    )

    # Test curva Monaco (Turn 1, raggio ~668m)
    balance = compute_balance(
        mu_base=1.65,
        aero=test_aero,
        aero_setup=test_setup,
        v_ms=50.0,  # 180 kph
        radius_m=668.0,
        mass_kg=798.0,
        env=test_env,
        a_long_g=0.0,
    )
    print(f"Monaco Turn 1 balance: {balance}")
    print(f"  Grip: front={balance.mu_front_eff:.3f}, rear={balance.mu_rear_eff:.3f}")
    print(f"  Load transfer: {balance.load_transfer_lat:.0f} N")
    print(f"  Lateral G: {balance.a_lat_g:.2f}g")
