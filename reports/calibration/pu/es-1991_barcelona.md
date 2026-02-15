# PowerUnit calibration – es-1991_barcelona

## Track stats
- heat_mean: 0.762
- heat_peak: 1.500
- drs_ratio: 0.536
- brake_density (MJ/km): 2.698
- power_bias: 0.747
- circuit_length_km: 4.619

## Regen profile
- base_factor: 0.857
- limit_nm: 374.4
- potential_mj_per_lap: 1.328
- regen_migration_bias: -0.229
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.138}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.943 | 1.717 | 0.766 | 0.486 | 0.859 |
| STANDARD | 3.116 | 1.453 | 0.351 | 0.779 | 0.727 |
| RICH | 3.814 | 1.063 | 0.05 | 0.954 | 0.531 |
| QUALY | 4.0 | 0.681 | 0.05 | 1.0 | 0.341 |
| WET | 2.431 | 1.699 | 0.59 | 0.608 | 0.85 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 95% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.34)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 215.68 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.502 |
| ers_output_kw | 107.08 |
| deploy_mj_per_lap | 1.943 |
| harvest_mj_per_lap | 1.717 |
| mguh_direct_ratio | 0.58 |
| target_soc_end_lap | 0.766 |
| torque_bias | -0.0253 |
| mguh_power_kw | 97.1 |

Notes:
- map: ECONOMY
- heat_scale: 0.98
- cooling_target: 0.502
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 254.9 |
| torque_ramp | 0.6296 |
| deployment_style | balanced |
| cooling_share | 0.452 |
| ers_output_kw | 160.62 |
| deploy_mj_per_lap | 3.116 |
| harvest_mj_per_lap | 1.453 |
| mguh_direct_ratio | 0.62 |
| target_soc_end_lap | 0.351 |
| torque_bias | 0.0247 |
| mguh_power_kw | 105.55 |

Notes:
- map: STANDARD
- heat_scale: 0.98
- cooling_target: 0.452
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 294.12 |
| torque_ramp | 0.8396 |
| deployment_style | aggressive |
| cooling_share | 0.402 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 3.814 |
| harvest_mj_per_lap | 1.063 |
| mguh_direct_ratio | 0.68 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0647 |
| mguh_power_kw | 110.82 |

Notes:
- map: RICH
- heat_scale: 0.98
- cooling_target: 0.402
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 323.53 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.352 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.681 |
| mguh_direct_ratio | 0.74 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1047 |
| mguh_power_kw | 116.1 |

Notes:
- map: QUALY
- heat_scale: 0.98
- cooling_target: 0.352
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 235.29 |
| torque_ramp | 0.5396 |
| deployment_style | wet_grip |
| cooling_share | 0.552 |
| ers_output_kw | 127.16 |
| deploy_mj_per_lap | 2.431 |
| harvest_mj_per_lap | 1.699 |
| mguh_direct_ratio | 0.57 |
| target_soc_end_lap | 0.59 |
| torque_bias | 0.0047 |
| mguh_power_kw | 94.99 |

Notes:
- map: WET
- heat_scale: 0.98
- cooling_target: 0.552
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 225.49 |
| torque_ramp | 0.4296 |
| deployment_style | harvest |
| cooling_share | 0.602 |
| ers_output_kw | 93.7 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.44 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0353 |
| mguh_power_kw | 84.44 |

Notes:
- map: RECHARGE
- heat_scale: 0.98
- cooling_target: 0.602
- torque_bias_delta: 0.0247
- drs_ratio: 0.536
- deploy_dynamic: 1.039
- harvest_dynamic: 0.908
- deploy_limit_hit: False
- harvest_limit_hit: True
