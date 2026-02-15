# PowerUnit calibration – it-1953_imola

## Track stats
- heat_mean: 0.835
- heat_peak: 1.500
- drs_ratio: 0.132
- brake_density (MJ/km): 2.331
- power_bias: 0.212
- circuit_length_km: 4.876

## Regen profile
- base_factor: 0.847
- limit_nm: 361.6
- potential_mj_per_lap: 0.723
- regen_migration_bias: -0.245
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.392}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.62 | 1.637 | 0.803 | 0.405 | 0.819 |
| STANDARD | 2.599 | 1.386 | 0.418 | 0.65 | 0.693 |
| RICH | 3.181 | 1.014 | 0.125 | 0.795 | 0.507 |
| QUALY | 3.885 | 0.65 | 0.05 | 0.971 | 0.325 |
| WET | 2.027 | 1.62 | 0.639 | 0.507 | 0.81 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.12) – plan recharge lap
- QUALY: deploy at 97% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 219.71 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.517 |
| ers_output_kw | 91.47 |
| deploy_mj_per_lap | 1.62 |
| harvest_mj_per_lap | 1.637 |
| mguh_direct_ratio | 0.137 |
| target_soc_end_lap | 0.803 |
| torque_bias | -0.0788 |
| mguh_power_kw | 29.94 |

Notes:
- map: ECONOMY
- heat_scale: 0.999
- cooling_target: 0.517
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 259.66 |
| torque_ramp | 0.5655 |
| deployment_style | balanced |
| cooling_share | 0.467 |
| ers_output_kw | 137.21 |
| deploy_mj_per_lap | 2.599 |
| harvest_mj_per_lap | 1.386 |
| mguh_direct_ratio | 0.177 |
| target_soc_end_lap | 0.418 |
| torque_bias | -0.0288 |
| mguh_power_kw | 32.55 |

Notes:
- map: STANDARD
- heat_scale: 0.999
- cooling_target: 0.467
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 299.61 |
| torque_ramp | 0.7755 |
| deployment_style | aggressive |
| cooling_share | 0.417 |
| ers_output_kw | 171.51 |
| deploy_mj_per_lap | 3.181 |
| harvest_mj_per_lap | 1.014 |
| mguh_direct_ratio | 0.237 |
| target_soc_end_lap | 0.125 |
| torque_bias | 0.0112 |
| mguh_power_kw | 34.17 |

Notes:
- map: RICH
- heat_scale: 0.999
- cooling_target: 0.417
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 329.57 |
| torque_ramp | 0.9855 |
| deployment_style | time_attack |
| cooling_share | 0.367 |
| ers_output_kw | 194.38 |
| deploy_mj_per_lap | 3.885 |
| harvest_mj_per_lap | 0.65 |
| mguh_direct_ratio | 0.297 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0512 |
| mguh_power_kw | 35.8 |

Notes:
- map: QUALY
- heat_scale: 0.999
- cooling_target: 0.367
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 239.69 |
| torque_ramp | 0.4755 |
| deployment_style | wet_grip |
| cooling_share | 0.567 |
| ers_output_kw | 108.62 |
| deploy_mj_per_lap | 2.027 |
| harvest_mj_per_lap | 1.62 |
| mguh_direct_ratio | 0.127 |
| target_soc_end_lap | 0.639 |
| torque_bias | -0.0488 |
| mguh_power_kw | 29.29 |

Notes:
- map: WET
- heat_scale: 0.999
- cooling_target: 0.567
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 229.7 |
| torque_ramp | 0.3655 |
| deployment_style | harvest |
| cooling_share | 0.617 |
| ers_output_kw | 80.04 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.05 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0888 |
| mguh_power_kw | 26.04 |

Notes:
- map: RECHARGE
- heat_scale: 0.999
- cooling_target: 0.617
- torque_bias_delta: -0.0288
- drs_ratio: 0.132
- deploy_dynamic: 0.866
- harvest_dynamic: 0.866
- deploy_limit_hit: False
- harvest_limit_hit: True
