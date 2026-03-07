"""
Congruence Check – 4 circuiti, compound reale qualifica 2025, assetto neutro bilanciato.

Compound reali (da pirelli_package nei Telemetry JSON):
  Monza       -> SOFT = C5
  Monaco      -> SOFT = C6
  Silverstone -> SOFT = C3
  Suzuka      -> SOFT = C3

Assetto neutro bilanciato: FW=20°, RW=15° (aero_balance~0.509, handling_penalty~0.007)
CDA_mult=0.0845 calibrato su Monza ref=78.792s

Output per ogni circuito:
  - Tempo simulato vs ref Q3 2025
  - V_max simulato vs telemetria
  - Tabella sezione per sezione: v_exit_sim vs v_max_tel, dt_sim vs dt_ref
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python_backend.lap_simulator.lap_simulator import LapSimulator, CarEntry
from python_backend.lap_simulator.data_types import (
    CarState,
    EnvContext,
    AeroSetup,
    AeroComponent,
    SuspensionState,
    DriverSkills,
    TyreCompound,
    TyreState,
    WheelPosition,
    EngineMapName,
)
from python_backend.lap_simulator.config_loader import load_circuit_config
from python_backend.data.teams import TEAMS

CIRCUITS = {
    "it-1922_monza":       ("Monza",       78.792, 348.0, TyreCompound.C5, "FW=15/RW=10.9"),
    "mc-1929_monaco":      ("Monaco",      69.954, 289.0, TyreCompound.C6, "FW=80/RW=80.5"),
    "gb-1948_silverstone": ("Silverstone", 63.971, 324.0, TyreCompound.C3, "FW=30/RW=27.0"),
    "jp-1962_suzuka":      ("Suzuka",      86.983, 325.0, TyreCompound.C3, "FW=55/RW=53.8"),
}

# Assetti bilanciati per circuito (balance=0.500, handling_penalty≈0)
# Categoria: basso carico=min drag, medio-basso, medio-alto, alto carico=max DF
# Trovati con ricerca griglia FW fisso, RW ottimizzato per balance=0.500
SETUPS = {
    "it-1922_monza":       (15.0, 10.9),   # basso carico:  balance=0.500, penalty=0.0000
    "mc-1929_monaco":      (80.0, 80.5),   # alto carico:   balance=0.500, penalty=0.0001
    "gb-1948_silverstone": (30.0, 27.0),   # medio-basso:   balance=0.500, penalty=0.0001
    "jp-1962_suzuka":      (55.0, 53.8),   # medio-alto:    balance=0.500, penalty=0.0001
}



def make_aero(circuit_id: str, fw_angle: float, rw_angle: float) -> AeroSetup:
    if "monza" in circuit_id:
        # Low Downforce Package (Finestra: 15°)
        fw = AeroComponent(name="front_wing", base_downforce=18.0, base_drag=3.0, angle_deg=fw_angle, angle_ref_deg=15.0, drs_drag_reduction=0.15)
        fw.angle_sensitivity = 0.015
        rw = AeroComponent(name="rear_wing",  base_downforce=16.0, base_drag=4.0, angle_deg=rw_angle, angle_ref_deg=15.0, drs_drag_reduction=0.20)
        rw.angle_sensitivity = 0.015
    elif "monaco" in circuit_id:
        # High Downforce Package (Finestra: 80°)
        fw = AeroComponent(name="front_wing", base_downforce=40.0, base_drag=10.0, angle_deg=fw_angle, angle_ref_deg=80.0, drs_drag_reduction=0.15)
        fw.angle_sensitivity = 0.035
        rw = AeroComponent(name="rear_wing",  base_downforce=38.0, base_drag=12.0, angle_deg=rw_angle, angle_ref_deg=80.0, drs_drag_reduction=0.20)
        rw.angle_sensitivity = 0.035
    else:
        # Medium Downforce Package (Finestra: 45°)
        fw = AeroComponent(name="front_wing", base_downforce=28.0, base_drag=6.0, angle_deg=fw_angle, angle_ref_deg=45.0, drs_drag_reduction=0.15)
        fw.angle_sensitivity = 0.025
        rw = AeroComponent(name="rear_wing",  base_downforce=26.0, base_drag=8.0, angle_deg=rw_angle, angle_ref_deg=45.0, drs_drag_reduction=0.20)
        rw.angle_sensitivity = 0.025

    return AeroSetup(
        front_wing=fw, rear_wing=rw,

        beam_wing    = AeroComponent(name="beam_wing",    base_downforce=5.0,  base_drag=2.5,
                                     angle_deg=8.0, angle_ref_deg=10.0),
        front_floor  = AeroComponent(name="front_floor",  base_downforce=12.0, base_drag=2.0),
        rear_floor   = AeroComponent(name="rear_floor",   base_downforce=12.0, base_drag=2.0),
        sidepods     = AeroComponent(name="sidepods",     base_downforce=4.0,  base_drag=3.0,
                                     cooling_contribution=45.0),
        engine_cover = AeroComponent(name="engine_cover", base_downforce=2.0,  base_drag=1.0,
                                     cooling_contribution=18.0),
        b_wing       = AeroComponent(name="b_wing",       base_downforce=3.0,  base_drag=1.5),
        suspension_front=SuspensionState(rigidity=0.55, efficiency=0.80),
        suspension_rear =SuspensionState(rigidity=0.55, efficiency=0.80),
        ride_height_front_mm=35.0, ride_height_rear_mm=48.0,
        ride_height_optimal_front_mm=35.0, ride_height_optimal_rear_mm=48.0,
    )


# Temperatura ottimale per compound (centro finestra termica)
COMPOUND_OPT_TEMP = {
    TyreCompound.C3: (90.0, 80.0),   # surface, core
    TyreCompound.C4: (93.0, 83.0),
    TyreCompound.C5: (95.0, 85.0),
    TyreCompound.C6: (88.0, 78.0),
}

_BASE_TEAM = next((team for team in TEAMS if team.sigla_scuderia == "MCL"), TEAMS[0])


def make_state(compound: TyreCompound, v_entry_kph: float = 300.0) -> CarState:
    """Condizioni giro di qualifica: gomme quasi nuove, temp ottimale, giro lanciato."""
    state = CarState(car_id="REF")
    state.pu = _BASE_TEAM.power_unit.create_state(fuel_kg=2.5, map_name=EngineMapName.QUALIFY)
    state.ers_mode = "Deploy"
    state.v_current_ms     = v_entry_kph / 3.6
    surf_t, core_t = COMPOUND_OPT_TEMP.get(compound, (92.0, 82.0))
    for wp in WheelPosition:
        ts = TyreState(wheel_pos=wp, compound=compound)
        ts.wear_pct        = 0.02   # quasi nuove (giro di qualifica)
        ts.surface_temp_c  = surf_t
        ts.core_temp_c     = core_t
        state.tyres[wp]    = ts
    return state


def run_circuit(circuit_id: str):
    name, ref_time, ref_vmax, compound, dummy = CIRCUITS[circuit_id]
    fw, rw = SETUPS[circuit_id]

    config = load_circuit_config(circuit_id, 2025)
    env    = EnvContext(air_temp_c=25.0, track_temp_c=38.0)

    # Velocità di ingresso dal giro lanciato: fine del rettilineo principale
    v_entry_kph = config.sections[0].v_entry_kph if config.sections[0].v_entry_kph > 0 else 300.0

    sim = LapSimulator(config, env)
    sim.register_car(CarEntry(
        car_id       = "REF",
        state        = make_state(compound, v_entry_kph),
        aero_setup   = make_aero(circuit_id, fw, rw),
        driver_skills= DriverSkills(raw_pace=95, consistency=90, aggression=60, tyre_management=85),
        push_level   = 1.0,
    ))
    res  = sim.run_lap()["REF"]
    secs = config.sections

    lap_t  = res.lap_time_s
    v_max  = max(s.v_exit_kph for s in res.section_results)
    delta_t = lap_t - ref_time
    delta_v = v_max - ref_vmax

    print(f"\n{'='*80}")
    print(f"  {name.upper()}  |  Compound: {compound.value} (SOFT)  |  Setup: FW={fw:.0f}°/RW={rw:.0f}°")
    print(f"  Tempo sim : {lap_t:>8.3f} s   Ref Q3: {ref_time:.3f} s   Delta: {delta_t:>+.3f} s")
    print(f"  V_max sim : {v_max:>8.1f} kph  Ref tel: {ref_vmax:.1f} kph  Delta: {delta_v:>+.1f} kph")
    print(f"{'='*80}")
    print(f"  {'#':<3} {'Tipo':<18} {'len_m':>5}  "
          f"{'Vmin_tel':>8} {'Vmax_tel':>8}  "
          f"{'Vexit_sim':>9}  {'%Vmax':>6}  "
          f"{'dt_ref':>7} {'dt_sim':>7} {'Δdt':>7}  DRS")
    print(f"  {'-'*88}")

    ok_v = 0; warn_v = 0; bad_v = 0
    ok_t = 0; warn_t = 0; bad_t = 0

    for i, (sec, sr) in enumerate(zip(secs, res.section_results)):
        v_exit = sr.v_exit_kph
        dt_sim = sr.dt_s
        dt_ref = sec.dt_ref_s
        pct_vmax = (v_exit / sec.v_max_kph * 100) if sec.v_max_kph > 0 else 0.0
        drs_mark = "DRS" if sec.drs_available else "   "

        # Valutazione velocità: entro 5% = OK, 5-15% = warn, >15% = bad
        v_err = abs(v_exit - sec.v_max_kph) / max(sec.v_max_kph, 1.0)
        if v_err <= 0.05:   v_sym = "✓"; ok_v += 1
        elif v_err <= 0.15: v_sym = "~"; warn_v += 1
        else:               v_sym = "✗"; bad_v += 1

        # Valutazione dt: entro 5% = OK, 5-15% = warn, >15% = bad
        dt_err = abs(dt_sim - dt_ref) / max(dt_ref, 0.1)
        if dt_err <= 0.05:   t_sym = "✓"; ok_t += 1
        elif dt_err <= 0.15: t_sym = "~"; warn_t += 1
        else:                t_sym = "✗"; bad_t += 1

        print(f"  {i:<3} {sec.kind.value:<18} {sec.length_m:>5.0f}  "
              f"{sec.v_min_kph:>8.1f} {sec.v_max_kph:>8.1f}  "
              f"{v_exit:>9.1f} {v_sym} {pct_vmax:>5.1f}%  "
              f"{dt_ref:>7.3f} {dt_sim:>7.3f} {dt_sim-dt_ref:>+7.3f}  {drs_mark} {t_sym}")

    total = len(secs)
    print(f"\n  Velocità  : ✓{ok_v}/{total}  ~{warn_v}/{total}  ✗{bad_v}/{total}")
    print(f"  Tempi sez : ✓{ok_t}/{total}  ~{warn_t}/{total}  ✗{bad_t}/{total}")
    print(f"  Lap delta : {delta_t:>+.3f} s  ({delta_t/ref_time*100:>+.2f}%)")
    print(f"  Vmax delta: {delta_v:>+.1f} kph  ({delta_v/ref_vmax*100:>+.2f}%)")

    return {
        "circuit": name, "lap_time": lap_t, "ref_time": ref_time,
        "delta_t": delta_t, "v_max": v_max, "ref_vmax": ref_vmax,
        "ok_v": ok_v, "warn_v": warn_v, "bad_v": bad_v,
        "ok_t": ok_t, "warn_t": warn_t, "bad_t": bad_t,
    }


def main():
    print("\n" + "█"*80)
    print("  CONGRUENCE CHECK – F1 Manager AI Physics Engine")
    print("  Compound reale qualifica 2025 | Assetto neutro bilanciato | CDA_mult=0.0845")
    print("█"*80)

    results = []
    for cid in CIRCUITS:
        r = run_circuit(cid)
        results.append(r)

    print(f"\n\n{'='*80}")
    print("  RIEPILOGO FINALE")
    print(f"{'='*80}")
    print(f"  {'Circuito':<14} {'Tempo sim':>10} {'Ref':>8} {'Delta':>8} {'%':>6}  "
          f"{'Vmax sim':>9} {'Vmax tel':>9} {'ΔV':>6}  {'V✓/~✗':>8}  {'T✓/~✗':>8}")
    print(f"  {'-'*90}")
    for r in results:
        v_score = f"{r['ok_v']}/{r['warn_v']}/{r['bad_v']}"
        t_score = f"{r['ok_t']}/{r['warn_t']}/{r['bad_t']}"
        print(f"  {r['circuit']:<14} {r['lap_time']:>10.3f} {r['ref_time']:>8.3f} "
              f"{r['delta_t']:>+8.3f} {r['delta_t']/r['ref_time']*100:>+6.2f}%  "
              f"{r['v_max']:>9.1f} {r['ref_vmax']:>9.1f} {r['v_max']-r['ref_vmax']:>+6.1f}  "
              f"{v_score:>8}  {t_score:>8}")


if __name__ == "__main__":
    main()
