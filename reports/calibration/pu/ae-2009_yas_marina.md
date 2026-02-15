# PowerUnit calibration – ae-2009_yas_marina

## Track stats
- heat_mean: 0.746
- heat_peak: 1.500
- drs_ratio: 0.366
- brake_density (MJ/km): 2.167
- power_bias: 0.814
- circuit_length_km: 5.250

## Regen profile
- base_factor: 0.842
- limit_nm: 355.8
- potential_mj_per_lap: 1.378
- regen_migration_bias: -0.253
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.364}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.98 | 1.602 | 0.743 | 0.495 | 0.801 |
| STANDARD | 3.177 | 1.356 | 0.327 | 0.794 | 0.678 |
| RICH | 3.889 | 0.992 | 0.05 | 0.972 | 0.496 |
| QUALY | 4.0 | 0.636 | 0.05 | 1.0 | 0.318 |
| WET | 2.478 | 1.585 | 0.566 | 0.62 | 0.792 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 97% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.32)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 214.84 |
| torque_ramp | 0.3577 |
| deployment_style | conservative |
| cooling_share | 0.499 |
| ers_output_kw | 99.4 |
| deploy_mj_per_lap | 1.98 |
| harvest_mj_per_lap | 1.602 |
| mguh_direct_ratio | 0.555 |
| target_soc_end_lap | 0.743 |
| torque_bias | -0.0186 |
| mguh_power_kw | 83.93 |

Notes:
- map: ECONOMY
- heat_scale: 0.977
- cooling_target: 0.499
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 253.9 |
| torque_ramp | 0.6377 |
| deployment_style | balanced |
| cooling_share | 0.449 |
| ers_output_kw | 149.1 |
| deploy_mj_per_lap | 3.177 |
| harvest_mj_per_lap | 1.356 |
| mguh_direct_ratio | 0.595 |
| target_soc_end_lap | 0.327 |
| torque_bias | 0.0314 |
| mguh_power_kw | 91.23 |

Notes:
- map: STANDARD
- heat_scale: 0.977
- cooling_target: 0.449
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 292.96 |
| torque_ramp | 0.8477 |
| deployment_style | aggressive |
| cooling_share | 0.399 |
| ers_output_kw | 186.38 |
| deploy_mj_per_lap | 3.889 |
| harvest_mj_per_lap | 0.992 |
| mguh_direct_ratio | 0.655 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0714 |
| mguh_power_kw | 95.79 |

Notes:
- map: RICH
- heat_scale: 0.977
- cooling_target: 0.399
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 322.26 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.636 |
| mguh_direct_ratio | 0.715 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1114 |
| mguh_power_kw | 100.36 |

Notes:
- map: QUALY
- heat_scale: 0.977
- cooling_target: 0.35
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 234.37 |
| torque_ramp | 0.5477 |
| deployment_style | wet_grip |
| cooling_share | 0.549 |
| ers_output_kw | 118.04 |
| deploy_mj_per_lap | 2.478 |
| harvest_mj_per_lap | 1.585 |
| mguh_direct_ratio | 0.545 |
| target_soc_end_lap | 0.566 |
| torque_bias | 0.0114 |
| mguh_power_kw | 82.11 |

Notes:
- map: WET
- heat_scale: 0.977
- cooling_target: 0.549
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 224.6 |
| torque_ramp | 0.4377 |
| deployment_style | harvest |
| cooling_share | 0.599 |
| ers_output_kw | 86.98 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.415 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0286 |
| mguh_power_kw | 72.99 |

Notes:
- map: RECHARGE
- heat_scale: 0.977
- cooling_target: 0.599
- torque_bias_delta: 0.0314
- drs_ratio: 0.366
- deploy_dynamic: 1.059
- harvest_dynamic: 0.848
- deploy_limit_hit: False
- harvest_limit_hit: True
