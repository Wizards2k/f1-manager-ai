# PowerUnit calibration – au-1953_melbourne

## Track stats
- heat_mean: 0.729
- heat_peak: 1.500
- drs_ratio: 0.189
- brake_density (MJ/km): 1.649
- power_bias: 0.671
- circuit_length_km: 5.222

## Regen profile
- base_factor: 0.827
- limit_nm: 337.7
- potential_mj_per_lap: 0.963
- regen_migration_bias: -0.277
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.805}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.88 | 1.49 | 0.741 | 0.47 | 0.745 |
| STANDARD | 3.017 | 1.261 | 0.337 | 0.754 | 0.63 |
| RICH | 3.692 | 0.922 | 0.05 | 0.923 | 0.461 |
| QUALY | 4.0 | 0.591 | 0.05 | 1.0 | 0.295 |
| WET | 2.353 | 1.474 | 0.568 | 0.588 | 0.737 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.30)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 213.87 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.496 |
| ers_output_kw | 91.55 |
| deploy_mj_per_lap | 1.88 |
| harvest_mj_per_lap | 1.49 |
| mguh_direct_ratio | 0.528 |
| target_soc_end_lap | 0.741 |
| torque_bias | -0.0329 |
| mguh_power_kw | 79.33 |

Notes:
- map: ECONOMY
- heat_scale: 0.972
- cooling_target: 0.496
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 252.76 |
| torque_ramp | 0.6205 |
| deployment_style | balanced |
| cooling_share | 0.446 |
| ers_output_kw | 137.33 |
| deploy_mj_per_lap | 3.017 |
| harvest_mj_per_lap | 1.261 |
| mguh_direct_ratio | 0.568 |
| target_soc_end_lap | 0.337 |
| torque_bias | 0.0171 |
| mguh_power_kw | 86.22 |

Notes:
- map: STANDARD
- heat_scale: 0.972
- cooling_target: 0.446
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 291.64 |
| torque_ramp | 0.8305 |
| deployment_style | aggressive |
| cooling_share | 0.396 |
| ers_output_kw | 171.66 |
| deploy_mj_per_lap | 3.692 |
| harvest_mj_per_lap | 0.922 |
| mguh_direct_ratio | 0.628 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0571 |
| mguh_power_kw | 90.53 |

Notes:
- map: RICH
- heat_scale: 0.972
- cooling_target: 0.396
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 320.81 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 194.55 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.591 |
| mguh_direct_ratio | 0.688 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0971 |
| mguh_power_kw | 94.85 |

Notes:
- map: QUALY
- heat_scale: 0.972
- cooling_target: 0.35
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 233.31 |
| torque_ramp | 0.5305 |
| deployment_style | wet_grip |
| cooling_share | 0.546 |
| ers_output_kw | 108.72 |
| deploy_mj_per_lap | 2.353 |
| harvest_mj_per_lap | 1.474 |
| mguh_direct_ratio | 0.518 |
| target_soc_end_lap | 0.568 |
| torque_bias | -0.0029 |
| mguh_power_kw | 77.6 |

Notes:
- map: WET
- heat_scale: 0.972
- cooling_target: 0.546
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 223.59 |
| torque_ramp | 0.4205 |
| deployment_style | harvest |
| cooling_share | 0.596 |
| ers_output_kw | 80.11 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.388 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0429 |
| mguh_power_kw | 68.98 |

Notes:
- map: RECHARGE
- heat_scale: 0.972
- cooling_target: 0.596
- torque_bias_delta: 0.0171
- drs_ratio: 0.189
- deploy_dynamic: 1.006
- harvest_dynamic: 0.788
- deploy_limit_hit: False
- harvest_limit_hit: True
