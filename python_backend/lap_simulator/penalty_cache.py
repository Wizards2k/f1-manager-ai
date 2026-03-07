"""
Penalty Cache System - Pre-computed static penalty values for performance optimization.

Caches circuit-specific values that don't change during a session to avoid repeated calculations.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from .data_types import CircuitConfig, SectionContext, SectionKind


@dataclass
class SectionPenaltyCache:
    """Pre-computed penalty values for a specific section."""
    section_id: str
    section_fraction: float  # length / total_length
    is_curve: bool
    is_straight: bool
    
    # Fuel penalty cache
    fuel_section_fraction: float
    
    # Tyre penalty cache
    tyre_section_weight: float  # 1.0 / n_curves for curves, 0.0 for straights
    
    # Engine penalty cache
    engine_applies: bool  # True for straights only
    
    # Setup penalty cache
    setup_curve_applies: bool
    setup_straight_applies: bool
    setup_curve_weight: float
    setup_straight_weight: float


@dataclass
class CircuitPenaltyCache:
    """Pre-computed penalty values for an entire circuit."""
    circuit_id: str
    total_length_m: float
    n_curve_sections: int
    
    # Section-specific caches
    sections: Dict[str, SectionPenaltyCache]
    
    # Fuel penalty cache
    fuel_reference_kg: float
    fuel_penalty_coeff: float
    
    # Tyre penalty cache
    tyre_reference_compound: str
    tyre_compound_deltas: Dict[str, float]
    tyre_wear_coeffs: Dict[str, float]
    tyre_temp_windows: Dict[str, Dict[str, list]]
    
    # Engine penalty cache
    engine_reference_cv: float
    engine_penalty_coeff: float
    engine_map_penalties: Dict[str, float]
    
    # Setup penalty cache
    setup_enabled: bool


class PenaltyCacheManager:
    """Manages penalty caches for multiple circuits."""
    
    def __init__(self):
        self._circuit_caches: Dict[str, CircuitPenaltyCache] = {}
    
    def get_or_create_cache(self, config: CircuitConfig) -> CircuitPenaltyCache:
        """Get existing cache or create new one for the circuit."""
        if config.circuit_id not in self._circuit_caches:
            self._circuit_caches[config.circuit_id] = self._create_circuit_cache(config)
        return self._circuit_caches[config.circuit_id]
    
    def _create_circuit_cache(self, config: CircuitConfig) -> CircuitPenaltyCache:
        """Create a new penalty cache for the circuit."""
        sections = {}
        
        # Pre-compute section-specific values
        for section in config.sections:
            section_cache = self._create_section_cache(section, config)
            sections[section.section_id] = section_cache
        
        return CircuitPenaltyCache(
            circuit_id=config.circuit_id,
            total_length_m=config.circuit_length_m,
            n_curve_sections=config.n_curve_sections,
            sections=sections,
            
            # Fuel cache
            fuel_reference_kg=getattr(config, 'fuel_reference_kg', 10.0),
            fuel_penalty_coeff=getattr(config, 'fuel_penalty_coeff', 0.0),
            
            # Tyre cache
            tyre_reference_compound=getattr(config, 'tyre_reference_compound', 'C3'),
            tyre_compound_deltas=getattr(config, 'tyre_compound_deltas', {}),
            tyre_wear_coeffs=getattr(config, 'tyre_wear_coeffs', {}),
            tyre_temp_windows=getattr(config, 'tyre_temp_windows', {}),
            
            # Engine cache
            engine_reference_cv=getattr(config, 'engine_reference_cv', 1008.0),
            engine_penalty_coeff=getattr(config, 'engine_penalty_coeff', 0.0),
            engine_map_penalties=getattr(config, 'engine_map_penalties', {}),
            
            # Setup cache
            setup_enabled=bool(getattr(config, 'setup_penalty_config', None)),
        )
    
    def _create_section_cache(self, section: SectionContext, config: CircuitConfig) -> SectionPenaltyCache:
        """Create cache for a specific section."""
        # Section fraction for fuel penalty
        section_fraction = section.length_m / config.circuit_length_m
        
        # Curve detection
        curve_kinds = {
            SectionKind.VERY_SLOW_CORNER, 
            SectionKind.SLOW_CORNER, 
            SectionKind.MEDIUM_CORNER, 
            SectionKind.FAST_CORNER, 
            SectionKind.ULTRA_FAST_CORNER
        }
        is_curve = section.kind in curve_kinds
        is_straight = section.kind in [SectionKind.STRAIGHT, SectionKind.MEDIUM_STRAIGHT]
        
        # Engine penalty applies only on straights
        from .engine_penalty import STRAIGHT_KINDS
        engine_applies = section.kind in STRAIGHT_KINDS
        
        # Setup penalty weights
        tyre_section_weight = 1.0 / max(1, config.n_curve_sections) if is_curve else 0.0
        setup_curve_weight = 0.1 if is_curve else 0.0
        setup_straight_weight = 0.1 if is_straight else 0.0
        
        return SectionPenaltyCache(
            section_id=section.section_id,
            section_fraction=section_fraction,
            is_curve=is_curve,
            is_straight=is_straight,
            
            # Fuel cache
            fuel_section_fraction=section_fraction,
            
            # Tyre cache
            tyre_section_weight=tyre_section_weight,
            
            # Engine cache
            engine_applies=engine_applies,
            
            # Setup cache
            setup_curve_applies=is_curve,
            setup_straight_applies=is_straight,
            setup_curve_weight=setup_curve_weight,
            setup_straight_weight=setup_straight_weight,
        )
    
    def clear_cache(self, circuit_id: Optional[str] = None):
        """Clear cache for specific circuit or all circuits."""
        if circuit_id:
            self._circuit_caches.pop(circuit_id, None)
        else:
            self._circuit_caches.clear()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_circuits": len(self._circuit_caches),
            "total_sections": sum(
                len(cache.sections) for cache in self._circuit_caches.values()
            ),
        }


# Global cache manager instance
_cache_manager = PenaltyCacheManager()


def get_penalty_cache(config: CircuitConfig) -> CircuitPenaltyCache:
    """Get penalty cache for the circuit (convenience function)."""
    return _cache_manager.get_or_create_cache(config)


def clear_penalty_cache(circuit_id: Optional[str] = None):
    """Clear penalty cache (convenience function)."""
    _cache_manager.clear_cache(circuit_id)


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics (convenience function)."""
    return _cache_manager.get_cache_stats()
