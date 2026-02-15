# PowerUnit calibration – nl-1948_zandvoort

## Track stats
- heat_mean: 0.692
- heat_peak: 1.500
- drs_ratio: 0.405
- brake_density (MJ/km): 2.488
- power_bias: 0.874
- circuit_length_km: 4.229

## Regen profile
- base_factor: 0.851
- limit_nm: 367.1
- potential_mj_per_lap: 1.027
- regen_migration_bias: -0.238
- brake_energy_window: {'min_mj': 0.0, 'max_mj': 2.681}

## ERS budget
- battery_capacity_mj: 5.5
- deploy_limit_mj: 4.0
- harvest_limit_mj: 2.0

| Map | Deploy (MJ) | Harvest (MJ) | Target SOC | Deploy ratio | Harvest ratio |
|-----|-------------|--------------|------------|--------------|---------------|
| ECONOMY | 1.999 | 1.672 | 0.751 | 0.5 | 0.836 |
| STANDARD | 3.208 | 1.415 | 0.331 | 0.802 | 0.708 |
| RICH | 3.926 | 1.035 | 0.05 | 0.982 | 0.517 |
| QUALY | 4.0 | 0.663 | 0.05 | 1.0 | 0.332 |
| WET | 2.502 | 1.654 | 0.573 | 0.625 | 0.827 |
| RECHARGE | 0.5 | 2.0 | 0.98 | 0.125 | 1.0 |

## SOC warnings
- RICH: deploy at 98% of MGU-K limit
- RICH: SOC target very low (0.05) – plan recharge lap
- QUALY: deploy at 100% of MGU-K limit
- QUALY: harvest insufficient vs deploy (ratio 0.33)
- QUALY: SOC target very low (0.05) – plan recharge lap

## Maps
### ECONOMY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 211.88 |
| torque_ramp | 0.3648 |
| deployment_style | conservative |
| cooling_share | 0.488 |
| ers_output_kw | 101.76 |
| deploy_mj_per_lap | 1.999 |
| harvest_mj_per_lap | 1.672 |
| mguh_direct_ratio | 0.561 |
| target_soc_end_lap | 0.751 |
| torque_bias | -0.0126 |
| mguh_power_kw | 87.57 |

Notes:
- map: ECONOMY
- heat_scale: 0.963
- cooling_target: 0.488
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### STANDARD
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 250.4 |
| torque_ramp | 0.6448 |
| deployment_style | balanced |
| cooling_share | 0.438 |
| ers_output_kw | 152.63 |
| deploy_mj_per_lap | 3.208 |
| harvest_mj_per_lap | 1.415 |
| mguh_direct_ratio | 0.601 |
| target_soc_end_lap | 0.331 |
| torque_bias | 0.0374 |
| mguh_power_kw | 95.19 |

Notes:
- map: STANDARD
- heat_scale: 0.963
- cooling_target: 0.438
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### RICH
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 288.92 |
| torque_ramp | 0.8548 |
| deployment_style | aggressive |
| cooling_share | 0.388 |
| ers_output_kw | 190.79 |
| deploy_mj_per_lap | 3.926 |
| harvest_mj_per_lap | 1.035 |
| mguh_direct_ratio | 0.661 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.0774 |
| mguh_power_kw | 99.95 |

Notes:
- map: RICH
- heat_scale: 0.963
- cooling_target: 0.388
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### QUALY
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 317.82 |
| torque_ramp | 1.0 |
| deployment_style | time_attack |
| cooling_share | 0.35 |
| ers_output_kw | 200 |
| deploy_mj_per_lap | 4.0 |
| harvest_mj_per_lap | 0.663 |
| mguh_direct_ratio | 0.721 |
| target_soc_end_lap | 0.05 |
| torque_bias | 0.1174 |
| mguh_power_kw | 104.71 |

Notes:
- map: QUALY
- heat_scale: 0.963
- cooling_target: 0.35
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: True
- harvest_limit_hit: False

### WET
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 231.14 |
| torque_ramp | 0.5548 |
| deployment_style | wet_grip |
| cooling_share | 0.538 |
| ers_output_kw | 120.83 |
| deploy_mj_per_lap | 2.502 |
| harvest_mj_per_lap | 1.654 |
| mguh_direct_ratio | 0.551 |
| target_soc_end_lap | 0.573 |
| torque_bias | 0.0174 |
| mguh_power_kw | 85.67 |

Notes:
- map: WET
- heat_scale: 0.963
- cooling_target: 0.538
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: False

### RECHARGE
| Parametro | Valore |
|-----------|--------|
| heat_load_kw | 221.51 |
| torque_ramp | 0.4448 |
| deployment_style | harvest |
| cooling_share | 0.588 |
| ers_output_kw | 89.04 |
| deploy_mj_per_lap | 0.5 |
| harvest_mj_per_lap | 2.0 |
| mguh_direct_ratio | 0.421 |
| target_soc_end_lap | 0.98 |
| torque_bias | -0.0226 |
| mguh_power_kw | 76.15 |

Notes:
- map: RECHARGE
- heat_scale: 0.963
- cooling_target: 0.588
- torque_bias_delta: 0.0374
- drs_ratio: 0.405
- deploy_dynamic: 1.069
- harvest_dynamic: 0.884
- deploy_limit_hit: False
- harvest_limit_hit: True
