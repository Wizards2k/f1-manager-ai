# PowerUnit calibration – be-1925_spa_francorchamps

## Track stats
- heat_mean: 0.720
- heat_peak: 1.300
- drs_ratio: 0.328
- brake_density (MJ/km): 1.240
- power_bias: 0.681
- circuit_length_km: 6.942

## Regen profile
- base_factor: 0.815
- limit_nm: 323.4
- potential_mj_per_lap: 1.195
- regen_migration_bias: -0.295
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.692}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.884 | 1.436 | 0.733 | 0.471 | 0.718 |
| STANDARD | 3.023 | 1.216 | 0.329 | 0.756 | 0.608 |
| RICH | 3.7 | 0.889 | 0.05 | 0.925 | 0.445 |
| QUALY | 4.0 | 0.57 | 0.05 | 1.0 | 0.285 |
| WET | 2.358 | 1.421 | 0.56 | 0.59 | 0.711 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.28)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 209.88 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.494 |
| ers_output_kw | 95.38 |
| deploy_mj_per_lap | 1.884 |
| harvest_mj_per_lap | 1.436 |
| mguh_direct_ratio | 0.549 |
| target_soc_end_lap | 0.733 |
| torque_bias | -0.0319 |
| mguh_power_kw | 100.11 |

Notes:
- map: ECONOMY
- heat_scale: 0.954
- cooling_target: 0.494
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 248.04 |
| torque_ramp | 0.6218 |
| deployment_style | balanced |
| cooling_share | 0.444 |
| ers_output_kw | 143.07 |
| deploy_mj_per_lap | 3.023 |
| harvest_mj_per_lap | 1.216 |
| mguh_direct_ratio | 0.589 |
| target_soc_end_lap | 0.329 |
| torque_bias | 0.0181 |
| mguh_power_kw | 108.81 |

Notes:
- map: STANDARD
- heat_scale: 0.954
- cooling_target: 0.444
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 286.2 |
| torque_ramp | 0.8318 |
| deployment_style | aggressive |
| cooling_share | 0.394 |
| ers_output_kw | 178.84 |
| deploy_mj_per_lap | 3.7 |
| harvest_mj_per_lap | 0.889 |
| mguh_direct_ratio | 0.649 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0581 |
| mguh_power_kw | 114.25 |

Notes:
- map: RICH
- heat_scale: 0.954
- cooling_target: 0.394
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 314.82 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.57 |
| mguh_direct_ratio | 0.709 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0981 |
| mguh_power_kw | 119.7 |

Notes:
- map: QUALY
- heat_scale: 0.954
- cooling_target: 0.35
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 228.96 |
| torque_ramp | 0.5318 |
| deployment_style | wet_grip |
| cooling_share | 0.544 |
| ers_output_kw | 113.27 |
| deploy_mj_per_lap | 2.358 |
| harvest_mj_per_lap | 1.421 |
| mguh_direct_ratio | 0.539 |
| target_soc_end_lap | 0.56 |
| torque_bias | -0.0019 |
| mguh_power_kw | 97.93 |

Notes:
- map: WET
- heat_scale: 0.954
- cooling_target: 0.544
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 219.42 |
| torque_ramp | 0.4218 |
| deployment_style | harvest |
| cooling_share | 0.594 |
| ers_output_kw | 83.46 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.409 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0419 |
| mguh_power_kw | 87.05 |

Notes:
- map: RECHARGE
- heat_scale: 0.954
- cooling_target: 0.594
- torque_bias_delta: 0.0181
- drs_ratio: 0.328
- deploy_dynamic: 1.008
- harvest_dynamic: 0.76
- deploy_limit_hit: False
- harvest_limit_hit: True
