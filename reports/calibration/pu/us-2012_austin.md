# PowerUnit calibration – us-2012_austin

## Track stats
- heat_mean: 0.794
- heat_peak: 1.500
- drs_ratio: 0.538
- brake_density (MJ/km): 2.056
- power_bias: 0.661
- circuit_length_km: 5.457

## Regen profile
- base_factor: 0.839
- limit_nm: 352.0
- potential_mj_per_lap: 1.081
- regen_migration_bias: -0.258
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.184}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.898 | 1.578 | 0.752 | 0.474 | 0.789 |
| STANDARD | 3.045 | 1.336 | 0.344 | 0.761 | 0.668 |
| RICH | 3.727 | 0.977 | 0.05 | 0.932 | 0.488 |
| QUALY | 4.0 | 0.626 | 0.05 | 1.0 | 0.313 |
| WET | 2.375 | 1.561 | 0.578 | 0.594 | 0.78 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.31)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 217.48 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.509 |
| ers_output_kw | 105.3 |
| deploy_mj_per_lap | 1.898 |
| harvest_mj_per_lap | 1.578 |
| mguh_direct_ratio | 0.581 |
| target_soc_end_lap | 0.752 |
| torque_bias | -0.0339 |
| mguh_power_kw | 90.71 |

Notes:
- map: ECONOMY
- heat_scale: 0.989
- cooling_target: 0.509
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 257.02 |
| torque_ramp | 0.6193 |
| deployment_style | balanced |
| cooling_share | 0.459 |
| ers_output_kw | 157.95 |
| deploy_mj_per_lap | 3.045 |
| harvest_mj_per_lap | 1.336 |
| mguh_direct_ratio | 0.621 |
| target_soc_end_lap | 0.344 |
| torque_bias | 0.0161 |
| mguh_power_kw | 98.59 |

Notes:
- map: STANDARD
- heat_scale: 0.989
- cooling_target: 0.459
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 296.56 |
| torque_ramp | 0.8293 |
| deployment_style | aggressive |
| cooling_share | 0.409 |
| ers_output_kw | 197.44 |
| deploy_mj_per_lap | 3.727 |
| harvest_mj_per_lap | 0.977 |
| mguh_direct_ratio | 0.681 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0561 |
| mguh_power_kw | 103.52 |

Notes:
- map: RICH
- heat_scale: 0.989
- cooling_target: 0.409
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 326.21 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.359 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.626 |
| mguh_direct_ratio | 0.741 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0961 |
| mguh_power_kw | 108.45 |

Notes:
- map: QUALY
- heat_scale: 0.989
- cooling_target: 0.359
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 237.25 |
| torque_ramp | 0.5293 |
| deployment_style | wet_grip |
| cooling_share | 0.559 |
| ers_output_kw | 125.05 |
| deploy_mj_per_lap | 2.375 |
| harvest_mj_per_lap | 1.561 |
| mguh_direct_ratio | 0.571 |
| target_soc_end_lap | 0.578 |
| torque_bias | -0.0039 |
| mguh_power_kw | 88.73 |

Notes:
- map: WET
- heat_scale: 0.989
- cooling_target: 0.559
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 227.36 |
| torque_ramp | 0.4193 |
| deployment_style | harvest |
| cooling_share | 0.609 |
| ers_output_kw | 92.14 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.441 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0439 |
| mguh_power_kw | 78.87 |

Notes:
- map: RECHARGE
- heat_scale: 0.989
- cooling_target: 0.609
- torque_bias_delta: 0.0161
- drs_ratio: 0.538
- deploy_dynamic: 1.015
- harvest_dynamic: 0.835
- deploy_limit_hit: False
- harvest_limit_hit: True
