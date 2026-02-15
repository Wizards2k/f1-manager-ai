# PowerUnit calibration – br-1940_sao_paulo

## Track stats
- heat_mean: 0.845
- heat_peak: 1.500
- drs_ratio: 0.000
- brake_density (MJ/km): 2.935
- power_bias: 0.886
- circuit_length_km: 4.251

## Regen profile
- base_factor: 0.864
- limit_nm: 382.7
- potential_mj_per_lap: 1.447
- regen_migration_bias: -0.218
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.804}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 2.065 | 1.768 | 0.755 | 0.516 | 0.884 |
| STANDARD | 3.313 | 1.497 | 0.328 | 0.828 | 0.749 |
| RICH | 4.0 | 1.094 | 0.05 | 1.0 | 0.547 |
| QUALY | 4.0 | 0.702 | 0.05 | 1.0 | 0.351 |
| WET | 2.584 | 1.749 | 0.575 | 0.646 | 0.875 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 100% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.3 |
| torque_ramp | 0.3664 |
| deployment_style | conservative |
| cooling_share | 0.519 |
| ers_output_kw | 88.45 |
| deploy_mj_per_lap | 2.065 |
| harvest_mj_per_lap | 1.768 |
| mguh_direct_ratio | 0.5 |
| target_soc_end_lap | 0.755 |
| torque_bias | -0.0114 |
| mguh_power_kw | 63.74 |

Notes:
- map: ECONOMY
- heat_scale: 1.001
- cooling_target: 0.519
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 260.35 |
| torque_ramp | 0.6464 |
| deployment_style | balanced |
| cooling_share | 0.469 |
| ers_output_kw | 132.68 |
| deploy_mj_per_lap | 3.313 |
| harvest_mj_per_lap | 1.497 |
| mguh_direct_ratio | 0.54 |
| target_soc_end_lap | 0.328 |
| torque_bias | 0.0386 |
| mguh_power_kw | 69.28 |

Notes:
- map: STANDARD
- heat_scale: 1.001
- cooling_target: 0.469
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 300.41 |
| torque_ramp | 0.8564 |
| deployment_style | aggressive |
| cooling_share | 0.419 |
| ers_output_kw | 165.85 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 1.094 |
| mguh_direct_ratio | 0.6 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0786 |
| mguh_power_kw | 72.74 |

Notes:
- map: RICH
- heat_scale: 1.001
- cooling_target: 0.419
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: True
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 330.45 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.369 |
| ers_output_kw | 187.96 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.702 |
| mguh_direct_ratio | 0.66 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1186 |
| mguh_power_kw | 76.21 |

Notes:
- map: QUALY
- heat_scale: 1.001
- cooling_target: 0.369
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 240.33 |
| torque_ramp | 0.5564 |
| deployment_style | wet_grip |
| cooling_share | 0.569 |
| ers_output_kw | 105.04 |
| deploy_mj_per_lap | 2.584 |
| harvest_mj_per_lap | 1.749 |
| mguh_direct_ratio | 0.49 |
| target_soc_end_lap | 0.575 |
| torque_bias | 0.0186 |
| mguh_power_kw | 62.35 |

Notes:
- map: WET
- heat_scale: 1.001
- cooling_target: 0.569
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 230.31 |
| torque_ramp | 0.4464 |
| deployment_style | harvest |
| cooling_share | 0.619 |
| ers_output_kw | 77.4 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.36 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0214 |
| mguh_power_kw | 55.42 |

Notes:
- map: RECHARGE
- heat_scale: 1.001
- cooling_target: 0.619
- torque_bias_delta: 0.0386
- drs_ratio: 0.0
- deploy_dynamic: 1.104
- harvest_dynamic: 0.935
- deploy_limit_hit: False
- harvest_limit_hit: True
