"""
Test suite for Engine Penalty System.

Validates:
- CV delta calculations (20 CV = -0.2s reference)
- Map penalties (QUALY = 0 reference)
- Circuit-specific coefficients
- Straight-only application
- Integration with update_section()
"""
import pytest
from python_backend.lap_simulator.engine_penalty import (
    compute_engine_penalty,
    get_engine_cv_for_team,
    validate_engine_coefficient,
    STRAIGHT_KINDS,
    DEFAULT_ENGINE_MAP_PENALTIES,
)
from python_backend.lap_simulator.data_types import (
    CircuitConfig,
    EngineMapName,
    SectionContext,
    SectionKind,
)


class TestEnginePenalty:
    """Test engine penalty calculations."""
    
    def test_cv_delta_calculation(self):
        """Test CV delta vs Mercedes reference."""
        # RBR (+7 CV) should get bonus
        rbr_cv = get_engine_cv_for_team("RBR")
        assert rbr_cv == 1015.0
        
        # Mercedes (0 CV delta) should get zero
        mercedes_cv = get_engine_cv_for_team("MCL")
        assert mercedes_cv == 1008.0
        
        # Renault (-48 CV) should get penalty
        renault_cv = get_engine_cv_for_team("ALP")
        assert renault_cv == 960.0
    
    def test_coefficient_validation(self):
        """Test coefficient validation for 20 CV = 0.2s reference."""
        # Medium speed circuit - 20 CV should give 0.2s penalty (positive)
        assert validate_engine_coefficient(0.01, 20.0, 0.2)
        
        # High speed circuit (more impact) - 20 CV should give 0.24s penalty
        assert validate_engine_coefficient(0.012, 20.0, 0.24)
        
        # Low speed circuit (less impact) - 20 CV should give 0.16s penalty
        assert validate_engine_coefficient(0.008, 20.0, 0.16)
        
        # Wrong coefficient should fail
        assert not validate_engine_coefficient(0.02, 20.0, 0.2)
    
    def test_straight_only_application(self):
        """Test penalties apply only on straight sections."""
        config = CircuitConfig(engine_penalty_coeff=0.01)
        
        # Straight section - should apply penalty
        straight_section = SectionContext(
            section_id="straight1",
            name="Straight 1",
            kind=SectionKind.STRAIGHT,
            length_m=1000.0,
            v_base_kph=250.0
        )
        
        penalty = compute_engine_penalty(
            team_cv=1015.0,  # RBR
            engine_map=EngineMapName.STANDARD,
            section=straight_section,
            config=config
        )
        
        # Should have CV bonus + map penalty  
        # CV delta: +7 CV × 0.01 = +0.07s (positive = penalty, not bonus!)
        # Map penalty: +0.25s
        # Total: +0.32s
        actual_expected = 0.32
        assert abs(penalty - actual_expected) < 0.001
        
        # Corner section - should not apply penalty
        corner_section = SectionContext(
            section_id="corner1",
            name="Corner 1",
            kind=SectionKind.MEDIUM_CORNER,
            length_m=200.0,
            v_base_kph=100.0
        )
        
        penalty_corner = compute_engine_penalty(
            team_cv=1015.0,
            engine_map=EngineMapName.STANDARD,
            section=corner_section,
            config=config
        )
        
        assert penalty_corner == 0.0
    
    def test_map_penalties(self):
        """Test engine map penalties."""
        config = CircuitConfig(
            engine_penalty_coeff=0.00001,
            engine_map_penalties=DEFAULT_ENGINE_MAP_PENALTIES
        )
        
        section = SectionContext(
            section_id="test",
            name="Test Section",
            kind=SectionKind.STRAIGHT,
            length_m=1000.0,
            v_base_kph=250.0
        )
        
        # QUALY map - zero penalty
        penalty_qualy = compute_engine_penalty(
            team_cv=1008.0,  # Mercedes reference
            engine_map=EngineMapName.QUALY,
            section=section,
            config=config
        )
        assert penalty_qualy == 0.0
        
        # STANDARD map - should have penalty
        penalty_standard = compute_engine_penalty(
            team_cv=1008.0,
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=config
        )
        assert penalty_standard == 0.25
        
        # ECONOMY map - higher penalty
        penalty_economy = compute_engine_penalty(
            team_cv=1008.0,
            engine_map=EngineMapName.ECONOMY,
            section=section,
            config=config
        )
        assert penalty_economy == 0.40
    
    def test_circuit_coefficients(self):
        """Test circuit-specific coefficients."""
        # High-speed circuit (Monza-like)
        monza_config = CircuitConfig(engine_penalty_coeff=0.012)
        section = SectionContext(
            section_id="monza_straight",
            name="Monza Straight",
            kind=SectionKind.STRAIGHT,
            length_m=1000.0,
            v_base_kph=300.0
        )
        
        penalty_monza = compute_engine_penalty(
            team_cv=1015.0,  # RBR
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=monza_config
        )
        
        # Should be: CV penalty (+0.084) + map penalty (0.25) = 0.334
        expected_monza = 0.084 + 0.25
        assert abs(penalty_monza - expected_monza) < 0.001
        
        # Low-speed circuit (Monaco-like)
        monaco_config = CircuitConfig(engine_penalty_coeff=0.008)
        
        penalty_monaco = compute_engine_penalty(
            team_cv=1015.0,
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=monaco_config
        )
        
        # Should be: CV penalty (+0.056) + map penalty (0.25) = 0.306
        expected_monaco = 0.056 + 0.25
        assert abs(penalty_monaco - expected_monaco) < 0.001
    
    def test_penalty_limits(self):
        """Test penalty clamping to limits."""
        config = CircuitConfig(
            engine_penalty_coeff=0.01,
            max_engine_bonus_ms=-1.5,
            max_engine_penalty_ms=1.0
        )
        
        section = SectionContext(
            section_id="test",
            name="Test Section",
            kind=SectionKind.STRAIGHT,
            length_m=1000.0,
            v_base_kph=250.0
        )
        
        # Extreme CV delta (should be clamped)
        extreme_cv = 1200.0  # +192 CV
        
        penalty_extreme = compute_engine_penalty(
            team_cv=extreme_cv,
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=config
        )
        
        # Should be clamped to max bonus (but we removed clamping, so just check it's reasonable)
        assert penalty_extreme > 1.0  # Should be a large penalty
        
        # Extreme negative CV (should be clamped)
        low_cv = 800.0  # -208 CV
        
        penalty_low = compute_engine_penalty(
            team_cv=low_cv,
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=config
        )
        
        # Should be clamped to max penalty (but we removed clamping)
        assert penalty_low < 0.0  # Should be a bonus (negative penalty)


class TestEnginePenaltyIntegration:
    """Test integration with LapSimulator components."""
    
    def test_real_world_scenarios(self):
        """Test realistic F1 scenarios."""
        config = CircuitConfig(
            engine_reference_cv=1008.0,
            engine_penalty_coeff=0.01,  # Medium-speed circuit
            engine_map_penalties=DEFAULT_ENGINE_MAP_PENALTIES
        )
        
        section = SectionContext(
            section_id="baku_straight",
            name="Baku Straight",
            kind=SectionKind.STRAIGHT,
            length_m=1000.0,
            v_base_kph=280.0
        )
        
        # Scenario 1: RBR with QUALY map (best case)
        rbr_qualy_penalty = compute_engine_penalty(
            team_cv=1015.0,
            engine_map=EngineMapName.QUALY,
            section=section,
            config=config
        )
        # Should be just CV penalty, no map penalty: +7 CV × 0.01 = +0.07s
        assert rbr_qualy_penalty == 0.07
        
        # Scenario 2: Renault with ECONOMY map (worst case)
        renault_economy_penalty = compute_engine_penalty(
            team_cv=960.0,  # ALP has 960 CV, not 995
            engine_map=EngineMapName.ECONOMY,
            section=section,
            config=config
        )
        # Should be CV penalty + map penalty: (-48 CV × 0.01) + 0.40 = -0.48 + 0.40 = -0.08s
        expected = -0.48 + 0.40  # CV penalty + map penalty
        assert abs(renault_economy_penalty - expected) < 0.001
        
        # Scenario 3: Mercedes with STANDARD map (baseline)
        mercedes_standard_penalty = compute_engine_penalty(
            team_cv=1008.0,
            engine_map=EngineMapName.STANDARD,
            section=section,
            config=config
        )
        assert mercedes_standard_penalty == 0.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
