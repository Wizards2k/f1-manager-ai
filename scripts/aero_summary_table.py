#!/usr/bin/env python3
"""
Generate a summary table of DF/drag values for the first 5 teams
"""

import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'python_backend'))

from tmp_data.cars_2025 import CARS_2025

def print_aero_summary():
    print("=== AERO COMPONENTS SUMMARY (First 5 Teams) ===")
    print()
    
    # Component order for display
    components = [
        ("Front Wing", "ala_anteriore"),
        ("Front Floor", "fondo_anteriore"),
        ("Rear Wing", "ala_posteriore"),
        ("Rear Floor", "fondo_posteriore"),
        ("Beam Wing", "beam_wing"),
        ("B Wing", "b_wing"),
        ("Engine Cover", "cofano_motore"),
        ("Sidepods", "sidepods"),
    ]
    
    # Teams to display
    teams = ['MCL', 'RBR', 'FER', 'MER', 'AST']
    
    # Header
    header = "Component".ljust(15)
    for team in teams:
        header += f" | {team:8} DF | {team:8} DR"
    print(header)
    print("-" * len(header))
    
    # Per-component values
    for comp_name, comp_attr in components:
        row = comp_name.ljust(15)
        for team in teams:
            car = CARS_2025[team]
            comp = getattr(car.aero_package, comp_attr, None)
            if comp:
                df_val = comp.df_coeff * 1000  # Convert back to kgf
                drag_val = comp.drag_coeff
                row += f" | {df_val:8.2f} | {drag_val:8.4f}"
            else:
                row += " |      N/A |      N/A"
        print(row)
    
    print("-" * len(header))
    
    # Totals per team
    totals_row = "TOTAL".ljust(15)
    for team in teams:
        car = CARS_2025[team]
        total_df = 0
        total_drag = 0
        
        for _, comp_attr in components:
            comp = getattr(car.aero_package, comp_attr, None)
            if comp:
                total_df += comp.df_coeff * 1000
                total_drag += comp.drag_coeff
        
        # Calculate front/rear ratio
        front_df = car.aero_package.ala_anteriore.df_coeff * 1000 + car.aero_package.fondo_anteriore.df_coeff * 1000
        rear_df = car.aero_package.ala_posteriore.df_coeff * 1000 + car.aero_package.fondo_posteriore.df_coeff * 1000
        if car.aero_package.beam_wing:
            rear_df += car.aero_package.beam_wing.df_coeff * 1000
        if car.aero_package.b_wing:
            rear_df += car.aero_package.b_wing.df_coeff * 1000
        if car.aero_package.cofano_motore:
            rear_df += car.aero_package.cofano_motore.df_coeff * 1000
        if car.aero_package.sidepods:
            rear_df += car.aero_package.sidepods.df_coeff * 1000
        
        front_pct = (front_df / total_df * 100) if total_df > 0 else 0
        rear_pct = (rear_df / total_df * 100) if total_df > 0 else 0
        
        totals_row += f" | {total_df:8.2f} | {total_drag:8.4f}"
        print(f"Front/Rear DF for {team}: {front_pct:.1f}% / {rear_pct:.1f}%")
    
    print(totals_row)
    print()
    
    # Component scores summary
    print("=== COMPONENT QUALITY SCORES (DF) ===")
    score_header = "Component".ljust(15)
    for team in teams:
        score_header += f" | {team:8}"
    print(score_header)
    print("-" * len(score_header))
    
    for comp_name, comp_attr in components:
        score_row = comp_name.ljust(15)
        for team in teams:
            car = CARS_2025[team]
            comp = getattr(car.aero_package, comp_attr, None)
            if comp:
                score = comp.component_score_df
                score_row += f" | {score:8.1f}"
            else:
                score_row += " |      N/A"
        print(score_row)
    
    print("-" * len(score_header))
    print()

if __name__ == "__main__":
    print_aero_summary()
