import sys
from pathlib import Path

current_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(current_dir))

from lap_simulator.physics_v4.integrator.waypoint_integrator import integrate_lap_hd

def run_all_circuits():
    calendar = [
        ("bh-2002_sakhir", "Bahrain", 57),
        ("sa-2021_jeddah", "Jeddah", 50),
        ("au-1953_melbourne", "Melbourne", 58),
        ("jp-1962_suzuka", "Suzuka", 53),
        ("cn-2004_shanghai", "Shanghai", 56),
        ("us-2022_miami", "Miami", 57),
        ("it-1953_imola", "Imola", 63),
        ("mc-1929_monaco", "Monaco", 78),
        ("ca-1978_montreal", "Montreal", 70),
        ("es-1991_barcelona", "Barcelona", 66),
        ("at-1969_spielberg", "Spielberg", 71),
        ("gb-1948_silverstone", "Silverstone", 52),
        ("hu-1986_budapest", "Budapest", 70),
        ("be-1925_spa_francorchamps", "Spa", 44),
        ("nl-1948_zandvoort", "Zandvoort", 72),
        ("it-1922_monza", "Monza", 53),
        ("az-2016_baku", "Baku", 51),
        ("sg-2008_singapore", "Singapore", 62),
        ("us-2012_austin", "Austin", 56),
        ("mx-1962_mexico_city", "Mexico City", 71),
        ("br-1940_sao_paulo", "Sao Paulo", 71),
        ("us-2023_las_vegas", "Las Vegas", 50),
        ("qa-2004_lusail", "Lusail", 57),
        ("ae-2009_yas_marina", "Abu Dhabi", 58)
    ]
    
    engine_map = "RACE"
    push_level = 10
    driver_skill = 1.0
    car_base_mass = 798.0
    
    import json
    
    # Carica i setup ottimali elaborati precedentemente per il V6.0
    optimal_setups_path = current_dir / "optimal_wings_v60_rebalanced.json"
    if optimal_setups_path.exists():
        with open(optimal_setups_path, 'r') as f:
            optimal_setups = json.load(f)
    else:
        optimal_setups = {}
        print("⚠️ File setup ottimali non trovato. Uso setup predefiniti.")

    # Convert mapping to be keyed by circuit_id
    setup_by_cid = { v["circuit_id"]: v for k, v in optimal_setups.items() }

    print("## ⛽ Analisi Consumi Formula 1 (Calendario Completo: 24 Gare)")
    print("> **Parametri Base**: Mappa RACE | Push Level 10/10 (MASSIMO) | **Setup Aerodinamico Ottimale 2025**\n")
    print("| Gara | Circuito | Laps | Setup (FW/RW) | Consumo Medio | Consumo Gara Totale | Benzina Rimasta (Max 110) | Status |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for idx, (cid, cname, total_laps) in enumerate(calendar):
        try:
            # Estrazione aero ottimale per lo specifico tracciato
            aero_opt = setup_by_cid.get(cid, {})
            fw = aero_opt.get("optimal_fw", 20.0)
            rw = aero_opt.get("optimal_rw", 22.0)
            aero = {"front_wing": fw, "rear_wing": rw, "b_wing": 10.0}
            
            res_mid = integrate_lap_hd(
                circuit_id=cid, aero_setup=aero, mass_kg=car_base_mass+60.0,
                pu_config={"engine_map": engine_map}, driver_skill=driver_skill,
                push_level=push_level, verbose=False
            )
            avg_cons = res_mid["fuel_consumed_kg"]
            est_total_consumed = avg_cons * total_laps
            margin = 110.0 - est_total_consumed
            
            if margin >= 15.0:
                status = "🟢 Sicuro"
            elif margin >= 0.0:
                status = "🟡 Limite"
            else:
                status = "🔴 UNDERFUEL"
                
            print(f"| {idx + 1} | **{cname}** | {total_laps} | {avg_cons:.3f} Kg | **{est_total_consumed:.2f} Kg** | {margin:+.2f} Kg | {status} |")
        except Exception as e:
            print(f"| {idx + 1} | **{cname}** | {total_laps} | FALLITO | FALLITO | FALLITO | 💥 ERROR: {e} |")

if __name__ == "__main__":
    run_all_circuits()
