"""
Test: Physics V3 Constants Validation

Verifica che le costanti fisiche F1 2025 siano dentro i range attesi.
"""

import pytest
from python_backend.lap_simulator.physics_v3 import constants


class TestPhysicalConstants:
    """Test costanti fisiche base."""

    def test_gravity(self):
        """Gravità terrestre."""
        assert 9.8 <= constants.G <= 9.82

    def test_air_density(self):
        """Densità aria a livello mare."""
        assert 1.2 <= constants.RHO_SEA_LEVEL <= 1.23

    def test_mass_dry(self):
        """Massa minima FIA."""
        assert constants.MASS_DRY_KG == 798.0

    def test_fuel_race(self):
        """Benzina inizio gara."""
        assert 105 <= constants.FUEL_RACE_START_KG <= 115


class TestPowerConstants:
    """Test power unit constants."""

    def test_ice_power(self):
        """Potenza motore termico."""
        assert 740 <= constants.ICE_PEAK_POWER_KW <= 760

    def test_ers_power(self):
        """Potenza MGU-K."""
        assert 155 <= constants.ERS_PEAK_POWER_KW <= 165

    def test_total_power(self):
        """Potenza totale ICE + ERS."""
        assert constants.PU_TOTAL_PEAK_KW == (
            constants.ICE_PEAK_POWER_KW + constants.ERS_PEAK_POWER_KW
        )

    def test_drivetrain_efficiency(self):
        """Perdite meccaniche."""
        assert 0.88 <= constants.DRIVETRAIN_EFFICIENCY <= 0.91


class TestAeroConstants:
    """Test aerodinamica constants."""

    def test_cla_range(self):
        """Range CLA (downforce)."""
        assert constants.CLA_MIN < constants.CLA_NEUTRAL < constants.CLA_MAX
        assert constants.CLA_MIN == 2.80
        assert constants.CLA_MAX == 4.80
        assert constants.CLA_NEUTRAL == 3.20

    def test_cda_range(self):
        """Range CDA (drag)."""
        assert constants.CDA_MIN < constants.CDA_NEUTRAL < constants.CDA_MAX
        assert constants.CDA_MIN == 0.85
        assert constants.CDA_MAX == 1.60

    def test_drs_reduction(self):
        """DRS drag reduction factor."""
        assert 0.15 <= constants.DRS_DRAG_REDUCTION_FACTOR <= 0.20


class TestGripConstants:
    """Test grip coefficients."""

    def test_mu_base_range(self):
        """Grip base per compound."""
        assert constants.MU_BASE["C1"] < constants.MU_BASE["C6"]
        assert constants.MU_BASE["WET"] < constants.MU_BASE["INTERMEDIATE"]
        assert all(0.7 <= mu <= 1.9 for mu in constants.MU_BASE.values())

    def test_cornering_efficiency(self):
        """Efficienza grip in curva."""
        assert 0.80 <= constants.GRIP_CORNERING_EFFICIENCY <= 0.90


class TestBrakeConstants:
    """Test brake system constants."""

    def test_brake_mu_map(self):
        """Mappa μ_brake(T)."""
        assert len(constants.BRAKE_MU_MAP) >= 5
        # Verifica che sia ordinato per temperatura
        temps = [t for t, _ in constants.BRAKE_MU_MAP]
        assert temps == sorted(temps)
        # Picco attorno a 700°C
        temp_peak_idx = max(
            range(len(constants.BRAKE_MU_MAP)),
            key=lambda i: constants.BRAKE_MU_MAP[i][1],
        )
        assert 600 <= constants.BRAKE_MU_MAP[temp_peak_idx][0] <= 800

    def test_brake_temperature_windows(self):
        """Finestra termica freni."""
        assert constants.BRAKE_TEMP_OPTIMAL_MIN_C < constants.BRAKE_TEMP_OPTIMAL_MAX_C
        assert constants.BRAKE_TEMP_OPTIMAL_MAX_C < constants.BRAKE_TEMP_FADE_C

    def test_interpolate_brake_mu(self):
        """Test interpolazione μ_brake."""
        mu_cold = constants.interpolate_brake_mu(200)
        mu_hot = constants.interpolate_brake_mu(700)
        assert mu_cold < mu_hot  # Cold < optimal


class TestGeometryConstants:
    """Test auto geometry."""

    def test_cg_height(self):
        """Altezza centro di gravità."""
        assert 0.25 <= constants.H_CG <= 0.30

    def test_wheelbase(self):
        """Interasse."""
        assert 3.5 <= constants.WHEELBASE <= 3.7

    def test_weight_distribution(self):
        """Distribuzione peso."""
        assert 0.40 <= constants.WEIGHT_DIST_FRONT <= 0.50


class TestDynamicsLimits:
    """Test limiti dinamici."""

    def test_max_lateral_g(self):
        """G laterali massimi."""
        assert 5.0 <= constants.MAX_LATERAL_G <= 6.0

    def test_max_brake_decel_g(self):
        """G frenata massimi."""
        assert 6.0 <= constants.MAX_BRAKE_DECEL_G <= 7.0


class TestTargetLapTimes:
    """Test target lap times F1 2025."""

    def test_monza_target(self):
        """Target Monza."""
        assert "it-1922_monza" in constants.TARGET_LAP_TIMES
        assert 78 <= constants.TARGET_LAP_TIMES["it-1922_monza"] <= 81

    def test_monaco_target(self):
        """Target Monaco."""
        assert "mc-1929_monaco" in constants.TARGET_LAP_TIMES
        assert 69 <= constants.TARGET_LAP_TIMES["mc-1929_monaco"] <= 72

    def test_all_targets(self):
        """Tutti i target per 10 circuiti."""
        assert len(constants.TARGET_LAP_TIMES) >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
