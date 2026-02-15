# PowerUnit calibration – cn-2004_shanghai

## Track stats
- heat_mean: 0.782
- heat_peak: 1.500
- drs_ratio: 0.427
- brake_density (MJ/km): 2.488
- power_bias: 0.575
- circuit_length_km: 5.367

## Regen profile
- base_factor: 0.851
- limit_nm: 367.1
- potential_mj_per_lap: 1.265
- regen_migration_bias: -0.238
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.931}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.838 | 1.671 | 0.775 | 0.46 | 0.836 |
| STANDARD | 2.949 | 1.415 | 0.37 | 0.737 | 0.708 |
| RICH | 3.609 | 1.035 | 0.064 | 0.902 | 0.517 |
| QUALY | 4.0 | 0.663 | 0.05 | 1.0 | 0.332 |
| WET | 2.3 | 1.654 | 0.603 | 0.575 | 0.827 |
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
| heat_load_kw | 216.83 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.506 |
| ers_output_kw | 102.54 |
| deploy_mj_per_lap | 1.838 |
| harvest_mj_per_lap | 1.671 |
| mguh_direct_ratio | 0.51 |
| target_soc_end_lap | 0.775 |
| torque_bias | -0.0425 |
| mguh_power_kw | 55.96 |

Notes:
- map: ECONOMY
- heat_scale: 0.986
- cooling_target: 0.506
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 256.25 |
| torque_ramp | 0.609 |
| deployment_style | balanced |
| cooling_share | 0.456 |
| ers_output_kw | 153.81 |
| deploy_mj_per_lap | 2.949 |
| harvest_mj_per_lap | 1.415 |
| mguh_direct_ratio | 0.55 |
| target_soc_end_lap | 0.37 |
| torque_bias | 0.0075 |
| mguh_power_kw | 60.83 |

Notes:
- map: STANDARD
- heat_scale: 0.986
- cooling_target: 0.456
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 295.68 |
| torque_ramp | 0.819 |
| deployment_style | aggressive |
| cooling_share | 0.406 |
| ers_output_kw | 192.26 |
| deploy_mj_per_lap | 3.609 |
| harvest_mj_per_lap | 1.035 |
| mguh_direct_ratio | 0.61 |
| target_soc_end_lap | 0.064 |
| torque_bias | 0.0475 |
| mguh_power_kw | 63.87 |

Notes:
- map: RICH
- heat_scale: 0.986
- cooling_target: 0.406
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 325.24 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.356 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.663 |
| mguh_direct_ratio | 0.67 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0875 |
| mguh_power_kw | 66.91 |

Notes:
- map: QUALY
- heat_scale: 0.986
- cooling_target: 0.356
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 236.54 |
| torque_ramp | 0.519 |
| deployment_style | wet_grip |
| cooling_share | 0.556 |
| ers_output_kw | 121.76 |
| deploy_mj_per_lap | 2.3 |
| harvest_mj_per_lap | 1.654 |
| mguh_direct_ratio | 0.5 |
| target_soc_end_lap | 0.603 |
| torque_bias | -0.0125 |
| mguh_power_kw | 54.74 |

Notes:
- map: WET
- heat_scale: 0.986
- cooling_target: 0.556
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 226.69 |
| torque_ramp | 0.409 |
| deployment_style | harvest |
| cooling_share | 0.606 |
| ers_output_kw | 89.72 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.37 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0525 |
| mguh_power_kw | 48.66 |

Notes:
- map: RECHARGE
- heat_scale: 0.986
- cooling_target: 0.606
- torque_bias_delta: 0.0075
- drs_ratio: 0.427
- deploy_dynamic: 0.983
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: True
