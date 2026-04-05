"""
Vehicle Dynamics package - Dinamica veicolo F1 2025 (Physics V4)

Moduli:
- load_transfer: Trasferimento carico (longitudinale/laterale)
- kamm_circle: Cerchio di Kamm (grip combinato)
- handling: Bilanciamento handling (understeer/oversteer)
- balance: Balance vettura (aero/mechanical)
- cornering_limit: Limite accelerazione laterale

NOTA: Moduli V4 standalone, non dipendono da codice V1
"""

from .load_transfer import LoadTransfer, LoadTransferState
from .kamm_circle import KammCircle, FrictionCircle
from .handling import HandlingModel, HandlingState
from .balance import VehicleBalance, BalanceState
from .cornering_limit import CorneringLimitCalculator, CorneringLimitResult

__all__ = [
    # Load Transfer
    'LoadTransfer',
    'LoadTransferState',
    
    # Kamm Circle
    'KammCircle',
    'FrictionCircle',
    
    # Handling
    'HandlingModel',
    'HandlingState',
    
    # Balance
    'VehicleBalance',
    'BalanceState',
    
    # Cornering Limit
    'CorneringLimitCalculator',
    'CorneringLimitResult',
]
