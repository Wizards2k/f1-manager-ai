#!/usr/bin/env python3
# Convert GeoJSON circuits to SVG paths

import json
import os
import math

def geojson_to_svg(geojson_file, output_file):
    """Convert GeoJSON circuit to SVG path"""
    
    with open(geojson_file, 'r') as f:
        data = json.load(f)
    
    # Extract coordinates - handle different GeoJSON structures
    coords = []
    
    if data['type'] == 'Feature':
        geometry = data['geometry']
        if geometry['type'] == 'LineString':
            coords = geometry['coordinates']
        elif geometry['type'] == 'MultiLineString':
            coords = geometry['coordinates'][0]  # Take first line
    elif data['type'] == 'LineString':
        coords = data['coordinates']
    elif data['type'] == 'MultiLineString':
        coords = data['coordinates'][0]
    
    if not coords:
        print(f"❌ No coordinates found in {geojson_file}")
        return None
    
    # Validate coordinates format
    if len(coords) > 0 and isinstance(coords[0], list) and len(coords[0]) >= 2:
        # Valid coordinate format [lon, lat]
        pass
    else:
        print(f"❌ Invalid coordinate format in {geojson_file}")
        return None
    
    # Find bounds
    lons = [coord[0] for coord in coords]
    lats = [coord[1] for coord in coords]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    
    # Calculate scale to fit 200x120 viewBox
    width = 200
    height = 120
    padding = 20
    
    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat
    
    scale_x = (width - 2 * padding) / lon_range
    scale_y = (height - 2 * padding) / lat_range
    scale = min(scale_x, scale_y)
    
    # Convert coordinates to SVG path
    svg_coords = []
    for i, coord in enumerate(coords):
        if i % 5 == 0:  # Sample every 5th point to reduce complexity
            x = (coord[0] - min_lon) * scale + padding
            y = height - ((coord[1] - min_lat) * scale + padding)
            svg_coords.append((x, y))
    
    # Create SVG path
    if svg_coords:
        path_data = f"M {svg_coords[0][0]:.1f} {svg_coords[0][1]:.1f}"
        for x, y in svg_coords[1:]:
            path_data += f" L {x:.1f} {y:.1f}"
        
        # Close the path
        path_data += f" L {svg_coords[0][0]:.1f} {svg_coords[0][1]:.1f}"
        
        svg = f'<svg viewBox="0 0 {width} {height}"><path d="{path_data}" stroke="#e10600" stroke-width="3" fill="none" stroke-linejoin="round"/></svg>'
        
        # Save SVG
        with open(output_file, 'w') as f:
            f.write(svg)
        
        print(f"✅ Created: {output_file}")
        return svg
    else:
        print(f"❌ No coordinates found in {geojson_file}")
        return None

def convert_all_circuits():
    """Convert all F1 2025 circuits"""
    
    circuits_dir = "/Users/wizards/Desktop/Sviluppo/F1 Manager AI/circuits"
    svg_dir = "/Users/wizards/Desktop/Sviluppo/F1 Manager AI/circuits/svg"
    
    # Create SVG directory
    os.makedirs(svg_dir, exist_ok=True)
    
    # F1 2025 circuits
    f1_2025_circuits = [
        'au-1953_melbourne.json',
        'cn-2004_shanghai.json', 
        'jp-1962_suzuka.json',
        'bh-2002_sakhir.json',
        'sa-2021_jeddah.json',
        'us-2022_miami.json',
        'it-1953_imola.json',
        'mc-1929_monaco.json',
        'es-1991_barcelona.json',
        'ca-1978_montreal.json',
        'at-1969_spielberg.json',
        'gb-1948_silverstone.json',
        'be-1925_spa_francorchamps.json',
        'hu-1986_budapest.json',
        'nl-1948_zandvoort.json',
        'it-1922_monza.json',
        'sg-2008_singapore.json',
        'us-2012_austin.json',
        'mx-1962_mexico_city.json',
        'br-1940_sao_paulo.json',
        'qa-2004_lusail.json',
        'az-2016_baku.json',
        'us-2023_las_vegas.json',
        'ae-2009_yas_marina.json'
    ]
    
    svg_results = {}
    
    for circuit_file in f1_2025_circuits:
        input_path = os.path.join(circuits_dir, circuit_file)
        svg_filename = circuit_file.replace('.json', '.svg')
        output_path = os.path.join(svg_dir, svg_filename)
        
        if os.path.exists(input_path):
            svg = geojson_to_svg(input_path, output_path)
            if svg:
                circuit_id = circuit_file.replace('.json', '')
                svg_results[circuit_id] = svg
        else:
            print(f"❌ File not found: {input_path}")
    
    # Save results as JavaScript
    js_content = "// Auto-generated SVG circuits from GeoJSON\n"
    js_content += "const circuitSvgs = {\n"
    
    for circuit_id, svg in svg_results.items():
        js_content += f"  '{circuit_id}': `{svg}`,\n"
    
    js_content += "};\n"
    
    with open(os.path.join(svg_dir, 'circuits_svg.js'), 'w') as f:
        f.write(js_content)
    
    print(f"\n🎯 Converted {len(svg_results)} circuits to SVG")
    print(f"📁 SVG files saved in: {svg_dir}")
    print(f"📄 JavaScript file: circuits_svg.js")

if __name__ == "__main__":
    convert_all_circuits()
