# PowerUnit calibration – sg-2008_singapore

## Track stats
- heat_mean: 0.737
- heat_peak: 1.300
- drs_ratio: 0.344
- brake_density (MJ/km): 2.358
- power_bias: 0.776
- circuit_length_km: 4.887

## Regen profile
- base_factor: 0.847
- limit_nm: 362.5
- potential_mj_per_lap: 0.889
- regen_migration_bias: -0.244
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.733}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.952 | 1.643 | 0.754 | 0.488 | 0.822 |
| STANDARD | 3.132 | 1.391 | 0.339 | 0.783 | 0.696 |
| RICH | 3.833 | 1.017 | 0.05 | 0.958 | 0.508 |
| QUALY | 4.0 | 0.652 | 0.05 | 1.0 | 0.326 |
| WET | 2.443 | 1.626 | 0.577 | 0.611 | 0.813 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 96% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 210.81 |
| torque_ramp | 0.3531 |
| deployment_style | conservative |
| cooling_share | 0.497 |
| ers_output_kw | 99.17 |
| deploy_mj_per_lap | 1.952 |
| harvest_mj_per_lap | 1.643 |
| mguh_direct_ratio | 0.552 |
| target_soc_end_lap | 0.754 |
| torque_bias | -0.0224 |
| mguh_power_kw | 74.59 |

Notes:
- map: ECONOMY
- heat_scale: 0.958
- cooling_target: 0.497
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 249.13 |
| torque_ramp | 0.6331 |
| deployment_style | balanced |
| cooling_share | 0.447 |
| ers_output_kw | 148.75 |
| deploy_mj_per_lap | 3.132 |
| harvest_mj_per_lap | 1.391 |
| mguh_direct_ratio | 0.592 |
| target_soc_end_lap | 0.339 |
| torque_bias | 0.0276 |
| mguh_power_kw | 81.07 |

Notes:
- map: STANDARD
- heat_scale: 0.958
- cooling_target: 0.447
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 287.46 |
| torque_ramp | 0.8431 |
| deployment_style | aggressive |
| cooling_share | 0.397 |
| ers_output_kw | 185.94 |
| deploy_mj_per_lap | 3.833 |
| harvest_mj_per_lap | 1.017 |
| mguh_direct_ratio | 0.652 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0676 |
| mguh_power_kw | 85.13 |

Notes:
- map: RICH
- heat_scale: 0.958
- cooling_target: 0.397
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 316.21 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.652 |
| mguh_direct_ratio | 0.712 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1076 |
| mguh_power_kw | 89.18 |

Notes:
- map: QUALY
- heat_scale: 0.958
- cooling_target: 0.35
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 229.97 |
| torque_ramp | 0.5431 |
| deployment_style | wet_grip |
| cooling_share | 0.547 |
| ers_output_kw | 117.76 |
| deploy_mj_per_lap | 2.443 |
| harvest_mj_per_lap | 1.626 |
| mguh_direct_ratio | 0.542 |
| target_soc_end_lap | 0.577 |
| torque_bias | 0.0076 |
| mguh_power_kw | 72.97 |

Notes:
- map: WET
- heat_scale: 0.958
- cooling_target: 0.547
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.39 |
| torque_ramp | 0.4331 |
| deployment_style | harvest |
| cooling_share | 0.597 |
| ers_output_kw | 86.77 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.412 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0324 |
| mguh_power_kw | 64.86 |

Notes:
- map: RECHARGE
- heat_scale: 0.958
- cooling_target: 0.597
- torque_bias_delta: 0.0276
- drs_ratio: 0.344
- deploy_dynamic: 1.044
- harvest_dynamic: 0.87
- deploy_limit_hit: False
- harvest_limit_hit: True
