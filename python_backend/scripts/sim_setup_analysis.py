#!/usr/bin/env python3
"""
Headless simulation: how many runs/laps does each AI car need
to collect enough setup data (setup_feedback_ready)?

Outputs an HTML report to python_backend/scripts/setup_report.html
"""
from __future__ import annotations

import os
import sys
import random
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ── path setup ──
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from data.teams import TEAMS
from data.pilots import PILOTS
from models import RaceCar
from models.models import DEFAULT_SETUP_CONFIG
from utils.session_bridge import _ai_setup_target

# ── tier mapping (same as session_bridge) ──
_TEAM_TIERS = {
    "Oracle Red Bull Racing": "top",
    "Scuderia Ferrari": "top",
    "Mercedes-AMG PETRONAS": "top",
    "McLaren F1 Team": "top",
    "Aston Martin Aramco": "midfield",
    "BWT Alpine F1 Team": "midfield",
    "Williams Racing": "midfield",
    "Visa Cash App RB": "midfield",
    "Stake F1 Team Kick Sauber": "backmarker",
    "MoneyGram Haas F1 Team": "backmarker",
}

_TIER_KEYWORDS = {
    "top": ["red bull", "ferrari", "mercedes", "mclaren"],
    "midfield": ["aston", "alpine", "williams", "rb"],
    "backmarker": ["sauber", "haas", "kick"],
}


def get_tier(team_name: str) -> str:
    t = _TEAM_TIERS.get(team_name)
    if t:
        return t
    lower = team_name.lower()
    for tier, kws in _TIER_KEYWORDS.items():
        if any(k in lower for k in kws):
            return tier
    return "midfield"


# ── simulation data types ──
@dataclass
class LapRecord:
    run_idx: int
    lap_idx: int          # within run (0-based)
    lap_type: str         # OUT_LAP, HOT_LAP, IN_LAP
    info_gain: float
    info_total: float
    info_target: float
    info_pct: float
    ready: bool


@dataclass
class RunRecord:
    run_idx: int
    session: str          # FP1, FP2, FP3
    program: str
    laps_planned: int
    hot_laps: int
    total_gain: float
    info_at_start: float
    info_at_end: float
    info_target: float
    pct_at_end: float
    ready_at_end: bool
    ready_at_lap: Optional[int] = None  # hot lap # within run where ready triggered


@dataclass
class CarResult:
    driver_number: int
    driver_name: str
    team_name: str
    team_sigla: str
    tier: str
    ricerca_assetto: int
    info_target: float
    gain_per_lap: float
    runs: List[RunRecord] = field(default_factory=list)
    laps: List[LapRecord] = field(default_factory=list)
    total_hot_laps: int = 0
    total_runs: int = 0
    setup_complete_run: Optional[int] = None   # 1-based run index where ready
    setup_complete_session: Optional[str] = None
    setup_complete_hot_lap: Optional[int] = None  # cumulative hot lap


# ── session programs (mirrors ai_data_types.SESSION_PROGRAMS) ──
SESSION_PROGRAMS = {
    "FP1": ["SETUP_VALIDATION", "SETUP_VALIDATION", "TYRE_DEG"],
    "FP2": ["TYRE_DEG", "QUALI_SIM", "RACE_TRIM"],
    "FP3": ["QUALI_SIM", "SETUP_VALIDATION"],
}

RUN_LAPS_RANGE = {
    "SETUP_VALIDATION": (3, 6),
    "TYRE_DEG": (6, 9),
    "QUALI_SIM": (3, 4),
    "RACE_TRIM": (5, 8),
}


# Tier → sim_efficiency mapping (same as session_bridge)
_TIER_SIM_EFF = {"top": 85, "midfield": 70, "backmarker": 55}


def simulate_car(car: RaceCar, team_name: str, seed: int = 42) -> CarResult:
    """Simulate FP1 → FP2 → FP3 for one AI car, tracking setup info."""
    rng = random.Random(seed + car.driver_number)

    tier = get_tier(team_name)
    skill = getattr(car.pilot, 'ricerca_assetto', 50)
    gain_per_lap = 35.0 * (0.6 + (skill / 100.0) * 0.8)

    sim_eff = _TIER_SIM_EFF.get(tier, 70)
    info_target = _ai_setup_target(sim_eff)
    info_points = 0.0

    result = CarResult(
        driver_number=car.driver_number,
        driver_name=car.driver_name,
        team_name=team_name,
        team_sigla=getattr(car.team, 'sigla_scuderia', '???'),
        tier=tier,
        ricerca_assetto=skill,
        info_target=info_target,
        gain_per_lap=round(gain_per_lap, 1),
    )

    global_run_idx = 0
    cumulative_hot_laps = 0
    setup_done = False

    for session in ["FP1", "FP2", "FP3"]:
        programs = SESSION_PROGRAMS[session]
        for prog in programs:
            laps_lo, laps_hi = RUN_LAPS_RANGE[prog]
            laps_planned = rng.randint(laps_lo, laps_hi)

            info_at_start = info_points
            run_hot_laps = 0
            run_gain = 0.0
            ready_at_lap = None

            for lap_i in range(laps_planned):
                if lap_i == 0:
                    lap_type = "OUT_LAP"
                elif lap_i == laps_planned - 1:
                    lap_type = "IN_LAP"
                else:
                    lap_type = "HOT_LAP"

                gain = 0.0
                if lap_type == "HOT_LAP":
                    gain = gain_per_lap
                    info_points = min(info_points + gain, info_target * 1.5)
                    run_hot_laps += 1
                    cumulative_hot_laps += 1
                    run_gain += gain

                ready = info_points >= info_target
                pct = min(100.0, (info_points / info_target) * 100.0) if info_target > 0 else 100.0

                result.laps.append(LapRecord(
                    run_idx=global_run_idx,
                    lap_idx=lap_i,
                    lap_type=lap_type,
                    info_gain=round(gain, 1),
                    info_total=round(info_points, 1),
                    info_target=info_target,
                    info_pct=round(pct, 1),
                    ready=ready,
                ))

                if ready and not setup_done:
                    setup_done = True
                    result.setup_complete_run = global_run_idx + 1
                    result.setup_complete_session = session
                    result.setup_complete_hot_lap = cumulative_hot_laps
                    if ready_at_lap is None:
                        ready_at_lap = run_hot_laps

                # AI early box: if setup data complete during hot lap, next lap becomes IN_LAP
                if ready and lap_type == "HOT_LAP" and lap_i < laps_planned - 2:
                    # Simulate the in_lap and break
                    in_lap_i = lap_i + 1
                    result.laps.append(LapRecord(
                        run_idx=global_run_idx,
                        lap_idx=in_lap_i,
                        lap_type="IN_LAP (early box)",
                        info_gain=0.0,
                        info_total=round(info_points, 1),
                        info_target=info_target,
                        info_pct=round(pct, 1),
                        ready=True,
                    ))
                    break

            pct_end = min(100.0, (info_points / info_target) * 100.0) if info_target > 0 else 100.0

            result.runs.append(RunRecord(
                run_idx=global_run_idx,
                session=session,
                program=prog,
                laps_planned=laps_planned,
                hot_laps=run_hot_laps,
                total_gain=round(run_gain, 1),
                info_at_start=round(info_at_start, 1),
                info_at_end=round(info_points, 1),
                info_target=info_target,
                pct_at_end=round(pct_end, 1),
                ready_at_end=info_points >= info_target,
                ready_at_lap=ready_at_lap,
            ))

            global_run_idx += 1
            result.total_hot_laps = cumulative_hot_laps
            result.total_runs = global_run_idx

    return result


def generate_html(results: List[CarResult]) -> str:
    """Generate a self-contained HTML report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    tier_colors = {"top": "#4CAF50", "midfield": "#FF9800", "backmarker": "#F44336"}
    tier_labels = {"top": "TOP", "midfield": "MID", "backmarker": "BACK"}

    # Sort by tier then team then driver
    tier_order = {"top": 0, "midfield": 1, "backmarker": 2}
    results.sort(key=lambda r: (tier_order.get(r.tier, 1), r.team_name, r.driver_number))

    # ── Summary table ──
    summary_rows = ""
    for r in results:
        tc = tier_colors.get(r.tier, "#999")
        tl = tier_labels.get(r.tier, "?")
        sess = r.setup_complete_session or "—"
        run_n = r.setup_complete_run or "—"
        hl = r.setup_complete_hot_lap or "—"

        # Find the run where setup completed
        setup_run_detail = ""
        if r.setup_complete_run is not None:
            for rr in r.runs:
                if rr.ready_at_end and setup_run_detail == "":
                    setup_run_detail = f"Run {rr.run_idx+1} ({rr.session} / {rr.program})"

        summary_rows += f"""
        <tr>
            <td><span class="tier-badge" style="background:{tc}">{tl}</span></td>
            <td>{r.team_sigla}</td>
            <td><strong>#{r.driver_number}</strong> {r.driver_name}</td>
            <td class="num">{r.ricerca_assetto}</td>
            <td class="num">{r.info_target:.0f}</td>
            <td class="num">{r.gain_per_lap}</td>
            <td class="num highlight">{run_n}</td>
            <td class="num highlight">{hl}</td>
            <td>{sess}</td>
            <td class="detail">{setup_run_detail}</td>
        </tr>"""

    # ── Per-car run detail ──
    detail_sections = ""
    for r in results:
        tc = tier_colors.get(r.tier, "#999")
        tl = tier_labels.get(r.tier, "?")

        run_rows = ""
        for rr in r.runs:
            bar_w = min(100, rr.pct_at_end)
            bar_color = "#4CAF50" if rr.ready_at_end else "#2196F3"
            ready_icon = "✅" if rr.ready_at_end else ""
            early = ""
            if rr.ready_at_lap is not None:
                early = f" (ready @ hot lap {rr.ready_at_lap})"

            run_rows += f"""
            <tr class="{'run-complete' if rr.ready_at_end else ''}">
                <td>{rr.run_idx+1}</td>
                <td>{rr.session}</td>
                <td>{rr.program}</td>
                <td class="num">{rr.laps_planned}</td>
                <td class="num">{rr.hot_laps}</td>
                <td class="num">{rr.total_gain}</td>
                <td class="num">{rr.info_at_start:.0f}</td>
                <td class="num">{rr.info_at_end:.0f} / {rr.info_target:.0f}</td>
                <td>
                    <div class="bar-bg"><div class="bar-fill" style="width:{bar_w}%;background:{bar_color}"></div></div>
                    <span class="pct">{rr.pct_at_end:.0f}%</span>
                </td>
                <td>{ready_icon}{early}</td>
            </tr>"""

        detail_sections += f"""
        <div class="car-detail">
            <h3><span class="tier-badge" style="background:{tc}">{tl}</span>
                {r.team_sigla} #{r.driver_number} {r.driver_name}
                <span class="skill">ricerca_assetto: {r.ricerca_assetto} | gain/lap: {r.gain_per_lap} | target: {r.info_target:.0f}</span>
            </h3>
            <table class="detail-table">
                <thead><tr>
                    <th>Run</th><th>Session</th><th>Program</th><th>Laps</th><th>Hot</th>
                    <th>Gain</th><th>Start</th><th>End / Target</th><th>Progress</th><th>Status</th>
                </tr></thead>
                <tbody>{run_rows}</tbody>
            </table>
        </div>"""

    # ── Tier summary ──
    tier_summary = ""
    for tier_name in ["top", "midfield", "backmarker"]:
        cars = [r for r in results if r.tier == tier_name]
        if not cars:
            continue
        runs_list = [r.setup_complete_run for r in cars if r.setup_complete_run]
        hls_list = [r.setup_complete_hot_lap for r in cars if r.setup_complete_hot_lap]
        avg_runs = sum(runs_list) / len(runs_list) if runs_list else 0
        avg_hls = sum(hls_list) / len(hls_list) if hls_list else 0
        min_runs = min(runs_list) if runs_list else 0
        max_runs = max(runs_list) if runs_list else 0
        tc = tier_colors[tier_name]
        tl = tier_labels[tier_name]

        sessions = [r.setup_complete_session for r in cars if r.setup_complete_session]
        session_counts = {}
        for s in sessions:
            session_counts[s] = session_counts.get(s, 0) + 1
        session_str = ", ".join(f"{k}: {v}" for k, v in sorted(session_counts.items()))

        tier_summary += f"""
        <div class="tier-card" style="border-left: 4px solid {tc}">
            <h3><span class="tier-badge" style="background:{tc}">{tl}</span> {tier_name.upper()} ({len(cars)} cars)</h3>
            <div class="tier-stats">
                <div><strong>Avg runs to complete:</strong> {avg_runs:.1f}</div>
                <div><strong>Range:</strong> {min_runs}–{max_runs} runs</div>
                <div><strong>Avg hot laps:</strong> {avg_hls:.1f}</div>
                <div><strong>Session breakdown:</strong> {session_str}</div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Setup Optimization Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
h1 {{ color: #fff; margin-bottom: 5px; }}
h2 {{ color: #aaa; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 5px; }}
h3 {{ color: #ddd; margin-bottom: 10px; }}
.subtitle {{ color: #888; font-size: 14px; margin-bottom: 20px; }}
.tier-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; color: #fff; font-size: 11px; font-weight: bold; margin-right: 6px; }}
.skill {{ font-size: 12px; color: #888; font-weight: normal; margin-left: 15px; }}

/* Summary table */
table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
th {{ background: #16213e; color: #aaa; text-align: left; padding: 8px 10px; font-size: 12px; text-transform: uppercase; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #2a2a4a; font-size: 13px; }}
tr:hover {{ background: #1f1f3a; }}
.num {{ text-align: center; }}
.highlight {{ color: #4FC3F7; font-weight: bold; }}
.detail {{ font-size: 11px; color: #888; }}

/* Progress bar */
.bar-bg {{ display: inline-block; width: 80px; height: 12px; background: #333; border-radius: 6px; overflow: hidden; vertical-align: middle; }}
.bar-fill {{ height: 100%; border-radius: 6px; }}
.pct {{ font-size: 11px; margin-left: 4px; }}

/* Tier cards */
.tier-card {{ background: #16213e; padding: 15px 20px; border-radius: 8px; margin-bottom: 12px; }}
.tier-stats {{ display: flex; gap: 30px; flex-wrap: wrap; margin-top: 8px; font-size: 13px; }}
.tier-stats div {{ background: #1a1a2e; padding: 6px 12px; border-radius: 4px; }}

/* Detail */
.car-detail {{ background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 15px; }}
.detail-table th {{ font-size: 11px; }}
.detail-table td {{ font-size: 12px; }}
.run-complete {{ background: rgba(76, 175, 80, 0.08); }}

/* Target reference */
.ref-box {{ background: #16213e; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 40px; flex-wrap: wrap; }}
.ref-box div {{ font-size: 13px; }}
.ref-box strong {{ color: #4FC3F7; }}
</style>
</head>
<body>
<h1>🏎️ AI Setup Optimization Report</h1>
<p class="subtitle">Generated {now} — Simulated FP1 + FP2 + FP3 (all 8 sessions runs per car)</p>

<div class="ref-box">
    <div><strong>Target:</strong> Top ~213 pts | Mid ~325 pts | Back ~438 pts</div>
    <div><strong>Formula:</strong> 100 + (1 − sim_eff/100) × 750</div>
    <div><strong>Base gain/hot lap:</strong> 35 pts × skill multiplier</div>
    <div><strong>Skill multiplier:</strong> 0.6× (skill=1) → 1.4× (skill=100)</div>
    <div><strong>Expected:</strong> Top ≤3 runs | Mid 3-4 runs | Back 4-5 runs</div>
</div>

<h2>📊 Tier Summary</h2>
{tier_summary}

<h2>📋 All Cars — Setup Completion</h2>
<table>
<thead><tr>
    <th>Tier</th><th>Team</th><th>Driver</th><th>Skill</th><th>Target</th><th>Gain/Lap</th>
    <th>Runs</th><th>Hot Laps</th><th>Session</th><th>Detail</th>
</tr></thead>
<tbody>{summary_rows}</tbody>
</table>

<h2>🔍 Per-Car Run Detail</h2>
{detail_sections}

</body>
</html>"""
    return html


def main():
    random.seed(42)

    results: List[CarResult] = []
    for team in TEAMS:
        team_name = team.nome_scuderia
        for pilot in team.piloti_titolari:
            car = RaceCar(pilot=pilot, team=team)
            r = simulate_car(car, team_name, seed=42)
            results.append(r)

    html = generate_html(results)
    out_path = os.path.join(os.path.dirname(__file__), "setup_report.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {out_path}")

    # Quick console summary
    print("\n=== TIER SUMMARY ===")
    for tier in ["top", "midfield", "backmarker"]:
        cars = [r for r in results if r.tier == tier]
        runs = [r.setup_complete_run for r in cars if r.setup_complete_run]
        hls = [r.setup_complete_hot_lap for r in cars if r.setup_complete_hot_lap]
        if runs:
            print(f"  {tier.upper():12s}: avg {sum(runs)/len(runs):.1f} runs, "
                  f"range {min(runs)}-{max(runs)}, "
                  f"avg {sum(hls)/len(hls):.1f} hot laps")
        else:
            print(f"  {tier.upper():12s}: NEVER COMPLETED")


if __name__ == "__main__":
    main()
