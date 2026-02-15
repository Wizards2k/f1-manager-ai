# PowerUnit calibration – gb-1948_silverstone

## Track stats
- heat_mean: 0.731
- heat_peak: 1.300
- drs_ratio: 0.335
- brake_density (MJ/km): 1.696
- power_bias: 0.785
- circuit_length_km: 5.837

## Regen profile
- base_factor: 0.828
- limit_nm: 339.4
- potential_mj_per_lap: 1.334
- regen_migration_bias: -0.274
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.863}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.956 | 1.5 | 0.732 | 0.489 | 0.75 |
| STANDARD | 3.138 | 1.27 | 0.32 | 0.784 | 0.635 |
| RICH | 3.84 | 0.929 | 0.05 | 0.96 | 0.465 |
| QUALY | 4.0 | 0.595 | 0.05 | 1.0 | 0.297 |
| WET | 2.447 | 1.484 | 0.556 | 0.612 | 0.742 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 96% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.30)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 210.47 |
| torque_ramp | 0.3542 |
| deployment_style | conservative |
| cooling_share | 0.496 |
| ers_output_kw | 96.93 |
| deploy_mj_per_lap | 1.956 |
| harvest_mj_per_lap | 1.5 |
| mguh_direct_ratio | 0.55 |
| target_soc_end_lap | 0.732 |
| torque_bias | -0.0215 |
| mguh_power_kw | 68.38 |

Notes:
- map: ECONOMY
- heat_scale: 0.957
- cooling_target: 0.496
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 248.74 |
| torque_ramp | 0.6342 |
| deployment_style | balanced |
| cooling_share | 0.446 |
| ers_output_kw | 145.39 |
| deploy_mj_per_lap | 3.138 |
| harvest_mj_per_lap | 1.27 |
| mguh_direct_ratio | 0.59 |
| target_soc_end_lap | 0.32 |
| torque_bias | 0.0285 |
| mguh_power_kw | 74.33 |

Notes:
- map: STANDARD
- heat_scale: 0.957
- cooling_target: 0.446
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 287.01 |
| torque_ramp | 0.8442 |
| deployment_style | aggressive |
| cooling_share | 0.396 |
| ers_output_kw | 181.74 |
| deploy_mj_per_lap | 3.84 |
| harvest_mj_per_lap | 0.929 |
| mguh_direct_ratio | 0.65 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0685 |
| mguh_power_kw | 78.05 |

Notes:
- map: RICH
- heat_scale: 0.957
- cooling_target: 0.396
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
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
| harvest_mj_per_lap | 0.595 |
| mguh_direct_ratio | 0.71 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1085 |
| mguh_power_kw | 81.76 |

Notes:
- map: QUALY
- heat_scale: 0.957
- cooling_target: 0.35
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 229.61 |
| torque_ramp | 0.5442 |
| deployment_style | wet_grip |
| cooling_share | 0.546 |
| ers_output_kw | 115.1 |
| deploy_mj_per_lap | 2.447 |
| harvest_mj_per_lap | 1.484 |
| mguh_direct_ratio | 0.54 |
| target_soc_end_lap | 0.556 |
| torque_bias | 0.0085 |
| mguh_power_kw | 66.9 |

Notes:
- map: WET
- heat_scale: 0.957
- cooling_target: 0.546
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 220.04 |
| torque_ramp | 0.4342 |
| deployment_style | harvest |
| cooling_share | 0.596 |
| ers_output_kw | 84.81 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.41 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0315 |
| mguh_power_kw | 59.46 |

Notes:
- map: RECHARGE
- heat_scale: 0.957
- cooling_target: 0.596
- torque_bias_delta: 0.0285
- drs_ratio: 0.335
- deploy_dynamic: 1.046
- harvest_dynamic: 0.794
- deploy_limit_hit: False
- harvest_limit_hit: True
