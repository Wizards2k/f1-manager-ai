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

    tier_colors = {"top": "#c084fc", "midfield": "#7dd3fc", "backmarker": "#fcd34d"}
    tier_bg = {"top": "#2a1a3a", "midfield": "#1a2a3a", "backmarker": "#2a2a1a"}
    tier_labels = {"top": "TOP", "midfield": "MID", "backmarker": "BACK"}
    tier_order = {"top": 0, "midfield": 1, "backmarker": 2}
    tier_target = {"top": "2-3", "midfield": "3-4", "backmarker": "4-5"}

    results.sort(key=lambda r: (tier_order.get(_get_team_tier(r.team_name), 1), r.team_name, r.car_id))

    # ── Tier summary cards ──
    tier_cards = ""
    for tier_name in ["top", "midfield", "backmarker"]:
        cars = [r for r in results if _get_team_tier(r.team_name) == tier_name]
        if not cars:
            continue
        runs_list = [r.completion_run for r in cars if r.completion_run]
        avg_runs = sum(runs_list) / len(runs_list) if runs_list else 0
        min_runs = min(runs_list) if runs_list else 0
        max_runs = max(runs_list) if runs_list else 0
        not_done = len(cars) - len(runs_list)
        initial_scores = [r.run_history[0].score_before for r in cars if r.run_history]
        avg_initial = sum(initial_scores) / len(initial_scores) if initial_scores else 0
        avg_final = sum(r.setup_score for r in cars) / len(cars)
        tc = tier_colors[tier_name]
        tbg = tier_bg[tier_name]
        tl = tier_labels[tier_name]
        tgt = tier_target[tier_name]
        status = "pass" if not_done == 0 else "warn"
        status_icon = "&#10003;" if not_done == 0 else f"&#9888; {not_done} incomplete"

        tier_cards += f"""
        <div class="tier-card" style="border-left:4px solid {tc}">
          <div class="tier-header">
            <span class="tier" style="background:{tbg};color:{tc}">{tl}</span>
            <span class="tier-title">{tier_name.upper()}</span>
            <span class="tier-count">{len(cars)} cars</span>
          </div>
          <div class="tier-grid">
            <div class="metric"><div class="metric-val">{avg_initial:.1f}</div><div class="metric-lbl">Avg Initial</div></div>
            <div class="metric"><div class="metric-val">{avg_final:.1f}</div><div class="metric-lbl">Avg Final</div></div>
            <div class="metric"><div class="metric-val">{avg_runs:.1f}</div><div class="metric-lbl">Avg Runs</div></div>
            <div class="metric"><div class="metric-val">{min_runs}–{max_runs}</div><div class="metric-lbl">Range</div></div>
            <div class="metric"><div class="metric-val">{tgt}</div><div class="metric-lbl">Target</div></div>
            <div class="metric {'metric-ok' if not_done==0 else 'metric-warn'}"><div class="metric-val">{status_icon}</div><div class="metric-lbl">Status</div></div>
          </div>
        </div>"""

    # ── Main driver table ──
    driver_rows = ""
    for r in results:
        tier = _get_team_tier(r.team_name)
        tc = tier_colors.get(tier, "#999")
        tbg = tier_bg.get(tier, "#222")
        tl = tier_labels.get(tier, "?")
        cat_label, _, _, _ = _get_pilot_category(r.ricerca_assetto)
        comp_run = r.completion_run or "—"
        comp_sess = r.completion_session or "—"
        initial_score = r.run_history[0].score_before if r.run_history else 0
        final_score = r.setup_score
        gain = final_score - initial_score

        bar_init = min(100, initial_score / 10.0 * 100)
        bar_final = min(100, final_score / 10.0 * 100)
        done_cls = "row-done" if r.completion_run else "row-pending"

        driver_rows += f"""
        <tr class="{done_cls}">
          <td><span class="tier" style="background:{tbg};color:{tc}">{tl}</span></td>
          <td>{r.team_name}</td>
          <td><strong>{r.driver_name}</strong></td>
          <td class="num">{r.ricerca_assetto}</td>
          <td class="num"><span class="cat-tag cat-{cat_label}">{cat_label}</span></td>
          <td class="num">{r.perfezionismo}</td>
          <td class="num">{r.simulator_quality}</td>
          <td class="num">
            <div class="score-cell">
              <div class="mini-bar"><div class="mini-fill" style="width:{bar_init}%;background:#5b7db1"></div></div>
              {initial_score:.2f}
            </div>
          </td>
          <td class="num">
            <div class="score-cell">
              <div class="mini-bar"><div class="mini-fill" style="width:{bar_final}%;background:#63d59f"></div></div>
              {final_score:.2f}
            </div>
          </td>
          <td class="num gain">+{gain:.2f}</td>
          <td class="num">{r.threshold:.2f}</td>
          <td class="num runs-cell">{comp_run}</td>
          <td class="num">{comp_sess}</td>
        </tr>"""

    # ── Per-car run detail (collapsible) ──
    detail_blocks = ""
    for idx, r in enumerate(results):
        tier = _get_team_tier(r.team_name)
        tc = tier_colors.get(tier, "#999")
        tbg = tier_bg.get(tier, "#222")
        tl = tier_labels.get(tier, "?")
        initial_score = r.run_history[0].score_before if r.run_history else 0

        run_rows = ""
        for rr in r.run_history:
            gain = rr.score_after - rr.score_before
            gain_cls = "gain-pos" if gain > 0.01 else ("gain-neg" if gain < -0.01 else "gain-zero")
            bar_w = min(100, rr.score_after / 10.0 * 100)
            bar_color = "#63d59f" if rr.setup_complete else "#5b7db1"
            done_icon = "<span class='done-check'>&#10003;</span>" if rr.setup_complete else ""
            changes = rr.slider_changes or {}
            changes_parts = []
            for k, v in sorted(changes.items()):
                cls = "chg-pos" if v > 0 else "chg-neg"
                changes_parts.append(f"<span class='{cls}'>{k.replace('_',' ')}: {v:+.0f}</span>")
            changes_str = " ".join(changes_parts) if changes_parts else "<span class='no-chg'>no changes</span>"

            run_rows += f"""
            <tr class="{'rr-done' if rr.setup_complete else ''}">
              <td class="num">{rr.run_index}</td>
              <td>{rr.session}</td>
              <td><span class="prog-tag">{rr.program}</span></td>
              <td class="num">{rr.score_before:.2f}</td>
              <td class="num">{rr.score_after:.2f}</td>
              <td class="num {gain_cls}">{gain:+.2f}</td>
              <td>
                <div class="bar-bg"><div class="bar-fill" style="width:{bar_w}%;background:{bar_color}"></div></div>
              </td>
              <td class="num">{done_icon}</td>
              <td class="changes-cell">{changes_str}</td>
            </tr>"""

        detail_blocks += f"""
        <details class="driver-detail" id="detail-{idx}">
          <summary>
            <span class="tier" style="background:{tbg};color:{tc}">{tl}</span>
            <strong>{r.driver_name}</strong>
            <span class="detail-meta">{r.team_name} | sim_q: {r.simulator_quality} | ric: {r.ricerca_assetto} | perf: {r.perfezionismo} | init: {initial_score:.2f} &rarr; {r.setup_score:.2f} | threshold: {r.threshold:.2f} | runs: {r.completion_run or '—'}</span>
          </summary>
          <table class="run-table">
            <thead><tr>
              <th>Run</th><th>Session</th><th>Program</th><th>Score In</th><th>Score Out</th><th>Gain</th><th>Progress</th><th>Done</th><th>Slider Changes</th>
            </tr></thead>
            <tbody>{run_rows}</tbody>
          </table>
        </details>"""

    # ── Global stats ──
    total_cars = len(results)
    total_done = sum(1 for r in results if r.completion_run)
    total_runs = sum(r.total_runs for r in results)
    avg_all = sum(r.completion_run for r in results if r.completion_run) / max(1, total_done)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>AI Setup Search Report</title>
<style>
body{{font-family:"Segoe UI",Arial,sans-serif;background:#0d0d0d;color:#e0e0e0;padding:24px;max-width:1400px;margin:0 auto}}
h1{{color:#ff6b35;margin-bottom:4px}}
.meta{{color:#888;margin-bottom:20px;font-size:.95em}}
.stats{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
.stat-box{{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:12px 20px;min-width:120px}}
.stat-box .val{{font-size:1.6em;font-weight:bold;color:#63d59f}}.stat-box .label{{font-size:.82em;color:#888}}

.tier-card{{background:#1a1a1a;border:1px solid #333;border-radius:8px;padding:14px 18px;margin-bottom:10px}}
.tier-header{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
.tier-title{{font-weight:700;font-size:1.05em}}.tier-count{{color:#888;font-size:.85em}}
.tier-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}
.metric{{background:#111;border-radius:6px;padding:8px 12px;text-align:center}}
.metric-val{{font-size:1.3em;font-weight:700;color:#e0e0e0}}.metric-lbl{{font-size:.75em;color:#888;margin-top:2px}}
.metric-ok .metric-val{{color:#63d59f}}.metric-warn .metric-val{{color:#f5d56a}}

.tier{{padding:2px 8px;border-radius:3px;font-size:.8em;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-size:.9em;margin-bottom:20px}}
th{{background:#1a1a1a;padding:8px 10px;text-align:left;border-bottom:2px solid #333;position:sticky;top:0;font-size:.82em;text-transform:uppercase;color:#888}}
td{{padding:7px 10px;border-bottom:1px solid #1f1f1f}}
tr:hover{{background:#1a1a1a}}
.num{{text-align:center}}
.gain{{color:#63d59f;font-weight:600}}
.runs-cell{{font-weight:700;color:#7dd3fc;font-size:1.05em}}
.row-done{{}}
.row-pending td{{opacity:.6}}

.score-cell{{display:flex;align-items:center;gap:6px;justify-content:center}}
.mini-bar{{width:50px;height:6px;background:#222;border-radius:3px;overflow:hidden}}
.mini-fill{{height:100%;border-radius:3px}}

.cat-tag{{padding:2px 6px;border-radius:3px;font-size:.78em;font-weight:600}}
.cat-elite{{background:#174b2f;color:#63d59f}}
.cat-solido{{background:#1a2a3a;color:#7dd3fc}}
.cat-incostante{{background:#3d3520;color:#f5d56a}}
.cat-sperimentale{{background:#522;color:#ff8787}}

h2{{color:#ccc;margin:28px 0 12px;border-bottom:1px solid #333;padding-bottom:6px;font-size:1.1em}}

.driver-detail{{background:#1a1a1a;border:1px solid #333;border-radius:8px;margin-bottom:8px}}
.driver-detail summary{{padding:10px 14px;cursor:pointer;display:flex;align-items:center;gap:8px;font-size:.9em}}
.driver-detail summary:hover{{background:#222}}
.detail-meta{{color:#888;font-size:.85em;margin-left:auto}}
.run-table{{margin:0;font-size:.85em}}
.run-table th{{font-size:.78em;background:#111}}
.run-table td{{padding:5px 8px;border-bottom:1px solid #1a1a1a}}
.rr-done{{background:rgba(99,213,159,.06)}}
.done-check{{color:#63d59f;font-weight:700}}
.gain-pos{{color:#63d59f}}.gain-neg{{color:#ff8787}}.gain-zero{{color:#666}}
.bar-bg{{display:inline-block;width:70px;height:8px;background:#222;border-radius:4px;overflow:hidden;vertical-align:middle}}
.bar-fill{{height:100%;border-radius:4px}}
.prog-tag{{background:#222;padding:2px 6px;border-radius:3px;font-size:.82em;color:#aaa}}
.changes-cell{{font-size:.8em;max-width:350px}}
.chg-pos{{color:#63d59f;margin-right:6px}}.chg-neg{{color:#ff8787;margin-right:6px}}.no-chg{{color:#555}}
</style></head><body>

<h1>AI Setup Search Report</h1>
<div class="meta">Generated: <strong>{now}</strong> | Score scale: 0–10 | Threshold: 8.1 + perfezionismo offset | Baseline from simulator_quality</div>

<div class="stats">
  <div class="stat-box"><div class="val">{total_cars}</div><div class="label">Total Cars</div></div>
  <div class="stat-box"><div class="val">{total_done}/{total_cars}</div><div class="label">Completed</div></div>
  <div class="stat-box"><div class="val">{total_runs}</div><div class="label">Total Runs</div></div>
  <div class="stat-box"><div class="val">{avg_all:.1f}</div><div class="label">Avg Runs to Complete</div></div>
</div>

<h2>Tier Summary</h2>
{tier_cards}

<h2>All Drivers</h2>
<table>
<thead><tr>
  <th>Tier</th><th>Team</th><th>Driver</th><th>Ric.Ass.</th><th>Category</th><th>Perf.</th>
  <th>Sim.Q</th><th>Initial Score</th><th>Final Score</th><th>Gain</th><th>Threshold</th><th>Runs</th><th>Session</th>
</tr></thead>
<tbody>{driver_rows}</tbody>
</table>

<h2>Run Detail (click to expand)</h2>
{detail_blocks}

</body></html>"""
    return html


def main():
    random.seed(42)

    def iter_team_pilots(team):
        pilots = []
        if getattr(team, "pilota1", None):
            pilots.append(team.pilota1)
        if getattr(team, "pilota2", None):
            pilots.append(team.pilota2)
        if not pilots and hasattr(team, "piloti_titolari"):
            pilots.extend(team.piloti_titolari)
        return pilots

    results: List[AISetupState] = []
    for team in TEAMS:
        for pilot in iter_team_pilots(team):
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
