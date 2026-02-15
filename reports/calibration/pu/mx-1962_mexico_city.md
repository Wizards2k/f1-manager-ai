# PowerUnit calibration – mx-1962_mexico_city

## Track stats
- heat_mean: 0.723
- heat_peak: 1.300
- drs_ratio: 0.531
- brake_density (MJ/km): 2.434
- power_bias: 0.753
- circuit_length_km: 4.244

## Regen profile
- base_factor: 0.85
- limit_nm: 365.2
- potential_mj_per_lap: 1.012
- regen_migration_bias: -0.241
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.142}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.932 | 1.66 | 0.759 | 0.483 | 0.83 |
| STANDARD | 3.099 | 1.405 | 0.346 | 0.775 | 0.703 |
| RICH | 3.793 | 1.027 | 0.05 | 0.948 | 0.513 |
| QUALY | 4.0 | 0.659 | 0.05 | 1.0 | 0.33 |
| WET | 2.417 | 1.642 | 0.584 | 0.604 | 0.821 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 210.05 |
| torque_ramp | 0.3503 |
| deployment_style | conservative |
| cooling_share | 0.495 |
| ers_output_kw | 106.11 |
| deploy_mj_per_lap | 1.932 |
| harvest_mj_per_lap | 1.66 |
| mguh_direct_ratio | 0.58 |
| target_soc_end_lap | 0.759 |
| torque_bias | -0.0247 |
| mguh_power_kw | 98.01 |

Notes:
- map: ECONOMY
- heat_scale: 0.955
- cooling_target: 0.495
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 248.24 |
| torque_ramp | 0.6303 |
| deployment_style | balanced |
| cooling_share | 0.445 |
| ers_output_kw | 159.17 |
| deploy_mj_per_lap | 3.099 |
| harvest_mj_per_lap | 1.405 |
| mguh_direct_ratio | 0.62 |
| target_soc_end_lap | 0.346 |
| torque_bias | 0.0253 |
| mguh_power_kw | 106.53 |

Notes:
- map: STANDARD
- heat_scale: 0.955
- cooling_target: 0.445
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 286.43 |
| torque_ramp | 0.8403 |
| deployment_style | aggressive |
| cooling_share | 0.395 |
| ers_output_kw | 198.96 |
| deploy_mj_per_lap | 3.793 |
| harvest_mj_per_lap | 1.027 |
| mguh_direct_ratio | 0.68 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0653 |
| mguh_power_kw | 111.86 |

Notes:
- map: RICH
- heat_scale: 0.955
- cooling_target: 0.395
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 315.07 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.659 |
| mguh_direct_ratio | 0.74 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1053 |
| mguh_power_kw | 117.18 |

Notes:
- map: QUALY
- heat_scale: 0.955
- cooling_target: 0.35
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 229.14 |
| torque_ramp | 0.5403 |
| deployment_style | wet_grip |
| cooling_share | 0.545 |
| ers_output_kw | 126.01 |
| deploy_mj_per_lap | 2.417 |
| harvest_mj_per_lap | 1.642 |
| mguh_direct_ratio | 0.57 |
| target_soc_end_lap | 0.584 |
| torque_bias | 0.0053 |
| mguh_power_kw | 95.88 |

Notes:
- map: WET
- heat_scale: 0.955
- cooling_target: 0.545
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 219.6 |
| torque_ramp | 0.4303 |
| deployment_style | harvest |
| cooling_share | 0.595 |
| ers_output_kw | 92.85 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.44 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0347 |
| mguh_power_kw | 85.22 |

Notes:
- map: RECHARGE
- heat_scale: 0.955
- cooling_target: 0.595
- torque_bias_delta: 0.0253
- drs_ratio: 0.531
- deploy_dynamic: 1.033
- harvest_dynamic: 0.878
- deploy_limit_hit: False
- harvest_limit_hit: True
