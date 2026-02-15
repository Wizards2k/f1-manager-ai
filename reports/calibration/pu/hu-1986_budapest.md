# PowerUnit calibration – hu-1986_budapest

## Track stats
- heat_mean: 0.742
- heat_peak: 1.300
- drs_ratio: 0.299
- brake_density (MJ/km): 2.444
- power_bias: 0.620
- circuit_length_km: 4.349

## Regen profile
- base_factor: 0.85
- limit_nm: 365.5
- potential_mj_per_lap: 0.73
- regen_migration_bias: -0.24
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.666}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.852 | 1.662 | 0.771 | 0.463 | 0.831 |
| STANDARD | 2.972 | 1.407 | 0.365 | 0.743 | 0.704 |
| RICH | 3.637 | 1.029 | 0.059 | 0.909 | 0.514 |
| QUALY | 4.0 | 0.659 | 0.05 | 1.0 | 0.33 |
| WET | 2.318 | 1.644 | 0.599 | 0.58 | 0.822 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.06) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 211.1 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.498 |
| ers_output_kw | 97.79 |
| deploy_mj_per_lap | 1.852 |
| harvest_mj_per_lap | 1.662 |
| mguh_direct_ratio | 0.545 |
| target_soc_end_lap | 0.771 |
| torque_bias | -0.038 |
| mguh_power_kw | 91.33 |

Notes:
- map: ECONOMY
- heat_scale: 0.96
- cooling_target: 0.498
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 249.48 |
| torque_ramp | 0.6144 |
| deployment_style | balanced |
| cooling_share | 0.448 |
| ers_output_kw | 146.69 |
| deploy_mj_per_lap | 2.972 |
| harvest_mj_per_lap | 1.407 |
| mguh_direct_ratio | 0.585 |
| target_soc_end_lap | 0.365 |
| torque_bias | 0.012 |
| mguh_power_kw | 99.28 |

Notes:
- map: STANDARD
- heat_scale: 0.96
- cooling_target: 0.448
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 287.86 |
| torque_ramp | 0.8244 |
| deployment_style | aggressive |
| cooling_share | 0.398 |
| ers_output_kw | 183.36 |
| deploy_mj_per_lap | 3.637 |
| harvest_mj_per_lap | 1.029 |
| mguh_direct_ratio | 0.645 |
| target_soc_end_lap | 0.059 |
| torque_bias | 0.052 |
| mguh_power_kw | 104.24 |

Notes:
- map: RICH
- heat_scale: 0.96
- cooling_target: 0.398
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 316.64 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.659 |
| mguh_direct_ratio | 0.705 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.092 |
| mguh_power_kw | 109.2 |

Notes:
- map: QUALY
- heat_scale: 0.96
- cooling_target: 0.35
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 230.29 |
| torque_ramp | 0.5244 |
| deployment_style | wet_grip |
| cooling_share | 0.548 |
| ers_output_kw | 116.13 |
| deploy_mj_per_lap | 2.318 |
| harvest_mj_per_lap | 1.644 |
| mguh_direct_ratio | 0.535 |
| target_soc_end_lap | 0.599 |
| torque_bias | -0.008 |
| mguh_power_kw | 89.35 |

Notes:
- map: WET
- heat_scale: 0.96
- cooling_target: 0.548
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.69 |
| torque_ramp | 0.4144 |
| deployment_style | harvest |
| cooling_share | 0.598 |
| ers_output_kw | 85.57 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.405 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.048 |
| mguh_power_kw | 79.42 |

Notes:
- map: RECHARGE
- heat_scale: 0.96
- cooling_target: 0.598
- torque_bias_delta: 0.012
- drs_ratio: 0.299
- deploy_dynamic: 0.991
- harvest_dynamic: 0.879
- deploy_limit_hit: False
- harvest_limit_hit: True
