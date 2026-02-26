#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from typing import Dict, List

def generate_html_report(results_file: str, output_file: str = None):
    """Generate HTML report from team simulation results."""
    with open(results_file) as f:
        results = json.load(f)
    
    # Sort by lap time (best first)
    sorted_teams = sorted(results.items(), key=lambda kv: kv[1]["lap_time_s"])
    
    # Prepare HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Team Simulation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        h1 {{ color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px; text-align: center; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; font-weight: bold; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        tr:hover {{ background-color: #f1f1f1; }}
        .pos {{ font-weight: bold; }}
        .team {{ text-align: left; font-weight: bold; }}
        .gap-pos {{ color: #2196F3; }}
        .gap-neg {{ color: #f44336; }}
        .delta-pos {{ color: #4CAF50; }}
        .delta-neg {{ color: #ff9800; }}
        .section {{ font-size: 0.9em; color: #666; }}
        .summary {{ background: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <h1>Team Simulation Report - Silverstone</h1>
    
    <div class="summary">
        <p><strong>Circuit:</strong> gb-1948_silverstone</p>
        <p><strong>Baseline:</strong> McLaren (MCL)</p>
        <p><strong>Mode:</strong> Qualifying (Soft tyres, 2.5kg fuel, Deploy ERS)</p>
        <p><strong>Teams:</strong> 10 sandbox teams based on 2025 performance gaps</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>POS</th>
                <th>TEAM</th>
                <th>LAP TIME</th>
                <th>EXPECTED GAP</th>
                <th>SIMULATED GAP</th>
                <th>Δ (SIM - EXP)</th>
                <th>SECTOR TIMES</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for pos, (team_code, data) in enumerate(sorted_teams, start=1):
        lap_time = data["lap_time_s"]
        expected_gap = data["expected_gap_pct"]
        sim_gap = data["simulated_gap_pct"]
        delta = sim_gap - expected_gap
        
        # Format classes
        sim_gap_class = "gap-pos" if sim_gap >= 0 else "gap-neg"
        delta_class = "delta-pos" if delta >= 0 else "delta-neg"
        
        # Format sector times
        sectors = data["section_times"]
        sector_str = " | ".join([f"{s:.3f}" for s in sectors])
        
        html += f"""
            <tr>
                <td class="pos">{pos}</td>
                <td class="team">{team_code}</td>
                <td>{lap_time:.3f}s</td>
                <td class="gap-pos">{expected_gap:+.2f}%</td>
                <td class="{sim_gap_class}">{sim_gap:+.2f}%</td>
                <td class="{delta_class}">{delta:+.2f}%</td>
                <td class="section">{sector_str}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <div class="summary">
        <h3>Analysis</h3>
        <p><strong>Gap Accuracy:</strong> All teams show identical simulated times to McLaren, indicating the sandbox scaling factors are not yet translated into LapSimulator penalties.</p>
        <p><strong>Next Steps:</strong> Map sandbox aero/grip/power unit scaling to LapSimulator penalty coefficients (delta_aero, delta_grip, delta_power) to reflect expected gaps.</p>
    </div>
</body>
</html>
"""
    
    # Write output
    out_path = Path(output_file) if output_file else Path("reports/team_simulation_report.html")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html)
    
    print(f"HTML report generated: {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate HTML report from team simulation results")
    parser.add_argument("results", help="JSON results file from run_sim_teams.py")
    parser.add_argument("-o", "--output", help="Output HTML file (default: reports/team_simulation_report.html)")
    args = parser.parse_args()
    
    generate_html_report(args.results, args.output)
