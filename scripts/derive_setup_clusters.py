import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple


def load_json(path: Path) -> Dict:
    with path.open() as fp:
        return json.load(fp)


def avg(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return float(ordered[int(k)])
    d0 = ordered[f] * (c - k)
    d1 = ordered[c] * (k - f)
    return float(d0 + d1)


STOPWORDS = {
    "circuit",
    "circuito",
    "international",
    "grand",
    "prix",
    "course",
    "street",
    "strip",
    "track",
    "autodromo",
    "autodrome",
    "city",
    "gp",
    "de",
    "di",
    "the",
    "of",
    "international",
    "racing",
}


GP_TO_TELEMETRY = {
    "australia": "Albert Park Grand Prix Circuit",
    "china": "Shanghai International Circuit",
    "japan": "Suzuka International Racing Course",
    "bahrain": "Bahrain International Circuit",
    "saudi arabia": "Jeddah Corniche Circuit",
    "miami": "Miami International Autodrome",
    "emilia-romagna": "Autodromo Enzo e Dino Ferrari",
    "monaco": "Circuit de Monaco",
    "spain": "Circuit de Barcelona-Catalunya",
    "canada": "Circuit Gilles-Villeneuve",
    "austria": "Red Bull Ring",
    "great britain": "Silverstone Circuit",
    "belgium": "Circuit de Spa-Francorchamps",
    "hungary": "Hungaroring",
    "netherlands": "Circuit Zandvoort",
    "italy": "Autodromo Nazionale di Monza",
    "azerbaijan": "Baku City Circuit",
    "singapore": "Marina Bay Street Circuit",
    "usa": "Circuit of the Americas",
    "united states": "Circuit of the Americas",
    "mexico": "Autódromo Hermanos Rodríguez",
    "brazil": "Interlagos",
    "las vegas": "Las Vegas Strip Circuit",
    "qatar": "Lusail International Circuit",
    "abu dhabi": "Yas Marina Circuit",
}


def normalize_key(value: str) -> str:
    if not value:
        return ""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", ascii_value.lower())
        if token and token not in STOPWORDS
    ]
    return "".join(tokens)


def classify_curve_by_speed(speed: float) -> str:
    if speed <= 0:
        return "unknown"
    if speed < 80:
        return "v_slow"
    if speed < 130:
        return "low"
    if speed < 200:
        return "medium"
    if speed < 270:
        return "high"
    return "ultra"


def classify_load(straight_pct: float, fast_speed: float, slow_speed: float, heavy_brakes: int) -> str:
    if 0.45 <= straight_pct <= 0.65 and heavy_brakes >= 5 and slow_speed < 115:
        return "street_hybrid"
    if straight_pct >= 0.68 and fast_speed >= 235:
        return "low_drag"
    if straight_pct <= 0.4 or fast_speed < 215:
        return "high_df"
    if straight_pct <= 0.5 or fast_speed < 230:
        return "medium_high_df"
    if straight_pct <= 0.58:
        return "medium_low_df"
    return "balanced"


def classify_surface(surface_info: Dict, bump_sections: List[float], bump_count: int) -> str:
    surface_bump = surface_info.get("circuit_bumpiness")
    bump_avg = avg(bump_sections)
    if bump_count >= 4 or (surface_bump and surface_bump >= 18):
        return "bumpy"
    if bump_avg and bump_avg >= 12:
        return "bumpy"
    return "smooth"


def classify_climate(weather: Dict) -> str:
    track = weather.get("track_temp_c") or []
    if track:
        t_min, t_max = track[0], track[-1]
        if t_max >= 45:
            return "hot"
        if t_min <= 25:
            return "cool"
        return "temperate"
    air = weather.get("air_temp_c") or []
    if air:
        a_min, a_max = air[0], air[-1]
        if a_max >= 35:
            return "hot"
        if a_min <= 18:
            return "cool"
        return "temperate"
    return "unknown"


def extract_metrics(telemetry: Dict) -> Tuple[Dict, str, str, str]:
    sections = telemetry.get("geometry", {}).get("sections", [])
    straight_m = 0.0
    corner_m = 0.0
    slow_speeds: List[float] = []
    medium_speeds: List[float] = []
    fast_speeds: List[float] = []
    flatout_speeds: List[float] = []
    bumpiness_values: List[float] = []
    bumpiness_count = 0
    heavy_brakes = 0

    for section in sections:
        start = section.get("start_m") or 0.0
        end = section.get("end_m") or start
        length = max(0.0, float(end) - float(start))
        kind = (section.get("kind") or "").lower()
        avg_speed = float(section.get("avg_speed") or 0.0)
        bumpiness = section.get("bumpiness")
        if bumpiness is not None:
            bumpiness_values.append(float(bumpiness))
            if float(bumpiness) >= 12:
                bumpiness_count += 1
        if "straight" in kind:
            straight_m += length
        else:
            corner_m += length
            classification = classify_curve_by_speed(avg_speed)
            if classification in {"v_slow", "low"}:
                slow_speeds.append(avg_speed)
                heavy_brakes += 1
            elif classification == "medium":
                medium_speeds.append(avg_speed)
            elif classification == "high":
                fast_speeds.append(avg_speed)
            elif classification == "ultra":
                flatout_speeds.append(avg_speed)
            else:
                medium_speeds.append(avg_speed)

    total_m = straight_m + corner_m or 1.0
    straight_pct = straight_m / total_m
    corner_pct = corner_m / total_m
    load_class = classify_load(straight_pct, avg(fast_speeds), avg(slow_speeds), heavy_brakes)
    surface_class = classify_surface(telemetry.get("surface", {}), bumpiness_values, bumpiness_count)
    climate_class = classify_climate(telemetry.get("weather", {}))

    metrics = {
        "straight_pct": round(straight_pct, 3),
        "corner_pct": round(corner_pct, 3),
        "avg_slow_corner_speed": round(avg(slow_speeds), 1),
        "avg_medium_corner_speed": round(avg(medium_speeds), 1),
        "avg_fast_corner_speed": round(avg(fast_speeds), 1),
        "avg_flatout_corner_speed": round(avg(flatout_speeds), 1),
        "p95_corner_speed": round(percentile(slow_speeds + medium_speeds + fast_speeds, 0.95), 1),
        "heavy_brake_events": heavy_brakes,
        "bumpiness_avg": round(avg(bumpiness_values), 2) if bumpiness_values else None,
        "bump_sections": bumpiness_count,
        "track_temp_range": telemetry.get("weather", {}).get("track_temp_c"),
        "air_temp_range": telemetry.get("weather", {}).get("air_temp_c"),
    }
    return metrics, load_class, surface_class, climate_class


def main():
    parser = argparse.ArgumentParser(description="Derive setup clusters from telemetry files")
    parser.add_argument("--circuits", default="python_backend/data/circuits", help="Directory with *_Telemetry.json files")
    parser.add_argument("--output", default="tmp/setup_cluster_report.json", help="Destination JSON report")
    parser.add_argument(
        "--track-profile",
        default="config/pirelli_track_profile_2025.json",
        help="JSON file with Pirelli track profile + prescriptions",
    )
    args = parser.parse_args()

    circuits_dir = Path(args.circuits)
    telemetry_files = sorted(circuits_dir.glob("*_Telemetry.json"))

    track_profile_path = Path(args.track_profile)
    track_profile = load_json(track_profile_path) if track_profile_path.exists() else {}
    pirelli_meta = {}
    for item in track_profile.get("calendar", []):
        keys = set()
        circuit_name = item.get("circuit")
        if circuit_name:
            keys.add(normalize_key(circuit_name))
        gp_name = item.get("gp")
        if gp_name:
            mapped = GP_TO_TELEMETRY.get(gp_name.lower())
            if mapped:
                keys.add(normalize_key(mapped))
            keys.add(normalize_key(gp_name))
        for key in keys:
            if key:
                pirelli_meta[key] = item

    report = []
    for tf in telemetry_files:
        telemetry = load_json(tf)
        metrics, load_class, surface_class, climate_class = extract_metrics(telemetry)
        circuit_name = telemetry.get("metadata", {}).get("circuit_name")
        pirelli_profile = pirelli_meta.get(normalize_key(circuit_name), {})
        record = {
            "circuit_id": telemetry.get("metadata", {}).get("circuit_id"),
            "circuit_name": circuit_name,
            "load_class": load_class,
            "surface_class": surface_class,
            "climate_class": climate_class,
            "metrics": metrics,
            "pirelli_profile": {
                "track_category": pirelli_profile.get("track_category"),
                "corner_distribution": pirelli_profile.get("corner_distribution"),
                "tyre_nomination": pirelli_profile.get("nomination"),
                "wear_rate_base": pirelli_profile.get("wear_rate_base"),
                "lap_time_delta_hint": pirelli_profile.get("lap_time_delta_hint"),
                "track_features": pirelli_profile.get("track_features"),
                "notes": pirelli_profile.get("notes"),
                "pirelli_prescriptions": pirelli_profile.get("pirelli_prescriptions"),
                "energy_management": pirelli_profile.get("energy_management"),
                "gear_profile": pirelli_profile.get("gear_profile"),
                "weather_impact": pirelli_profile.get("weather_impact"),
            },
        }
        report.append(record)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fp:
        json.dump(report, fp, indent=2)

    print(f"Wrote {len(report)} circuit records to {output_path}")


if __name__ == "__main__":
    main()
