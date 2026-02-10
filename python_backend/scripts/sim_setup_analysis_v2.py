#!/usr/bin/env python3
"""
Headless simulation v2: uses the new ai_setup_search engine.

For each AI car, generates a baseline setup from simulator_quality,
then simulates FP1→FP2→FP3 runs adjusting real sliders each time.
Tracks setup score convergence and outputs an HTML report.
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
from utils.ai_setup_search import (
    AISetupState,
    SetupRunResult,
    compute_setup_score,
    _get_pilot_category,
)
from utils.session_bridge import _get_team_tier

# ── session programs (mirrors ai_data_types.SESSION_PROGRAMS) ──
SESSION_PROGRAMS = {
    "FP1": ["SETUP_VALIDATION", "SETUP_VALIDATION", "TYRE_DEG"],
    "FP2": ["TYRE_DEG", "QUALI_SIM", "RACE_TRIM"],
    "FP3": ["QUALI_SIM", "SETUP_VALIDATION"],
}


def simulate_car(team, pilot, seed: int = 42) -> AISetupState:
    """Simulate FP1→FP2→FP3 for one AI car."""
    state = AISetupState(
        car_id=str(pilot.numero_di_gara),
        driver_name=pilot.nome_completo,
        team_name=team.nome_scuderia,
        simulator_quality=team.simulator_quality,
        ricerca_assetto=pilot.ricerca_assetto,
        perfezionismo=pilot.perfezionismo,
    )
    state.initialize(seed=seed + pilot.numero_di_gara)

    for session in ["FP1", "FP2", "FP3"]:
        programs = SESSION_PROGRAMS[session]
        for prog in programs:
            if not state.setup_complete:
                state.process_run(session, prog)
            else:
                # Still log the run but no more adjustments needed
                state.process_run(session, prog)

    return state


def generate_html(results: List[AISetupState]) -> str:
    """Generate a self-contained HTML report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    tier_colors = {"top": "#4CAF50", "midfield": "#FF9800", "backmarker": "#F44336"}
    tier_labels = {"top": "TOP", "midfield": "MID", "backmarker": "BACK"}
    tier_order = {"top": 0, "midfield": 1, "backmarker": 2}

    # Sort by tier then team
    results.sort(key=lambda r: (tier_order.get(_get_team_tier(r.team_name), 1), r.team_name, r.car_id))

    # ── Summary table ──
    summary_rows = ""
    for r in results:
        tier = _get_team_tier(r.team_name)
        tc = tier_colors.get(tier, "#999")
        tl = tier_labels.get(tier, "?")
        cat_label, _, _, _ = _get_pilot_category(r.ricerca_assetto)
        comp_run = r.completion_run or "—"
        comp_sess = r.completion_session or "—"
        initial_score = r.run_history[0].score_before if r.run_history else 0
        final_score = r.setup_score

        summary_rows += f"""
        <tr>
            <td><span class="tier-badge" style="background:{tc}">{tl}</span></td>
            <td>{r.team_name[:20]}</td>
            <td><strong>#{r.car_id}</strong> {r.driver_name}</td>
            <td class="num">{r.ricerca_assetto}</td>
            <td class="num">{cat_label}</td>
            <td class="num">{r.perfezionismo}</td>
            <td class="num">{r.simulator_quality}</td>
            <td class="num">{initial_score:.2f}</td>
            <td class="num">{final_score:.2f}</td>
            <td class="num">{r.threshold:.2f}</td>
            <td class="num highlight">{comp_run}</td>
            <td>{comp_sess}</td>
        </tr>"""

    # ── Per-car run detail ──
    detail_sections = ""
    for r in results:
        tier = _get_team_tier(r.team_name)
        tc = tier_colors.get(tier, "#999")
        tl = tier_labels.get(tier, "?")

        run_rows = ""
        for rr in r.run_history:
            bar_w = min(100, rr.score_after / 10.0 * 100)
            bar_color = "#4CAF50" if rr.setup_complete else "#2196F3"
            ready_icon = "✅" if rr.setup_complete else ""
            changes_str = ", ".join(f"{k}: {v:+.0f}" for k, v in rr.slider_changes.items()) if rr.slider_changes else "—"

            run_rows += f"""
            <tr class="{'run-complete' if rr.setup_complete else ''}">
                <td>{rr.run_index}</td>
                <td>{rr.session}</td>
                <td>{rr.program}</td>
                <td class="num">{rr.score_before:.2f}</td>
                <td class="num">{rr.score_after:.2f}</td>
                <td>
                    <div class="bar-bg"><div class="bar-fill" style="width:{bar_w}%;background:{bar_color}"></div></div>
                    <span class="pct">{rr.score_after:.1f}/10</span>
                </td>
                <td class="num">{rr.threshold:.2f}</td>
                <td>{ready_icon}</td>
                <td class="detail">{changes_str}</td>
            </tr>"""

        detail_sections += f"""
        <div class="car-detail">
            <h3><span class="tier-badge" style="background:{tc}">{tl}</span>
                {r.team_name[:20]} #{r.car_id} {r.driver_name}
                <span class="skill">ric_ass: {r.ricerca_assetto} | perf: {r.perfezionismo} | sim_q: {r.simulator_quality} | threshold: {r.threshold:.2f}</span>
            </h3>
            <table class="detail-table">
                <thead><tr>
                    <th>Run</th><th>Session</th><th>Program</th><th>Score In</th><th>Score Out</th>
                    <th>Progress</th><th>Threshold</th><th>Done</th><th>Slider Changes</th>
                </tr></thead>
                <tbody>{run_rows}</tbody>
            </table>
        </div>"""

    # ── Tier summary ──
    tier_summary = ""
    for tier_name in ["top", "midfield", "backmarker"]:
        cars = [r for r in results if _get_team_tier(r.team_name) == tier_name]
        if not cars:
            continue
        runs_list = [r.completion_run for r in cars if r.completion_run]
        avg_runs = sum(runs_list) / len(runs_list) if runs_list else 0
        min_runs = min(runs_list) if runs_list else 0
        max_runs = max(runs_list) if runs_list else 0
        not_done = len(cars) - len(runs_list)
        tc = tier_colors[tier_name]
        tl = tier_labels[tier_name]

        initial_scores = [r.run_history[0].score_before for r in cars if r.run_history]
        avg_initial = sum(initial_scores) / len(initial_scores) if initial_scores else 0
        final_scores = [r.setup_score for r in cars]
        avg_final = sum(final_scores) / len(final_scores) if final_scores else 0

        sessions = [r.completion_session for r in cars if r.completion_session]
        session_counts = {}
        for s in sessions:
            session_counts[s] = session_counts.get(s, 0) + 1
        session_str = ", ".join(f"{k}: {v}" for k, v in sorted(session_counts.items()))

        tier_summary += f"""
        <div class="tier-card" style="border-left: 4px solid {tc}">
            <h3><span class="tier-badge" style="background:{tc}">{tl}</span> {tier_name.upper()} ({len(cars)} cars)</h3>
            <div class="tier-stats">
                <div><strong>Avg initial score:</strong> {avg_initial:.2f}/10</div>
                <div><strong>Avg final score:</strong> {avg_final:.2f}/10</div>
                <div><strong>Avg runs to complete:</strong> {avg_runs:.1f}</div>
                <div><strong>Range:</strong> {min_runs}–{max_runs} runs</div>
                <div><strong>Not completed:</strong> {not_done}</div>
                <div><strong>Session breakdown:</strong> {session_str}</div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Setup Search Report v2</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
h1 {{ color: #fff; margin-bottom: 5px; }}
h2 {{ color: #aaa; margin: 30px 0 15px; border-bottom: 1px solid #333; padding-bottom: 5px; }}
h3 {{ color: #ddd; margin-bottom: 10px; }}
.subtitle {{ color: #888; font-size: 14px; margin-bottom: 20px; }}
.tier-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; color: #fff; font-size: 11px; font-weight: bold; margin-right: 6px; }}
.skill {{ font-size: 12px; color: #888; font-weight: normal; margin-left: 15px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
th {{ background: #16213e; color: #aaa; text-align: left; padding: 8px 10px; font-size: 12px; text-transform: uppercase; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #2a2a4a; font-size: 13px; }}
tr:hover {{ background: #1f1f3a; }}
.num {{ text-align: center; }}
.highlight {{ color: #4FC3F7; font-weight: bold; }}
.detail {{ font-size: 11px; color: #888; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.bar-bg {{ display: inline-block; width: 80px; height: 12px; background: #333; border-radius: 6px; overflow: hidden; vertical-align: middle; }}
.bar-fill {{ height: 100%; border-radius: 6px; }}
.pct {{ font-size: 11px; margin-left: 4px; }}
.tier-card {{ background: #16213e; padding: 15px 20px; border-radius: 8px; margin-bottom: 12px; }}
.tier-stats {{ display: flex; gap: 30px; flex-wrap: wrap; margin-top: 8px; font-size: 13px; }}
.tier-stats div {{ background: #1a1a2e; padding: 6px 12px; border-radius: 4px; }}
.car-detail {{ background: #16213e; padding: 15px; border-radius: 8px; margin-bottom: 15px; }}
.detail-table th {{ font-size: 11px; }}
.detail-table td {{ font-size: 12px; }}
.run-complete {{ background: rgba(76, 175, 80, 0.08); }}
.ref-box {{ background: #16213e; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 40px; flex-wrap: wrap; }}
.ref-box div {{ font-size: 13px; }}
.ref-box strong {{ color: #4FC3F7; }}
</style>
</head>
<body>
<h1>🏎️ AI Setup Search Report v2</h1>
<p class="subtitle">Generated {now} — Real slider adjustments + score-based convergence</p>

<div class="ref-box">
    <div><strong>Baseline:</strong> from team simulator_quality (top ~90, mid ~72, back ~62)</div>
    <div><strong>Score scale:</strong> 0–10 (from evaluate_setup_categories)</div>
    <div><strong>Threshold:</strong> 7.5 + (perfezionismo - 50) / 200</div>
    <div><strong>Expected:</strong> Top ≤3 runs | Mid 3-4 runs | Back 4-5 runs</div>
</div>

<h2>📊 Tier Summary</h2>
{tier_summary}

<h2>📋 All Cars — Setup Completion</h2>
<table>
<thead><tr>
    <th>Tier</th><th>Team</th><th>Driver</th><th>Ric.Ass.</th><th>Category</th><th>Perf.</th>
    <th>Sim.Q</th><th>Initial</th><th>Final</th><th>Threshold</th><th>Runs</th><th>Session</th>
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

    results: List[AISetupState] = []
    for team in TEAMS:
        for pilot in team.piloti_titolari:
            state = simulate_car(team, pilot, seed=42)
            results.append(state)

    html = generate_html(results)
    out_path = os.path.join(os.path.dirname(__file__), "setup_report_v2.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {out_path}")

    # Quick console summary
    print("\n=== TIER SUMMARY ===")
    for tier in ["top", "midfield", "backmarker"]:
        cars = [r for r in results if _get_team_tier(r.team_name) == tier]
        runs = [r.completion_run for r in cars if r.completion_run]
        initials = [r.run_history[0].score_before for r in cars if r.run_history]
        finals = [r.setup_score for r in cars]
        if runs:
            print(f"  {tier.upper():12s}: avg {sum(runs)/len(runs):.1f} runs, "
                  f"range {min(runs)}-{max(runs)}, "
                  f"avg initial {sum(initials)/len(initials):.2f}, "
                  f"avg final {sum(finals)/len(finals):.2f}")
        else:
            print(f"  {tier.upper():12s}: NEVER COMPLETED "
                  f"(avg final {sum(finals)/len(finals):.2f})")


if __name__ == "__main__":
    main()
