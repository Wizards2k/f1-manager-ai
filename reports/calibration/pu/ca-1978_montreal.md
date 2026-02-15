# PowerUnit calibration – ca-1978_montreal

## Track stats
- heat_mean: 0.680
- heat_peak: 1.500
- drs_ratio: 0.492
- brake_density (MJ/km): 2.537
- power_bias: 0.789
- circuit_length_km: 4.274

## Regen profile
- base_factor: 0.852
- limit_nm: 368.8
- potential_mj_per_lap: 0.927
- regen_migration_bias: -0.236
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.312}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.939 | 1.682 | 0.761 | 0.485 | 0.841 |
| STANDARD | 3.111 | 1.424 | 0.347 | 0.778 | 0.712 |
| RICH | 3.808 | 1.041 | 0.05 | 0.952 | 0.52 |
| QUALY | 4.0 | 0.667 | 0.05 | 1.0 | 0.334 |
| WET | 2.427 | 1.664 | 0.586 | 0.607 | 0.832 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 95% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 211.2 |
| torque_ramp | 0.3547 |
| deployment_style | conservative |
| cooling_share | 0.486 |
| ers_output_kw | 105.04 |
| deploy_mj_per_lap | 1.939 |
| harvest_mj_per_lap | 1.682 |
| mguh_direct_ratio | 0.574 |
| target_soc_end_lap | 0.761 |
| torque_bias | -0.0211 |
| mguh_power_kw | 106.42 |

Notes:
- map: ECONOMY
- heat_scale: 0.96
- cooling_target: 0.486
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 249.6 |
| torque_ramp | 0.6347 |
| deployment_style | balanced |
| cooling_share | 0.436 |
| ers_output_kw | 157.55 |
| deploy_mj_per_lap | 3.111 |
| harvest_mj_per_lap | 1.424 |
| mguh_direct_ratio | 0.614 |
| target_soc_end_lap | 0.347 |
| torque_bias | 0.0289 |
| mguh_power_kw | 115.68 |

Notes:
- map: STANDARD
- heat_scale: 0.96
- cooling_target: 0.436
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 288.0 |
| torque_ramp | 0.8447 |
| deployment_style | aggressive |
| cooling_share | 0.386 |
| ers_output_kw | 196.94 |
| deploy_mj_per_lap | 3.808 |
| harvest_mj_per_lap | 1.041 |
| mguh_direct_ratio | 0.674 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0689 |
| mguh_power_kw | 120.0 |

Notes:
- map: RICH
- heat_scale: 0.96
- cooling_target: 0.386
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 316.8 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.667 |
| mguh_direct_ratio | 0.734 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1089 |
| mguh_power_kw | 120.0 |

Notes:
- map: QUALY
- heat_scale: 0.96
- cooling_target: 0.35
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 230.4 |
| torque_ramp | 0.5447 |
| deployment_style | wet_grip |
| cooling_share | 0.536 |
| ers_output_kw | 124.73 |
| deploy_mj_per_lap | 2.427 |
| harvest_mj_per_lap | 1.664 |
| mguh_direct_ratio | 0.564 |
| target_soc_end_lap | 0.586 |
| torque_bias | 0.0089 |
| mguh_power_kw | 104.11 |

Notes:
- map: WET
- heat_scale: 0.96
- cooling_target: 0.536
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.8 |
| torque_ramp | 0.4347 |
| deployment_style | harvest |
| cooling_share | 0.586 |
| ers_output_kw | 91.91 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.434 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0311 |
| mguh_power_kw | 92.54 |

Notes:
- map: RECHARGE
- heat_scale: 0.96
- cooling_target: 0.586
- torque_bias_delta: 0.0289
- drs_ratio: 0.492
- deploy_dynamic: 1.037
- harvest_dynamic: 0.89
- deploy_limit_hit: False
- harvest_limit_hit: True
