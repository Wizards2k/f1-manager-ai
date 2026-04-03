"""
Diagnostic: Isola il rettilineo DRS (Straight 1) per identificare l'errore fisico

Dati reali:
- Lunghezza: 784.5 m
- v_entry: 321.6 km/h = 89.33 m/s
- v_exit: 347.0 km/h = 96.39 m/s
- DRS: ATTIVO
- Guadagno di velocità: 25.4 km/h in 784.5m

Se il modello fisico è corretto, la simulazione deve raggiungere esattamente 347 km/h.
Se non ci riesce, analiziamo passo per passo quale forza è sbagliata.
"""

import sys
sys.path.insert(0, '/Users/wizards/Sviluppo/F1 Manager AI')

import math
from python_backend.lap_simulator.physics_v3 import constants
from python_backend.lap_simulator.physics_v3.power_curve import get_ice_power_kw
from python_backend.lap_simulator.physics_v3.aero_mapper import map_aero_setup
from python_backend.lap_simulator.physics_v3.acceleration_profile import compute_drive_force
from python_backend.lap_simulator.physics_v3.balance_model import compute_balance
from python_backend.lap_simulator.data_types import AeroSetup, DriverSkills, EnvContext, PUState

print("="*80)
print("DIAGNOSTIC ISOLATO: Rettilineo DRS (Straight 1)")
print("="*80)

# === SETUP ===
aero_setup = AeroSetup()
driver = DriverSkills(raw_pace=70)
env = EnvContext(air_temp_c=20.0, track_temp_c=40.0, air_density_kg_m3=1.225)

# Aero con DRS ATTIVO
aero = map_aero_setup(aero_setup, env, v_estimate_kph=340.0, drs_active=True)

# Power unit a regime (qualifica)
# Nota: ice_power_kw sarà aggiornato dinamicamente durante l'integrazione
pu_state_template = PUState(
    active_map="RACE",
    ers_mode="DEPLOY",
    ice_temp_c=90.0,
    ice_power_kw=constants.ICE_PEAK_POWER_KW,  # Valore iniziale
    ers_energy_mj=4.0,
    ers_output_kw=constants.ERS_PEAK_POWER_KW,
    fuel_kg=5.0,  # Qualifica
)

# === DATI REALI ===
v_entry_kph = 321.6
v_entry_ms = v_entry_kph / 3.6
v_exit_real_kph = 347.0
v_exit_real_ms = v_exit_real_kph / 3.6
section_length_m = 784.5
mass_kg = 798.0

print(f"\n[1] DATI REALI")
print(f"    v_entry: {v_entry_kph:.1f} km/h = {v_entry_ms:.2f} m/s")
print(f"    v_exit:  {v_exit_real_kph:.1f} km/h = {v_exit_real_ms:.2f} m/s")
print(f"    Δv:      {v_exit_real_kph - v_entry_kph:.1f} km/h")
print(f"    Lunghezza: {section_length_m:.1f} m")
print(f"    DRS: ATTIVO")

# === AERO ===
print(f"\n[2] PARAMETRI AERO (DRS ATTIVO)")
print(f"    CDA: {aero.CDA:.4f} m²")
print(f"    CDA_DRS_OPEN: {aero.CDA_drs_open:.4f} m²")
print(f"    CLA: {aero.CLA:.4f} m²")

# === INTEGRAZIONE NUMERICA ===
print(f"\n[3] INTEGRAZIONE NUMERICA (dt = {constants.INTEGRATION_DT_S}s)")

v_current_ms = v_entry_ms
distance_current_m = 0.0
time_current_s = 0.0
telemetry = []

dt = constants.INTEGRATION_DT_S
step = 0

while distance_current_m < section_length_m and step < 100000:
    step += 1

    # Aggiorna PU state con potenza dinamica basata su velocità
    v_current_kph = v_current_ms * 3.6
    ice_power_dynamic_kw = get_ice_power_kw(v_current_kph, ice_max_power_kw=950, gear=7)

    pu_state = PUState(
        active_map="RACE",
        ers_mode="DEPLOY",
        ice_temp_c=90.0,
        ice_power_kw=ice_power_dynamic_kw,  # DINAMICO basato su velocità
        ers_energy_mj=4.0,
        ers_output_kw=150.0,  # ERS léggermente ridotto
        fuel_kg=5.0,
    )

    # Compute balance (rettilineo, no radius)
    balance = compute_balance(
        mu_base=1.70,  # C3 compound
        aero=aero,
        aero_setup=aero_setup,
        v_ms=v_current_ms,
        radius_m=0.0,  # Rettilineo, nessuna curva
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,  # Non frenando, non curvando
    )

    # Compute drive force (rettilineo: no lateral G, no cornering constraint)
    F_drive, a_net, wheelspin = compute_drive_force(
        v_ms=v_current_ms,
        aero=aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=0.0,
        is_cornering=False,
    )

    # Calcula drag force per analisi
    rho = env.air_density_kg_m3
    F_drag_aero = 0.5 * rho * (v_current_ms ** 2) * aero.CDA_drs_open
    F_rolling = constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G
    F_drag_total = F_drag_aero + F_rolling

    # Update velocità
    v_new_ms = math.sqrt(max(0, v_current_ms**2 + 2 * a_net * (v_current_ms * dt)))

    # Distanza percorsa in questo step
    v_avg = (v_current_ms + v_new_ms) / 2
    dist_step = v_avg * dt
    distance_current_m += dist_step
    time_current_s += dt

    # Log ogni 0.5 secondi
    if step % int(0.5 / dt) == 0:
        telemetry.append({
            'time_s': time_current_s,
            'distance_m': distance_current_m,
            'v_ms': v_current_ms,
            'v_kph': v_current_ms * 3.6,
            'a_net': a_net,
            'F_drive': F_drive,
            'F_drag': F_drag_total,
            'wheelspin': wheelspin,
        })

    v_current_ms = v_new_ms

v_exit_sim_ms = v_current_ms
v_exit_sim_kph = v_exit_sim_ms * 3.6

print(f"\n[4] RISULTATO SIMULAZIONE")
print(f"    v_exit simulato: {v_exit_sim_kph:.1f} km/h = {v_exit_sim_ms:.2f} m/s")
print(f"    v_exit reale:    {v_exit_real_kph:.1f} km/h = {v_exit_real_ms:.2f} m/s")
print(f"    ERRORE:          {v_exit_real_kph - v_exit_sim_kph:.1f} km/h ({(v_exit_real_kph - v_exit_sim_kph)/v_exit_real_kph*100:.1f}%)")
print(f"    Tempo simulato:  {time_current_s:.2f} s")
print(f"    Distanza:        {distance_current_m:.1f} m")

# === ANALISI DETTAGLIATA ===
print(f"\n[5] ANALISI DETTAGLIATA DELLA TELEMETRIA")
print(f"\nTempo(s) | Dist(m) | v(km/h) | a(m/s²) | F_drive(N) | F_drag(N) | Wheelspin")
print("-" * 90)

for i, point in enumerate(telemetry):
    ws = "YES" if point['wheelspin'] else "no"
    print(f"{point['time_s']:7.2f} | {point['distance_m']:7.0f} | {point['v_kph']:7.1f} | {point['a_net']:7.2f} | {point['F_drive']:10.0f} | {point['F_drag']:9.0f} | {ws}")

# === ANALISI FORZE ===
print(f"\n[6] ANALISI FORZE A VELOCITÀ CHIAVE")

for v_test_kph in [321.6, 330, 340, 347]:
    v_test_ms = v_test_kph / 3.6

    balance = compute_balance(
        mu_base=1.70,
        aero=aero,
        aero_setup=aero_setup,
        v_ms=v_test_ms,
        radius_m=0.0,
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,
    )

    F_drive, a_net, wheelspin = compute_drive_force(
        v_ms=v_test_ms,
        aero=aero,
        balance=balance,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=0.0,
        is_cornering=False,
    )

    F_drag_aero = 0.5 * constants.RHO_SEA_LEVEL * (v_test_ms ** 2) * aero.CDA_drs_open
    F_rolling = constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G
    F_drag_total = F_drag_aero + F_rolling

    P_available = (pu_state.ice_power_kw + pu_state.ers_output_kw) * constants.DRIVETRAIN_EFFICIENCY * 1000

    print(f"\n  v = {v_test_kph:.1f} km/h ({v_test_ms:.2f} m/s)")
    print(f"    F_drive (forza di spinta): {F_drive:.0f} N")
    print(f"    F_drag (resistenza):       {F_drag_total:.0f} N (aero:{F_drag_aero:.0f} + rolling:{F_rolling:.0f})")
    print(f"    F_net (netta):             {F_drive - F_drag_total:.0f} N")
    print(f"    a_net (accelerazione):     {a_net:.3f} m/s² = {a_net/constants.G:.3f}g")
    print(f"    Potenza disponibile:       {P_available/1000:.0f} kW")
    print(f"    Equilibrio? {abs(F_drive - F_drag_total) < 100}")

# === CONCLUSIONE ===
print(f"\n" + "="*80)
print("CONCLUSIONE")
print("="*80)

if abs(v_exit_sim_kph - v_exit_real_kph) < 1:
    print("✓ IL MODELLO FISICO È CORRETTO - La simulazione raggiunge la velocità reale")
else:
    error_pct = (v_exit_real_kph - v_exit_sim_kph) / v_exit_real_kph * 100
    print(f"✗ ERRORE NEL MODELLO FISICO - La simulazione è {abs(v_exit_real_kph - v_exit_sim_kph):.1f} km/h troppo lenta ({error_pct:.1f}%)")

    # Analisi radice
    print(f"\nAnalisi radice possibile:")

    # Check se le forze sono in equilibrio a v_exit reale
    balance_exit = compute_balance(
        mu_base=1.70,
        aero=aero,
        aero_setup=aero_setup,
        v_ms=v_exit_real_ms,
        radius_m=0.0,
        mass_kg=mass_kg,
        env=env,
        a_long_g=0.0,
    )

    F_drive_exit, _, _ = compute_drive_force(
        v_ms=v_exit_real_ms,
        aero=aero,
        balance=balance_exit,
        mass_kg=mass_kg,
        pu_state=pu_state,
        radius_m=0.0,
        is_cornering=False,
    )

    F_drag_exit = 0.5 * constants.RHO_SEA_LEVEL * (v_exit_real_ms ** 2) * aero.CDA_drs_open
    F_drag_exit += constants.ROLLING_RESISTANCE_COEFF * mass_kg * constants.G

    if abs(F_drive_exit - F_drag_exit) > 100:
        print(f"  • A v_exit reale ({v_exit_real_kph:.0f} km/h): F_drive={F_drive_exit:.0f}N vs F_drag={F_drag_exit:.0f}N")
        if F_drive_exit < F_drag_exit:
            print(f"    → Drag TROPPO ALTO o Potenza TROPPO BASSA")
        else:
            print(f"    → Dovrebbe accelerare ancora, ma il modello non lo fa")
