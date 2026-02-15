# PowerUnit calibration – it-1922_monza

## Track stats
- heat_mean: 0.819
- heat_peak: 1.500
- drs_ratio: 0.462
- brake_density (MJ/km): 2.832
- power_bias: 0.660
- circuit_length_km: 5.725

## Regen profile
- base_factor: 0.861
- limit_nm: 379.1
- potential_mj_per_lap: 1.326
- regen_migration_bias: -0.223
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.524}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.907 | 1.746 | 0.776 | 0.477 | 0.873 |
| STANDARD | 3.059 | 1.478 | 0.363 | 0.765 | 0.739 |
| RICH | 3.745 | 1.081 | 0.05 | 0.936 | 0.54 |
| QUALY | 4.0 | 0.693 | 0.05 | 1.0 | 0.346 |
| WET | 2.386 | 1.727 | 0.601 | 0.597 | 0.864 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.35)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 218.85 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.514 |
| ers_output_kw | 104.78 |
| deploy_mj_per_lap | 1.907 |
| harvest_mj_per_lap | 1.746 |
| mguh_direct_ratio | 0.569 |
| target_soc_end_lap | 0.776 |
| torque_bias | -0.034 |
| mguh_power_kw | 68.24 |

Notes:
- map: ECONOMY
- heat_scale: 0.995
- cooling_target: 0.514
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 258.64 |
| torque_ramp | 0.6192 |
| deployment_style | balanced |
| cooling_share | 0.464 |
| ers_output_kw | 157.16 |
| deploy_mj_per_lap | 3.059 |
| harvest_mj_per_lap | 1.478 |
| mguh_direct_ratio | 0.609 |
| target_soc_end_lap | 0.363 |
| torque_bias | 0.016 |
| mguh_power_kw | 74.17 |

Notes:
- map: STANDARD
- heat_scale: 0.995
- cooling_target: 0.464
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 298.43 |
| torque_ramp | 0.8292 |
| deployment_style | aggressive |
| cooling_share | 0.414 |
| ers_output_kw | 196.46 |
| deploy_mj_per_lap | 3.745 |
| harvest_mj_per_lap | 1.081 |
| mguh_direct_ratio | 0.669 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.056 |
| mguh_power_kw | 77.88 |

Notes:
- map: RICH
- heat_scale: 0.995
- cooling_target: 0.414
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 328.27 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.364 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.693 |
| mguh_direct_ratio | 0.729 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.096 |
| mguh_power_kw | 81.59 |

Notes:
- map: QUALY
- heat_scale: 0.995
- cooling_target: 0.364
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 238.74 |
| torque_ramp | 0.5292 |
| deployment_style | wet_grip |
| cooling_share | 0.564 |
| ers_output_kw | 124.42 |
| deploy_mj_per_lap | 2.386 |
| harvest_mj_per_lap | 1.727 |
| mguh_direct_ratio | 0.559 |
| target_soc_end_lap | 0.601 |
| torque_bias | -0.004 |
| mguh_power_kw | 66.75 |

Notes:
- map: WET
- heat_scale: 0.995
- cooling_target: 0.564
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 228.8 |
| torque_ramp | 0.4192 |
| deployment_style | harvest |
| cooling_share | 0.614 |
| ers_output_kw | 91.68 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.429 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.044 |
| mguh_power_kw | 59.34 |

Notes:
- map: RECHARGE
- heat_scale: 0.995
- cooling_target: 0.614
- torque_bias_delta: 0.016
- drs_ratio: 0.462
- deploy_dynamic: 1.02
- harvest_dynamic: 0.924
- deploy_limit_hit: False
- harvest_limit_hit: True
