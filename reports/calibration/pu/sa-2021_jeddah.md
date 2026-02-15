# PowerUnit calibration – sa-2021_jeddah

## Track stats
- heat_mean: 0.780
- heat_peak: 1.500
- drs_ratio: 0.478
- brake_density (MJ/km): 2.093
- power_bias: 0.765
- circuit_length_km: 6.102

## Regen profile
- base_factor: 0.84
- limit_nm: 353.2
- potential_mj_per_lap: 1.558
- regen_migration_bias: -0.256
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.467}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.961 | 1.586 | 0.744 | 0.49 | 0.793 |
| STANDARD | 3.147 | 1.343 | 0.329 | 0.787 | 0.671 |
| RICH | 3.851 | 0.982 | 0.05 | 0.963 | 0.491 |
| QUALY | 4.0 | 0.629 | 0.05 | 1.0 | 0.315 |
| WET | 2.454 | 1.569 | 0.567 | 0.614 | 0.784 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 96% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.31)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 216.7 |
| torque_ramp | 0.3518 |
| deployment_style | conservative |
| cooling_share | 0.506 |
| ers_output_kw | 103.22 |
| deploy_mj_per_lap | 1.961 |
| harvest_mj_per_lap | 1.586 |
| mguh_direct_ratio | 0.572 |
| target_soc_end_lap | 0.744 |
| torque_bias | -0.0235 |
| mguh_power_kw | 75.98 |

Notes:
- map: ECONOMY
- heat_scale: 0.985
- cooling_target: 0.506
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 256.1 |
| torque_ramp | 0.6318 |
| deployment_style | balanced |
| cooling_share | 0.456 |
| ers_output_kw | 154.83 |
| deploy_mj_per_lap | 3.147 |
| harvest_mj_per_lap | 1.343 |
| mguh_direct_ratio | 0.612 |
| target_soc_end_lap | 0.329 |
| torque_bias | 0.0265 |
| mguh_power_kw | 82.58 |

Notes:
- map: STANDARD
- heat_scale: 0.985
- cooling_target: 0.456
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 295.5 |
| torque_ramp | 0.8418 |
| deployment_style | aggressive |
| cooling_share | 0.406 |
| ers_output_kw | 193.54 |
| deploy_mj_per_lap | 3.851 |
| harvest_mj_per_lap | 0.982 |
| mguh_direct_ratio | 0.672 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0665 |
| mguh_power_kw | 86.71 |

Notes:
- map: RICH
- heat_scale: 0.985
- cooling_target: 0.406
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 325.05 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.356 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.629 |
| mguh_direct_ratio | 0.732 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1065 |
| mguh_power_kw | 90.84 |

Notes:
- map: QUALY
- heat_scale: 0.985
- cooling_target: 0.356
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 236.4 |
| torque_ramp | 0.5418 |
| deployment_style | wet_grip |
| cooling_share | 0.556 |
| ers_output_kw | 122.57 |
| deploy_mj_per_lap | 2.454 |
| harvest_mj_per_lap | 1.569 |
| mguh_direct_ratio | 0.562 |
| target_soc_end_lap | 0.567 |
| torque_bias | 0.0065 |
| mguh_power_kw | 74.33 |

Notes:
- map: WET
- heat_scale: 0.985
- cooling_target: 0.556
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 226.55 |
| torque_ramp | 0.4318 |
| deployment_style | harvest |
| cooling_share | 0.606 |
| ers_output_kw | 90.32 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.432 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0335 |
| mguh_power_kw | 66.07 |

Notes:
- map: RECHARGE
- heat_scale: 0.985
- cooling_target: 0.606
- torque_bias_delta: 0.0265
- drs_ratio: 0.478
- deploy_dynamic: 1.049
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: True
