# PowerUnit calibration – az-2016_baku

## Track stats
- heat_mean: 0.748
- heat_peak: 1.500
- drs_ratio: 0.543
- brake_density (MJ/km): 2.810
- power_bias: 0.539
- circuit_length_km: 5.938

## Regen profile
- base_factor: 0.86
- limit_nm: 378.3
- potential_mj_per_lap: 1.189
- regen_migration_bias: -0.224
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.28}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.801 | 1.741 | 0.791 | 0.45 | 0.871 |
| STANDARD | 2.89 | 1.474 | 0.388 | 0.723 | 0.737 |
| RICH | 3.537 | 1.078 | 0.081 | 0.884 | 0.539 |
| QUALY | 4.0 | 0.691 | 0.05 | 1.0 | 0.345 |
| WET | 2.254 | 1.722 | 0.62 | 0.564 | 0.861 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: SOC target very low (0.08) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.35)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 214.94 |
| torque_ramp | 0.35 |
| deployment_style | conservative |
| cooling_share | 0.5 |
| ers_output_kw | 107.63 |
| deploy_mj_per_lap | 1.801 |
| harvest_mj_per_lap | 1.741 |
| mguh_direct_ratio | 0.527 |
| target_soc_end_lap | 0.791 |
| torque_bias | -0.0461 |
| mguh_power_kw | 56.64 |

Notes:
- map: ECONOMY
- heat_scale: 0.977
- cooling_target: 0.5
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 254.02 |
| torque_ramp | 0.6047 |
| deployment_style | balanced |
| cooling_share | 0.45 |
| ers_output_kw | 161.44 |
| deploy_mj_per_lap | 2.89 |
| harvest_mj_per_lap | 1.474 |
| mguh_direct_ratio | 0.567 |
| target_soc_end_lap | 0.388 |
| torque_bias | 0.0039 |
| mguh_power_kw | 61.56 |

Notes:
- map: STANDARD
- heat_scale: 0.977
- cooling_target: 0.45
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 293.1 |
| torque_ramp | 0.8147 |
| deployment_style | aggressive |
| cooling_share | 0.4 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 3.537 |
| harvest_mj_per_lap | 1.078 |
| mguh_direct_ratio | 0.627 |
| target_soc_end_lap | 0.081 |
| torque_bias | 0.0439 |
| mguh_power_kw | 64.64 |

Notes:
- map: RICH
- heat_scale: 0.977
- cooling_target: 0.4
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 322.41 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.691 |
| mguh_direct_ratio | 0.687 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0839 |
| mguh_power_kw | 67.72 |

Notes:
- map: QUALY
- heat_scale: 0.977
- cooling_target: 0.35
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 234.48 |
| torque_ramp | 0.5147 |
| deployment_style | wet_grip |
| cooling_share | 0.55 |
| ers_output_kw | 127.81 |
| deploy_mj_per_lap | 2.254 |
| harvest_mj_per_lap | 1.722 |
| mguh_direct_ratio | 0.517 |
| target_soc_end_lap | 0.62 |
| torque_bias | -0.0161 |
| mguh_power_kw | 55.41 |

Notes:
- map: WET
- heat_scale: 0.977
- cooling_target: 0.55
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 224.71 |
| torque_ramp | 0.4047 |
| deployment_style | harvest |
| cooling_share | 0.6 |
| ers_output_kw | 94.18 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.387 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0561 |
| mguh_power_kw | 49.25 |

Notes:
- map: RECHARGE
- heat_scale: 0.977
- cooling_target: 0.6
- torque_bias_delta: 0.0039
- drs_ratio: 0.543
- deploy_dynamic: 0.963
- harvest_dynamic: 0.921
- deploy_limit_hit: False
- harvest_limit_hit: True
