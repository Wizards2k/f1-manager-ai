# PowerUnit calibration – at-1969_spielberg

## Track stats
- heat_mean: 0.714
- heat_peak: 1.300
- drs_ratio: 0.313
- brake_density (MJ/km): 2.089
- power_bias: 0.832
- circuit_length_km: 4.302

## Regen profile
- base_factor: 0.84
- limit_nm: 353.1
- potential_mj_per_lap: 0.828
- regen_migration_bias: -0.257
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.971}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.98 | 1.585 | 0.741 | 0.495 | 0.792 |
| STANDARD | 3.177 | 1.342 | 0.325 | 0.794 | 0.671 |
| RICH | 3.889 | 0.981 | 0.05 | 0.972 | 0.49 |
| QUALY | 4.0 | 0.629 | 0.05 | 1.0 | 0.315 |
| WET | 2.478 | 1.568 | 0.564 | 0.62 | 0.784 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 97% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.31)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 209.57 |
| torque_ramp | 0.3598 |
| deployment_style | conservative |
| cooling_share | 0.493 |
| ers_output_kw | 97.3 |
| deploy_mj_per_lap | 1.98 |
| harvest_mj_per_lap | 1.585 |
| mguh_direct_ratio | 0.547 |
| target_soc_end_lap | 0.741 |
| torque_bias | -0.0168 |
| mguh_power_kw | 81.28 |

Notes:
- map: ECONOMY
- heat_scale: 0.953
- cooling_target: 0.493
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 247.67 |
| torque_ramp | 0.6398 |
| deployment_style | balanced |
| cooling_share | 0.443 |
| ers_output_kw | 145.95 |
| deploy_mj_per_lap | 3.177 |
| harvest_mj_per_lap | 1.342 |
| mguh_direct_ratio | 0.587 |
| target_soc_end_lap | 0.325 |
| torque_bias | 0.0332 |
| mguh_power_kw | 88.35 |

Notes:
- map: STANDARD
- heat_scale: 0.953
- cooling_target: 0.443
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 285.77 |
| torque_ramp | 0.8498 |
| deployment_style | aggressive |
| cooling_share | 0.393 |
| ers_output_kw | 182.43 |
| deploy_mj_per_lap | 3.889 |
| harvest_mj_per_lap | 0.981 |
| mguh_direct_ratio | 0.647 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0732 |
| mguh_power_kw | 92.76 |

Notes:
- map: RICH
- heat_scale: 0.953
- cooling_target: 0.393
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 314.35 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.629 |
| mguh_direct_ratio | 0.707 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1132 |
| mguh_power_kw | 97.18 |

Notes:
- map: QUALY
- heat_scale: 0.953
- cooling_target: 0.35
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 228.62 |
| torque_ramp | 0.5498 |
| deployment_style | wet_grip |
| cooling_share | 0.543 |
| ers_output_kw | 115.54 |
| deploy_mj_per_lap | 2.478 |
| harvest_mj_per_lap | 1.568 |
| mguh_direct_ratio | 0.537 |
| target_soc_end_lap | 0.564 |
| torque_bias | 0.0132 |
| mguh_power_kw | 79.51 |

Notes:
- map: WET
- heat_scale: 0.953
- cooling_target: 0.543
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 219.09 |
| torque_ramp | 0.4398 |
| deployment_style | harvest |
| cooling_share | 0.593 |
| ers_output_kw | 85.14 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.407 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0268 |
| mguh_power_kw | 70.68 |

Notes:
- map: RECHARGE
- heat_scale: 0.953
- cooling_target: 0.593
- torque_bias_delta: 0.0332
- drs_ratio: 0.313
- deploy_dynamic: 1.059
- harvest_dynamic: 0.839
- deploy_limit_hit: False
- harvest_limit_hit: True
