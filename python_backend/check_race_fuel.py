import sys
from pathlib import Path

current_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(current_dir))

from lap_simulator.physics_engine.integrator.waypoint_integrator import integrate_lap_hd

def test_full_race():
    races = [
        ("it-1922_monza", "Monza", 53, {"front_wing": 15.0, "rear_wing": 15.0, "b_wing": 10.0}),
        ("mc-1929_monaco", "Monaco", 78, {"front_wing": 45.0, "rear_wing": 45.0, "b_wing": 10.0})
    ]
    
    engine_map = "RACE"
    push_level = 7
    driver_skill = 1.0  # medio
    
    print(f"⛽ CONTROLLO CONSUMO GARA (Mappa: {engine_map}, Push: {push_level})")
    print("-" * 65)
    
    for cid, cname, total_laps, aero in races:
        current_mass = 110.0  # Fuel
        car_base_mass = 798.0
        
        total_time = 0.0
        fuel_consumed_total = 0.0
        
        # Simuliamo 3 campioni (inizio, metà, fine) per fare una media, o simulare tutto il loop
        # Facciamo una proiezione simulando 3 lap chiave: 110kg, 60kg, 10kg
        
        # Lap Start
        res_start = integrate_lap_hd(circuit_id=cid, aero_setup=aero, mass_kg=car_base_mass+110.0, 
                                     pu_config={"engine_map": engine_map}, driver_skill=driver_skill, 
                                     push_level=push_level, verbose=False)
        
        # Lap Mid
        res_mid = integrate_lap_hd(circuit_id=cid, aero_setup=aero, mass_kg=car_base_mass+60.0, 
                                     pu_config={"engine_map": engine_map}, driver_skill=driver_skill, 
                                     push_level=push_level, verbose=False)
                                     
        # Lap End
        res_end = integrate_lap_hd(circuit_id=cid, aero_setup=aero, mass_kg=car_base_mass+10.0, 
                                     pu_config={"engine_map": engine_map}, driver_skill=driver_skill, 
                                     push_level=push_level, verbose=False)
                                     
        avg_cons = (res_start["fuel_consumed_kg"] + res_mid["fuel_consumed_kg"] + res_end["fuel_consumed_kg"]) / 3.0
        est_total_consumed = avg_cons * total_laps
        
        margin = 110.0 - est_total_consumed
        status = "✅ OK" if margin >= 0 else "❌ FINITO"
        
        print(f"RACE: {cname} ({total_laps} Laps)")
        print(f"  Consumo Medio Stimato: {avg_cons:.3f} Kg/giro")
        print(f"  Consumo Totale Gara:   {est_total_consumed:.2f} Kg")
        print(f"  Benzina Rimanente:     {margin:+.2f} Kg  {status}")
        print("-" * 65)

if __name__ == "__main__":
    test_full_race()
