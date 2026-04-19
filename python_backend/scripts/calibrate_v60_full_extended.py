#!/usr/bin/env python3
"""V6.0 EXTENDED - Calibrate EVERYTHING: wings, bwing, springs, ARB, heights, mu."""
import sys, json, time
from pathlib import Path
from dataclasses import dataclass, asdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lap_simulator.physics_engine.core.car_setup import PhysicsV4Setup, DriverSkill

CIRCUIT_CATEGORIES = {
    "monza": "fast", "baku": "fast", "jeddah": "fast", "las_vegas": "fast", "spa": "fast",
    "silverstone": "medium", "spielberg": "medium", "sakhir": "medium", "melbourne": "medium",
    "yas_marina": "medium", "imola": "medium", "montreal": "medium", "miami": "medium",
    "lusail": "medium", "sao_paulo": "medium", "shanghai": "medium", "suzuka": "medium",
    "austin": "medium", "budapest": "slow", "zandvoort": "slow", "singapore": "slow", "monaco": "slow",
    "mexico_city": "medium",
}

WING_RANGES = {
    "fast":   {"fw": (4,  18, 3), "rw": (6,  20, 3)},
    "medium": {"fw": (8,  30, 4), "rw": (10, 34, 4)},
    "slow":   {"fw": (26, 42, 4), "rw": (30, 45, 4)},
}

BWING_RANGES = {"fast": (1, 12, 2), "medium": (5, 20, 3), "slow": (12, 25, 3)}
SPRING_RANGES = {"fast": (15, 35, 3), "medium": (15, 40, 3), "slow": (5, 25, 3)}

ALL_CIRCUITS = {
    "baku": {"circuit_id": "az-2016_baku", "compound": "C6", "fuel_kg": 20.0, "ref_time": 101.117},
    "spa": {"circuit_id": "be-1925_spa_francorchamps", "compound": "C4", "fuel_kg": 20.0, "ref_time": 100.562},
    "shanghai": {"circuit_id": "cn-2004_shanghai", "compound": "C4", "fuel_kg": 20.0, "ref_time": 90.641},
    "sakhir": {"circuit_id": "bh-2002_sakhir", "compound": "C3", "fuel_kg": 20.0, "ref_time": 89.841},
    "melbourne": {"circuit_id": "au-1953_melbourne", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.096},
    "yas_marina": {"circuit_id": "ae-2009_yas_marina", "compound": "C5", "fuel_kg": 20.0, "ref_time": 82.207},
    "barcelona": {"circuit_id": "es-1991_barcelona", "compound": "C3", "fuel_kg": 20.0, "ref_time": 71.546},
    "jeddah": {"circuit_id": "sa-2021_jeddah", "compound": "C5", "fuel_kg": 20.0, "ref_time": 87.294},
    "singapore": {"circuit_id": "sg-2008_singapore", "compound": "C5", "fuel_kg": 20.0, "ref_time": 89.158},
    "sao_paulo": {"circuit_id": "br-1940_sao_paulo", "compound": "C4", "fuel_kg": 20.0, "ref_time": 69.511},
    "monaco": {"circuit_id": "mc-1929_monaco", "compound": "C6", "fuel_kg": 20.0, "ref_time": 69.954},
    "suzuka": {"circuit_id": "jp-1962_suzuka", "compound": "C3", "fuel_kg": 20.0, "ref_time": 86.995},
    "silverstone": {"circuit_id": "gb-1948_silverstone", "compound": "C5", "fuel_kg": 20.0, "ref_time": 85.010},
    "zandvoort": {"circuit_id": "nl-1948_zandvoort", "compound": "C4", "fuel_kg": 20.0, "ref_time": 68.662},
    "budapest": {"circuit_id": "hu-1986_budapest", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.372},
    "monza": {"circuit_id": "it-1922_monza", "compound": "C5", "fuel_kg": 20.0, "ref_time": 78.869},
    "montreal": {"circuit_id": "ca-1978_montreal", "compound": "C6", "fuel_kg": 20.0, "ref_time": 70.899},
    "imola": {"circuit_id": "it-1953_imola", "compound": "C6", "fuel_kg": 20.0, "ref_time": 74.670},
    "mexico_city": {"circuit_id": "mx-1962_mexico_city", "compound": "C5", "fuel_kg": 20.0, "ref_time": 75.586},
    "miami": {"circuit_id": "us-2022_miami", "compound": "C5", "fuel_kg": 20.0, "ref_time": 86.204},
    "lusail": {"circuit_id": "qa-2004_lusail", "compound": "C3", "fuel_kg": 20.0, "ref_time": 79.387},
    "spielberg": {"circuit_id": "at-1969_spielberg", "compound": "C5", "fuel_kg": 20.0, "ref_time": 63.971},
    "austin": {"circuit_id": "us-2012_austin", "compound": "C4", "fuel_kg": 20.0, "ref_time": 92.510},
    "las_vegas": {"circuit_id": "us-2023_las_vegas", "compound": "C5", "fuel_kg": 20.0, "ref_time": 107.934},
}

DRIVER = DriverSkill(name="Reference", quali_skill=1.0, race_skill=1.0, braking_skill=1.0,
    cornering_skill=1.0, throttle_skill=1.0, consistency=1.0, front_wing_offset=0, rear_wing_offset=0, brake_bias_offset=0.0)

AERO_CAL_DIR = ROOT / "data" / "circuits" / "aero_calibration"
SETUP_CAL_DIR = ROOT / "data" / "circuits" / "setup_calibration_full"

def sim(cid, fw, rw, bw, sf, sr, af, ar, hf, hr, comp, mu=None):
    if mu:
        cal = json.load(open(AERO_CAL_DIR / f"{cid}_aero_cal.json"))
        cal["grip_data"]["mu_mechanical"] = mu
        json.dump(cal, open(AERO_CAL_DIR / f"{cid}_aero_cal.json", 'w'), indent=4)
        try:
            from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
            get_aero_calibration.cache_clear()
        except: pass
    setup = PhysicsV4Setup(driver_data=DRIVER, circuit=cid, session="qualifying")
    setup.set_aero(front_wing=fw, rear_wing=rw, bwing=bw)
    setup.set_suspension(spring_front=sf, spring_rear=sr, ARB_front=af, ARB_rear=ar,
        ride_height_front=hf, ride_height_rear=hr)
    setup.set_fuels(fuel_kg=20.0, fuel_mix="rich")
    setup.set_tyres(compound=comp)
    setup.set_ers_mode("quali_deploy")
    return setup.simulate_lap(verbose=False)["lap_time_s"]

def phase1(cid, cfg, cat, sf, sr, af, ar, hf, hr):
    fw_min, fw_max, fw_s = WING_RANGES[cat]["fw"]
    rw_min, rw_max, rw_s = WING_RANGES[cat]["rw"]
    bw_min, bw_max, bw_s = BWING_RANGES[cat]
    best = None; best_t = 999
    for fw in range(int(fw_min), int(fw_max)+1, fw_s):
        for rw in range(int(rw_min), int(rw_max)+1, rw_s):
            for bw in range(int(bw_min), int(bw_max)+1, bw_s):
                t = sim(cid, float(fw), float(rw), float(bw), sf, sr, af, ar, hf, hr, cfg["compound"])
                if t < best_t: best_t = t; best = (fw, rw, bw)
    return float(best[0]), float(best[1]), float(best[2])

def phase2(cid, cfg, fw, rw, bw, af, ar, hf, hr):
    sf_min, sf_max, sf_s = SPRING_RANGES[CIRCUIT_CATEGORIES.get(cid, "medium")]
    sr_min, sr_max, sr_s = SPRING_RANGES[CIRCUIT_CATEGORIES.get(cid, "medium")]
    best_sf, best_sr = sf_min, sr_min
    best_t = sim(cid, fw, rw, bw, best_sf, best_sr, af, ar, hf, hr, cfg["compound"])
    for sf in range(int(sf_min), int(sf_max)+1, int(sf_s)):
        t = sim(cid, fw, rw, bw, float(sf), best_sr, af, ar, hf, hr, cfg["compound"])
        if t < best_t: best_t = t; best_sf = sf
    for sr in range(int(sr_min), int(sr_max)+1, int(sr_s)):
        t = sim(cid, fw, rw, bw, best_sf, float(sr), af, ar, hf, hr, cfg["compound"])
        if t < best_t: best_t = t; best_sr = sr
    return float(best_sf), float(best_sr)

def phase3(cid, cfg, fw, rw, bw, sf, sr):
    best_af, best_ar, best_hf, best_hr = 15.0, 20.0, 5.0, 12.0
    best_t = sim(cid, fw, rw, bw, sf, sr, best_af, best_ar, best_hf, best_hr, cfg["compound"])
    for af in [max(5, best_af-2), best_af, min(30, best_af+2)]:
        t = sim(cid, fw, rw, bw, sf, sr, af, best_ar, best_hf, best_hr, cfg["compound"])
        if t < best_t: best_t = t; best_af = af
    for ar in [max(10, best_ar-2), best_ar, min(35, best_ar+2)]:
        t = sim(cid, fw, rw, bw, sf, sr, best_af, ar, best_hf, best_hr, cfg["compound"])
        if t < best_t: best_t = t; best_ar = ar
    for hf in [max(1, best_hf-2), best_hf, min(20, best_hf+2)]:
        t = sim(cid, fw, rw, bw, sf, sr, best_af, best_ar, hf, best_hr, cfg["compound"])
        if t < best_t: best_t = t; best_hf = hf
    for hr in [max(5, best_hr-2), best_hr, min(25, best_hr+2)]:
        t = sim(cid, fw, rw, bw, sf, sr, best_af, best_ar, best_hf, hr, cfg["compound"])
        if t < best_t: best_t = t; best_hr = hr
    return best_af, best_ar, best_hf, best_hr

def phase4(cid, cfg, mu):
    cal = json.load(open(AERO_CAL_DIR / f"{cid}_aero_cal.json"))
    cal["grip_data"]["mu_mechanical"] = mu
    json.dump(cal, open(AERO_CAL_DIR / f"{cid}_aero_cal.json", 'w'), indent=4)
    try:
        from lap_simulator.physics_engine.calibration.aero_calibration import get_aero_calibration
        get_aero_calibration.cache_clear()
    except: pass

def calibrate(name, cfg):
    cid = cfg["circuit_id"]
    cat = CIRCUIT_CATEGORIES.get(name, "medium")
    print(f"\n{'='*80}\n  {name.upper()} ({cat})\n{'='*80}")
    
    t0 = time.time()
    print("Phase 1: Wings+BW...", end=" ", flush=True)
    fw, rw, bw = phase1(cid, cfg, cat, 25.0, 33.0, 15.0, 20.0, 5.0, 12.0)
    print(f"✓ {time.time()-t0:.0f}s → FW={fw:.0f} RW={rw:.0f} BW={bw:.0f}")
    
    t0 = time.time()
    print("Phase 2: Springs...", end=" ", flush=True)
    sf, sr = phase2(cid, cfg, fw, rw, bw, 15.0, 20.0, 5.0, 12.0)
    print(f"✓ {time.time()-t0:.0f}s → SF={sf:.0f} SR={sr:.0f}")
    
    t0 = time.time()
    print("Phase 3: ARB+Heights...", end=" ", flush=True)
    af, ar, hf, hr = phase3(cid, cfg, fw, rw, bw, sf, sr)
    print(f"✓ {time.time()-t0:.0f}s → AF={af:.1f} AR={ar:.1f} HF={hf:.1f} HR={hr:.1f}")
    
    t0 = time.time()
    print("Phase 4: Mu...", end=" ", flush=True)
    lo, hi = 0.6, 2.5
    for _ in range(15):
        mid = (lo + hi) / 2
        t = sim(cid, fw, rw, bw, sf, sr, af, ar, hf, hr, cfg["compound"], mu=mid)
        if t > cfg["ref_time"]: lo = mid
        else: hi = mid
    mu = (lo + hi) / 2
    t_cal = sim(cid, fw, rw, bw, sf, sr, af, ar, hf, hr, cfg["compound"], mu=mu)
    err = abs(t_cal - cfg["ref_time"]) / cfg["ref_time"] * 100
    print(f"✓ {time.time()-t0:.0f}s → mu={mu:.4f} err={err:+.2f}%")
    
    t_low = sim(cid, max(1, fw-6), max(1, rw-6), bw, sf, sr, af, ar, hf, hr, cfg["compound"], mu=mu)
    t_high = sim(cid, min(50, fw+6), min(50, rw+6), bw, sf, sr, af, ar, hf, hr, cfg["compound"], mu=mu)
    cong = t_cal < t_low and t_cal < t_high
    print(f"Congruence: {'✅' if cong else '❌'} LOW={t_low:.2f}s CAL={t_cal:.2f}s HIGH={t_high:.2f}s")
    
    SETUP_CAL_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "circuit_name": name, "circuit_id": cid, "calibration_version": "v60_full",
        "optimal_setup": {"front_wing": fw, "rear_wing": rw, "bwing": bw, "spring_front": sf,
            "spring_rear": sr, "ARB_front": af, "ARB_rear": ar, "ride_height_front": hf,
            "ride_height_rear": hr, "mu_mechanical": mu, "compound": cfg["compound"]},
        "congruent": cong, "t_cal": t_cal, "t_low": t_low, "t_high": t_high, "error_pct": err
    }
    json.dump(out, open(SETUP_CAL_DIR / f"{cid}_setup_v60_full.json", 'w'), indent=2)
    return cong

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--circuit", type=str)
    args = parser.parse_args()
    
    circuits = ALL_CIRCUITS
    if args.circuit: circuits = {args.circuit: ALL_CIRCUITS[args.circuit]}
    elif args.quick: circuits = {k: v for k, v in ALL_CIRCUITS.items() if k in ["monza", "monaco", "silverstone"]}
    
    print(f"\n{'='*80}\nV6.0 EXTENDED CALIBRATION - {len(circuits)} circuits\n{'='*80}")
    results = [calibrate(n, c) for n, c in sorted(circuits.items())]
    cong = sum(results)
    print(f"\n{'='*80}\nSUMMARY: {cong}/{len(results)} congruent ({100*cong/len(results):.0f}%)\n{'='*80}\n")
