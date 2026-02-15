# PowerUnit calibration – us-2022_miami

## Track stats
- heat_mean: 0.713
- heat_peak: 1.300
- drs_ratio: 0.278
- brake_density (MJ/km): 2.068
- power_bias: 0.888
- circuit_length_km: 5.337

## Regen profile
- base_factor: 0.839
- limit_nm: 352.4
- potential_mj_per_lap: 1.178
- regen_migration_bias: -0.257
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.905}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 2.017 | 1.581 | 0.735 | 0.504 | 0.79 |
| STANDARD | 3.235 | 1.338 | 0.315 | 0.809 | 0.669 |
| RICH | 3.96 | 0.979 | 0.05 | 0.99 | 0.489 |
| QUALY | 4.0 | 0.627 | 0.05 | 1.0 | 0.314 |
| WET | 2.523 | 1.564 | 0.556 | 0.631 | 0.782 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 99% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.31)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 209.51 |
| torque_ramp | 0.3665 |
| deployment_style | conservative |
| cooling_share | 0.493 |
| ers_output_kw | 95.97 |
| deploy_mj_per_lap | 2.017 |
| harvest_mj_per_lap | 1.581 |
| mguh_direct_ratio | 0.542 |
| target_soc_end_lap | 0.735 |
| torque_bias | -0.0112 |
| mguh_power_kw | 92.36 |

Notes:
- map: ECONOMY
- heat_scale: 0.952
- cooling_target: 0.493
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 247.61 |
| torque_ramp | 0.6465 |
| deployment_style | balanced |
| cooling_share | 0.443 |
| ers_output_kw | 143.95 |
| deploy_mj_per_lap | 3.235 |
| harvest_mj_per_lap | 1.338 |
| mguh_direct_ratio | 0.582 |
| target_soc_end_lap | 0.315 |
| torque_bias | 0.0388 |
| mguh_power_kw | 100.4 |

Notes:
- map: STANDARD
- heat_scale: 0.952
- cooling_target: 0.443
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 285.7 |
| torque_ramp | 0.8565 |
| deployment_style | aggressive |
| cooling_share | 0.393 |
| ers_output_kw | 179.94 |
| deploy_mj_per_lap | 3.96 |
| harvest_mj_per_lap | 0.979 |
| mguh_direct_ratio | 0.642 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0788 |
| mguh_power_kw | 105.42 |

Notes:
- map: RICH
- heat_scale: 0.952
- cooling_target: 0.393
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: True
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 314.27 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.627 |
| mguh_direct_ratio | 0.702 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1188 |
| mguh_power_kw | 110.44 |

Notes:
- map: QUALY
- heat_scale: 0.952
- cooling_target: 0.35
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 228.56 |
| torque_ramp | 0.5565 |
| deployment_style | wet_grip |
| cooling_share | 0.543 |
| ers_output_kw | 113.96 |
| deploy_mj_per_lap | 2.523 |
| harvest_mj_per_lap | 1.564 |
| mguh_direct_ratio | 0.532 |
| target_soc_end_lap | 0.556 |
| torque_bias | 0.0188 |
| mguh_power_kw | 90.36 |

Notes:
- map: WET
- heat_scale: 0.952
- cooling_target: 0.543
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 219.04 |
| torque_ramp | 0.4465 |
| deployment_style | harvest |
| cooling_share | 0.593 |
| ers_output_kw | 83.97 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.402 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0212 |
| mguh_power_kw | 80.32 |

Notes:
- map: RECHARGE
- heat_scale: 0.952
- cooling_target: 0.593
- torque_bias_delta: 0.0388
- drs_ratio: 0.278
- deploy_dynamic: 1.078
- harvest_dynamic: 0.836
- deploy_limit_hit: False
- harvest_limit_hit: True
