# PowerUnit calibration – qa-2004_lusail

## Track stats
- heat_mean: 0.792
- heat_peak: 1.500
- drs_ratio: 0.640
- brake_density (MJ/km): 1.871
- power_bias: 0.896
- circuit_length_km: 5.375

## Regen profile
- base_factor: 0.833
- limit_nm: 345.5
- potential_mj_per_lap: 1.247
- regen_migration_bias: -0.266
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.312}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 2.051 | 1.538 | 0.723 | 0.513 | 0.769 |
| STANDARD | 3.291 | 1.302 | 0.302 | 0.823 | 0.651 |
| RICH | 4.0 | 0.952 | 0.05 | 1.0 | 0.476 |
| QUALY | 4.0 | 0.61 | 0.05 | 1.0 | 0.305 |
| WET | 2.567 | 1.522 | 0.543 | 0.642 | 0.761 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 100% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.30)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 217.38 |
| torque_ramp | 0.3675 |
| deployment_style | conservative |
| cooling_share | 0.508 |
| ers_output_kw | 108.42 |
| deploy_mj_per_lap | 2.051 |
| harvest_mj_per_lap | 1.538 |
| mguh_direct_ratio | 0.596 |
| target_soc_end_lap | 0.723 |
| torque_bias | -0.0104 |
| mguh_power_kw | 80.04 |

Notes:
- map: ECONOMY
- heat_scale: 0.988
- cooling_target: 0.508
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 256.9 |
| torque_ramp | 0.6475 |
| deployment_style | balanced |
| cooling_share | 0.458 |
| ers_output_kw | 162.63 |
| deploy_mj_per_lap | 3.291 |
| harvest_mj_per_lap | 1.302 |
| mguh_direct_ratio | 0.636 |
| target_soc_end_lap | 0.302 |
| torque_bias | 0.0396 |
| mguh_power_kw | 87.0 |

Notes:
- map: STANDARD
- heat_scale: 0.988
- cooling_target: 0.458
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 296.42 |
| torque_ramp | 0.8575 |
| deployment_style | aggressive |
| cooling_share | 0.408 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.952 |
| mguh_direct_ratio | 0.696 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0796 |
| mguh_power_kw | 91.35 |

Notes:
- map: RICH
- heat_scale: 0.988
- cooling_target: 0.408
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: True
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 326.07 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.358 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.61 |
| mguh_direct_ratio | 0.756 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1196 |
| mguh_power_kw | 95.7 |

Notes:
- map: QUALY
- heat_scale: 0.988
- cooling_target: 0.358
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 237.14 |
| torque_ramp | 0.5575 |
| deployment_style | wet_grip |
| cooling_share | 0.558 |
| ers_output_kw | 128.75 |
| deploy_mj_per_lap | 2.567 |
| harvest_mj_per_lap | 1.522 |
| mguh_direct_ratio | 0.586 |
| target_soc_end_lap | 0.543 |
| torque_bias | 0.0196 |
| mguh_power_kw | 78.3 |

Notes:
- map: WET
- heat_scale: 0.988
- cooling_target: 0.558
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 227.26 |
| torque_ramp | 0.4475 |
| deployment_style | harvest |
| cooling_share | 0.608 |
| ers_output_kw | 94.87 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.456 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0204 |
| mguh_power_kw | 69.6 |

Notes:
- map: RECHARGE
- heat_scale: 0.988
- cooling_target: 0.608
- torque_bias_delta: 0.0396
- drs_ratio: 0.64
- deploy_dynamic: 1.097
- harvest_dynamic: 0.814
- deploy_limit_hit: False
- harvest_limit_hit: True
