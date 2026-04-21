"""
Setup Effects - Calcolo effetti sospensioni sulla performance.

Estratto dal waypoint_integrator.py (V6.3) per modularizzazione.
Mantiene la stessa logica e costanti del codice originale.
"""

from typing import Dict, Optional


def compute_suspension_effects(suspension_setup: Optional[Dict]) -> Dict[str, float]:
    """
    Calcola effetti sospensioni sulla performance usando valori fisici reali.

    P5 FIX: Usa valori reali (N/mm, Nm/deg) invece di slider.
    La conversione slider→reale avviene qui tramite slider_to_real().

    Le sospensioni influenzano:
    1. Grip meccanico (contatto gomma-asfalto) - da spring rate
    2. Load transfer laterale (rollio in curva) - da ARB
    3. Stabilità in frenata - da bilanciamento molle ant/post
    4. Effetto ride height su downforce - da altezza da suolo

    Args:
        suspension_setup: dict con valori slider (spring_front 1-50, arb_front 1-30,
                         ride_height_front 1-30) + valori reali convertiti
                         (spring_front_Nmm, arb_front_Nmdeg, ride_height_front_mm)

    Returns:
        Dict con fattori moltiplicativi per grip/stabilità
    """
    if not suspension_setup:
        return {
            'mechanical_grip_factor': 1.0,
            'corner_grip_penalty': 0.0,
            'braking_stability_factor': 1.0,
            'ride_height_aero_factor': 1.0,
            'ride_height_front_m': 0.040,  # default 40mm
            'ride_height_rear_m': 0.050,   # default 50mm
        }

    # ── Valori reali F1 (da slider_to_real) ──────────────────────────────
    # Se i valori reali sono già nel dict (da get_setup_dict), usali.
    # Altrimenti converti da slider (backward compatibility con range 1-50/1-30).
    # Nuovo range: spring 1-50, ARB 1-30, RH 1-30
    spring_front_Nmm = float(suspension_setup.get('spring_front_Nmm',
        suspension_setup.get('spring_front', 25.0) * 12.0 + 100.0))
    spring_rear_Nmm = float(suspension_setup.get('spring_rear_Nmm',
        suspension_setup.get('spring_rear', 33.0) * 14.0 + 100.0))
    arb_front_Nmdeg = float(suspension_setup.get('arb_front_Nmdeg',
        suspension_setup.get('arb_front', 11.0) * 15.0 + 35.0))
    arb_rear_Nmdeg = float(suspension_setup.get('arb_rear_Nmdeg',
        suspension_setup.get('arb_rear', 18.0) * 15.0 + 35.0))
    ride_height_front_mm = float(suspension_setup.get('ride_height_front_mm',
        suspension_setup.get('ride_height_front', 7.0) * 1.0 + 19.0))
    ride_height_rear_mm = float(suspension_setup.get('ride_height_rear_mm',
        suspension_setup.get('ride_height_rear', 14.0) * 1.2 + 28.8))

    # ── Valori ottimali F1 ───────────────────────────────────────────────
    # Spring: ~400 N/mm front, ~562 N/mm rear (slider 25/33)
    SPRING_FRONT_OPT_NMM = 400.0   # N/mm
    SPRING_REAR_OPT_NMM = 562.0    # N/mm
    # ARB: ~200 Nm/deg front, ~305 Nm/deg rear (slider 11/18)
    ARB_FRONT_OPT_NMDEG = 200.0    # Nm/deg
    ARB_REAR_OPT_NMDEG = 305.0     # Nm/deg
    # Ride height: ~26 mm front, ~46 mm rear (slider 7/14)
    RH_FRONT_OPT_MM = 26.0         # mm
    RH_REAR_OPT_MM = 45.6          # mm

    # ── Spring rate → grip meccanico ─────────────────────────────────────
    # Deviazione normalizzata rispetto all'ottimale F1.
    # Range: 120-700 N/mm front, 173-840 N/mm rear.
    # Troppo morbido → rollio, imprecisione. Troppo rigido → rimbalzo, perdita contatto.
    spring_dev_f = abs(spring_front_Nmm - SPRING_FRONT_OPT_NMM) / SPRING_FRONT_OPT_NMM
    spring_dev_r = abs(spring_rear_Nmm - SPRING_REAR_OPT_NMM) / SPRING_REAR_OPT_NMM
    spring_dev_avg = (spring_dev_f + spring_dev_r) / 2.0

    # Penalità progressiva: fino a ~7% grip loss agli estremi
    mechanical_grip_factor = 1.0 - 0.07 * (spring_dev_avg ** 1.5)
    mechanical_grip_factor = max(0.93, min(1.0, mechanical_grip_factor))

    # ── ARB → load transfer in curva ─────────────────────────────────────
    # Deviazione normalizzata rispetto all'ottimale F1.
    # Range: 50-500 Nm/deg.
    # Troppo rigido → eccesso load transfer → meno grip ruota interna
    # Troppo morbido → troppo rollio → meno reattività (penalità minore)
    arb_dev_f = abs(arb_front_Nmdeg - ARB_FRONT_OPT_NMDEG) / ARB_FRONT_OPT_NMDEG
    arb_dev_r = abs(arb_rear_Nmdeg - ARB_REAR_OPT_NMDEG) / ARB_REAR_OPT_NMDEG

    # Asimmetria: troppo rigido penalizza di più
    if arb_front_Nmdeg > ARB_FRONT_OPT_NMDEG:
        arb_dev_f *= 1.3
    if arb_rear_Nmdeg > ARB_REAR_OPT_NMDEG:
        arb_dev_r *= 1.3

    arb_dev_avg = (arb_dev_f + arb_dev_r) / 2.0
    # Fino a ~8% penalità laterale agli estremi
    corner_grip_penalty = 0.08 * (arb_dev_avg ** 1.3)
    corner_grip_penalty = min(0.10, corner_grip_penalty)

    # ── Bilanciamento molle → stabilità frenata ──────────────────────────
    # Se le molle sono sbilanciate (es. molto rigido davanti, morbido dietro)
    # la frenata diventa instabile (bloccaggio ruote)
    ratio_front = spring_front_Nmm / SPRING_FRONT_OPT_NMM
    ratio_rear = spring_rear_Nmm / SPRING_REAR_OPT_NMM
    spring_imbalance = abs(ratio_front - ratio_rear)
    braking_stability_factor = 1.0 - 0.05 * min(1.0, spring_imbalance)
    braking_stability_factor = max(0.95, min(1.0, braking_stability_factor))

    # ── Ride height → effetto aero ───────────────────────────────────────
    # P6: Ride height influenza la downforce del fondo.
    # Ottimale: ~26mm front, ~46mm rear (più basso = più ground effect).
    # Penalità per altezza eccessiva (troppo alto = meno downforce dal fondo).
    # Range: 20-47mm front, 30-66mm rear.
    # Il fattore è moltiplicativo sulla downforce del fondo (già calcolata in aero).
    rh_front_dev = (ride_height_front_mm - RH_FRONT_OPT_MM) / RH_FRONT_OPT_MM
    rh_rear_dev = (ride_height_rear_mm - RH_REAR_OPT_MM) / RH_REAR_OPT_MM
    # Ogni mm sopra l'ottimale riduce la downforce del fondo di ~1.5%
    # (ground effect è sensibile all'altezza: più basso = più suction)
    rh_aero_penalty = 0.015 * max(0.0, rh_front_dev) + 0.015 * max(0.0, rh_rear_dev)
    ride_height_aero_factor = max(0.90, 1.0 - rh_aero_penalty)

    return {
        'mechanical_grip_factor': mechanical_grip_factor,
        'corner_grip_penalty': corner_grip_penalty,
        'braking_stability_factor': braking_stability_factor,
        'ride_height_aero_factor': ride_height_aero_factor,
        # P6: Ride height in metri per compute_forces()
        'ride_height_front_m': ride_height_front_mm / 1000.0,
        'ride_height_rear_m': ride_height_rear_mm / 1000.0,
    }
