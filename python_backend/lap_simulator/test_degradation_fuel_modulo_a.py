import sys
import os
from pathlib import Path

# Add the project root to the python path
current_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(current_dir))

from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

def run_degradation_tests():
    print("===================================================================")
    print("🧪 V6.1 DEGRADATION TEST: Modulo A (Fuel & Mass Dynamics)")
    print("===================================================================\n")
    
    circuits = [
        ("it-1922_monza", "Monza (Fast)"),
        ("mc-1929_monaco", "Monaco (Tight)")
    ]
    
    mass_scenarios = [
        (110.0, "110kg"),
        (10.0, "10kg")
    ]
    
    engine_maps = ["QUALIFY", "ECONOMY"]
    
    aero_setups = [
        ({"front_wing": 15.0, "rear_wing": 15.0, "b_wing": 10.0}, "LowD"),
    ]
    
    # Driver Skill rating (intrinsic)
    d_skills = [(1.05, "Top Driver"), (0.95, "Rookie")]
    
    # Push level (from 1 to 10, game UI slider)
    push_levels = [(10, "Push L10"), (1, "Save L1")]
    
    # Run test matrix
    for cid, cname in circuits:
        print(f"🏎️  CIRUIT: {cname} ({cid})")
        print(f"{'Mass':<4} | {'Aero':<4} | {'Map':<7} | {'Skill':<11} | {'Pace':<9} | {'Lap Time':<9} | {'Fuel Cons':<9} | {'Speed':<9}")
        print("-" * 90)
        
        baseline_time_quali = None
        
        for aero_dict, aero_label in aero_setups:
            for emap in engine_maps:
                for base_mass, mass_label in mass_scenarios:
                    for ds, ds_lbl in d_skills:
                        for p_lvl, p_lbl in push_levels:
                        
                            car_base_mass = 798.0
                            total_mass = car_base_mass + base_mass
                            
                            try:
                                result = integrate_lap_hd(
                                    circuit_id=cid,
                                    aero_setup=aero_dict,
                                    mass_kg=total_mass,
                                    pu_config={"engine_map": emap},
                                    driver_skill=ds,
                                    push_level=p_lvl,
                                    verbose=False
                                )
                                
                                lap_time = result["lap_time_s"]
                                fuel_consumed = result["fuel_consumed_kg"]
                                avg_speed = result["v_avg_kph"]
                                
                                if emap == "QUALIFY" and aero_label == "LowD" and base_mass == 10.0 and p_lvl == 10 and ds == 1.05:
                                    baseline_time_quali = lap_time
                                
                                delta_str = ""
                                if baseline_time_quali:
                                    delta = lap_time - baseline_time_quali
                                    if delta != 0:
                                        delta_str = f"({delta:+.3f}s)"
                                    
                                print(f"{base_mass:>3.0f}k | {aero_label:<4} | {emap:<7} | {ds_lbl:<11} | {p_lbl:<9} | {lap_time:>7.3f}s | {fuel_consumed:>6.3f} Kg | {avg_speed:>5.1f} kph {delta_str}")
                            except Exception as e:
                                print(f"Failed configuration: {e}")
        print("\n")

if __name__ == "__main__":
    run_degradation_tests()
