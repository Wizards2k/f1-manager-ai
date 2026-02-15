# PowerUnit calibration – us-2023_las_vegas

## Track stats
- heat_mean: 0.660
- heat_peak: 1.300
- drs_ratio: 0.196
- brake_density (MJ/km): 1.539
- power_bias: 0.725
- circuit_length_km: 6.144

## Regen profile
- base_factor: 0.824
- limit_nm: 333.9
- potential_mj_per_lap: 1.162
- regen_migration_bias: -0.282
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.595}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.89 | 1.466 | 0.736 | 0.472 | 0.733 |
| STANDARD | 3.033 | 1.241 | 0.331 | 0.758 | 0.621 |
| RICH | 3.712 | 0.908 | 0.05 | 0.928 | 0.454 |
| QUALY | 4.0 | 0.582 | 0.05 | 1.0 | 0.291 |
| WET | 2.366 | 1.451 | 0.563 | 0.592 | 0.726 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.29)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 206.58 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.482 |
| ers_output_kw | 91.47 |
| deploy_mj_per_lap | 1.89 |
| harvest_mj_per_lap | 1.466 |
| mguh_direct_ratio | 0.529 |
| target_soc_end_lap | 0.736 |
| torque_bias | -0.0275 |
| mguh_power_kw | 86.63 |

Notes:
- map: ECONOMY
- heat_scale: 0.939
- cooling_target: 0.482
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 244.14 |
| torque_ramp | 0.6271 |
| deployment_style | balanced |
| cooling_share | 0.432 |
| ers_output_kw | 137.21 |
| deploy_mj_per_lap | 3.033 |
| harvest_mj_per_lap | 1.241 |
| mguh_direct_ratio | 0.569 |
| target_soc_end_lap | 0.331 |
| torque_bias | 0.0225 |
| mguh_power_kw | 94.16 |

Notes:
- map: STANDARD
- heat_scale: 0.939
- cooling_target: 0.432
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 281.7 |
| torque_ramp | 0.8371 |
| deployment_style | aggressive |
| cooling_share | 0.382 |
| ers_output_kw | 171.51 |
| deploy_mj_per_lap | 3.712 |
| harvest_mj_per_lap | 0.908 |
| mguh_direct_ratio | 0.629 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0625 |
| mguh_power_kw | 98.87 |

Notes:
- map: RICH
- heat_scale: 0.939
- cooling_target: 0.382
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 309.87 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 194.38 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.582 |
| mguh_direct_ratio | 0.689 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1025 |
| mguh_power_kw | 103.58 |

Notes:
- map: QUALY
- heat_scale: 0.939
- cooling_target: 0.35
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 225.36 |
| torque_ramp | 0.5371 |
| deployment_style | wet_grip |
| cooling_share | 0.532 |
| ers_output_kw | 108.63 |
| deploy_mj_per_lap | 2.366 |
| harvest_mj_per_lap | 1.451 |
| mguh_direct_ratio | 0.519 |
| target_soc_end_lap | 0.563 |
| torque_bias | 0.0025 |
| mguh_power_kw | 84.74 |

Notes:
- map: WET
- heat_scale: 0.939
- cooling_target: 0.532
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 215.97 |
| torque_ramp | 0.4271 |
| deployment_style | harvest |
| cooling_share | 0.582 |
| ers_output_kw | 80.04 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.389 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0375 |
| mguh_power_kw | 75.33 |

Notes:
- map: RECHARGE
- heat_scale: 0.939
- cooling_target: 0.582
- torque_bias_delta: 0.0225
- drs_ratio: 0.196
- deploy_dynamic: 1.011
- harvest_dynamic: 0.776
- deploy_limit_hit: False
- harvest_limit_hit: True
