# PowerUnit calibration – mc-1929_monaco

## Track stats
- heat_mean: 0.731
- heat_peak: 1.300
- drs_ratio: 0.545
- brake_density (MJ/km): 2.959
- power_bias: 0.732
- circuit_length_km: 3.284

## Regen profile
- base_factor: 0.865
- limit_nm: 383.6
- potential_mj_per_lap: 0.736
- regen_migration_bias: -0.217
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.792}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.921 | 1.773 | 0.778 | 0.48 | 0.886 |
| STANDARD | 3.082 | 1.501 | 0.363 | 0.77 | 0.75 |
| RICH | 3.772 | 1.098 | 0.05 | 0.943 | 0.549 |
| QUALY | 4.0 | 0.704 | 0.05 | 1.0 | 0.352 |
| WET | 2.404 | 1.754 | 0.603 | 0.601 | 0.877 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 210.47 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.496 |
| ers_output_kw | 108.12 |
| deploy_mj_per_lap | 1.921 |
| harvest_mj_per_lap | 1.773 |
| mguh_direct_ratio | 0.582 |
| target_soc_end_lap | 0.778 |
| torque_bias | -0.0268 |
| mguh_power_kw | 96.04 |

Notes:
- map: ECONOMY
- heat_scale: 0.957
- cooling_target: 0.496
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 248.74 |
| torque_ramp | 0.6278 |
| deployment_style | balanced |
| cooling_share | 0.446 |
| ers_output_kw | 162.19 |
| deploy_mj_per_lap | 3.082 |
| harvest_mj_per_lap | 1.501 |
| mguh_direct_ratio | 0.622 |
| target_soc_end_lap | 0.363 |
| torque_bias | 0.0232 |
| mguh_power_kw | 104.39 |

Notes:
- map: STANDARD
- heat_scale: 0.957
- cooling_target: 0.446
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 287.01 |
| torque_ramp | 0.8378 |
| deployment_style | aggressive |
| cooling_share | 0.396 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 3.772 |
| harvest_mj_per_lap | 1.098 |
| mguh_direct_ratio | 0.682 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0632 |
| mguh_power_kw | 109.61 |

Notes:
- map: RICH
- heat_scale: 0.957
- cooling_target: 0.396
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 315.71 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.704 |
| mguh_direct_ratio | 0.742 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1032 |
| mguh_power_kw | 114.83 |

Notes:
- map: QUALY
- heat_scale: 0.957
- cooling_target: 0.35
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 229.61 |
| torque_ramp | 0.5378 |
| deployment_style | wet_grip |
| cooling_share | 0.546 |
| ers_output_kw | 128.4 |
| deploy_mj_per_lap | 2.404 |
| harvest_mj_per_lap | 1.754 |
| mguh_direct_ratio | 0.572 |
| target_soc_end_lap | 0.603 |
| torque_bias | 0.0032 |
| mguh_power_kw | 93.95 |

Notes:
- map: WET
- heat_scale: 0.957
- cooling_target: 0.546
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.04 |
| torque_ramp | 0.4278 |
| deployment_style | harvest |
| cooling_share | 0.596 |
| ers_output_kw | 94.61 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.442 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0368 |
| mguh_power_kw | 83.51 |

Notes:
- map: RECHARGE
- heat_scale: 0.957
- cooling_target: 0.596
- torque_bias_delta: 0.0232
- drs_ratio: 0.545
- deploy_dynamic: 1.027
- harvest_dynamic: 0.938
- deploy_limit_hit: False
- harvest_limit_hit: True
