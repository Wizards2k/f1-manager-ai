# PowerUnit calibration – jp-1962_suzuka

## Track stats
- heat_mean: 0.708
- heat_peak: 1.300
- drs_ratio: 0.514
- brake_density (MJ/km): 1.673
- power_bias: 0.861
- circuit_length_km: 5.766

## Regen profile
- base_factor: 0.828
- limit_nm: 338.5
- potential_mj_per_lap: 1.283
- regen_migration_bias: -0.276
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 1.841}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.997 | 1.495 | 0.725 | 0.499 | 0.748 |
| STANDARD | 3.204 | 1.266 | 0.309 | 0.801 | 0.633 |
| RICH | 3.922 | 0.926 | 0.05 | 0.981 | 0.463 |
| QUALY | 4.0 | 0.593 | 0.05 | 1.0 | 0.296 |
| WET | 2.499 | 1.479 | 0.547 | 0.625 | 0.74 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 98% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.30)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 209.2 |
| torque_ramp | 0.3634 |
| deployment_style | conservative |
| cooling_share | 0.492 |
| ers_output_kw | 103.32 |
| deploy_mj_per_lap | 1.997 |
| harvest_mj_per_lap | 1.495 |
| mguh_direct_ratio | 0.577 |
| target_soc_end_lap | 0.725 |
| torque_bias | -0.0139 |
| mguh_power_kw | 79.04 |

Notes:
- map: ECONOMY
- heat_scale: 0.951
- cooling_target: 0.492
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 247.24 |
| torque_ramp | 0.6434 |
| deployment_style | balanced |
| cooling_share | 0.442 |
| ers_output_kw | 154.98 |
| deploy_mj_per_lap | 3.204 |
| harvest_mj_per_lap | 1.266 |
| mguh_direct_ratio | 0.617 |
| target_soc_end_lap | 0.309 |
| torque_bias | 0.0361 |
| mguh_power_kw | 85.92 |

Notes:
- map: STANDARD
- heat_scale: 0.951
- cooling_target: 0.442
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 285.28 |
| torque_ramp | 0.8534 |
| deployment_style | aggressive |
| cooling_share | 0.392 |
| ers_output_kw | 193.72 |
| deploy_mj_per_lap | 3.922 |
| harvest_mj_per_lap | 0.926 |
| mguh_direct_ratio | 0.677 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0761 |
| mguh_power_kw | 90.21 |

Notes:
- map: RICH
- heat_scale: 0.951
- cooling_target: 0.392
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 313.8 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.593 |
| mguh_direct_ratio | 0.737 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1161 |
| mguh_power_kw | 94.51 |

Notes:
- map: QUALY
- heat_scale: 0.951
- cooling_target: 0.35
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 228.22 |
| torque_ramp | 0.5534 |
| deployment_style | wet_grip |
| cooling_share | 0.542 |
| ers_output_kw | 122.69 |
| deploy_mj_per_lap | 2.499 |
| harvest_mj_per_lap | 1.479 |
| mguh_direct_ratio | 0.567 |
| target_soc_end_lap | 0.547 |
| torque_bias | 0.0161 |
| mguh_power_kw | 77.32 |

Notes:
- map: WET
- heat_scale: 0.951
- cooling_target: 0.542
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 218.71 |
| torque_ramp | 0.4434 |
| deployment_style | harvest |
| cooling_share | 0.592 |
| ers_output_kw | 90.4 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.437 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0239 |
| mguh_power_kw | 68.73 |

Notes:
- map: RECHARGE
- heat_scale: 0.951
- cooling_target: 0.592
- torque_bias_delta: 0.0361
- drs_ratio: 0.514
- deploy_dynamic: 1.068
- harvest_dynamic: 0.791
- deploy_limit_hit: False
- harvest_limit_hit: True
