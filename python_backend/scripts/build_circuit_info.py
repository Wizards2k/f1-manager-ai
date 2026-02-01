#!/usr/bin/env python3
"""Utility per generare il file circuit_info.json combinando settori e parametri legacy."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SECTORS_FILE = BASE_DIR / "sectors_config.json"
OUTPUT_FILE = BASE_DIR / "config" / "circuit_info.json"
TMP_DIR = Path("tmp/legacy_circuits")
TMP_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_PARAM_URL = (
    "https://raw.githubusercontent.com/Wizards2k/F1-Manager-Simulator/"
    "master/Resources/Telemetry/Circuit_data/legacy_parameters_report.json"
)
TELEMETRY_BASE_URL = (
    "https://raw.githubusercontent.com/Wizards2k/F1-Manager-Simulator/"
    "master/Resources/Telemetry/"
)


@dataclass
class CircuitSource:
    legacy_code: str
    telemetry_file: str


CIRCUIT_MAPPING: dict[str, CircuitSource] = {
    "at-1969_spielberg": CircuitSource("austria", "austria_2024_Q.json"),
    "au-1953_melbourne": CircuitSource("australia", "australia_2024_Q.json"),
    "az-2016_baku": CircuitSource("azerbaijan", "azerbaijan_2024_Q.json"),
    "be-1925_spa_francorchamps": CircuitSource("belgium", "belgium_2024_Q.json"),
    "bh-2002_sakhir": CircuitSource("bahrain", "bahrain_2024_Q.json"),
    "br-1940_sao_paulo": CircuitSource("brazil", "brazil_2024_Q.json"),
    "ca-1978_montreal": CircuitSource("canada", "canada_2024_Q.json"),
    "cn-2004_shanghai": CircuitSource("china", "china_2024_Q.json"),
    "es-1991_barcelona": CircuitSource("spain", "spain_2024_Q.json"),
    "gb-1948_silverstone": CircuitSource("great_britain", "britain_2024_Q.json"),
    "hu-1986_budapest": CircuitSource("hungary", "hungary_2024_Q.json"),
    "it-1922_monza": CircuitSource("italy", "italy_2024_Q.json"),
    "it-1953_imola": CircuitSource("italy_imola", "emilia_romagna_2024_Q.json"),
    "jp-1962_suzuka": CircuitSource("japan", "japan_2024_Q.json"),
    "mc-1929_monaco": CircuitSource("monaco", "monaco_2024_Q.json"),
    "mx-1962_mexico_city": CircuitSource("mexico", "mexico_2024_Q.json"),
    "nl-1948_zandvoort": CircuitSource("netherlands", "netherlands_2024_Q.json"),
    "sa-2021_jeddah": CircuitSource("saudi_arabia", "saudi_arabia_2024_Q.json"),
    "sg-2008_singapore": CircuitSource("singapore", "singapore_2024_Q.json"),
    "us-2012_austin": CircuitSource("usa", "usa_2024_Q.json"),
    "us-2022_miami": CircuitSource("miami", "miami_2024_Q.json"),
}


def download_json(url: str, destination: Path) -> dict:
    if not destination.exists():
        print(f"Downloading {url} -> {destination}")
        urllib.request.urlretrieve(url, destination)
    return json.loads(destination.read_text())


def load_legacy_parameters() -> dict[str, dict]:
    legacy_path = TMP_DIR / "legacy_parameters_report.json"
    data = download_json(LEGACY_PARAM_URL, legacy_path)
    return {entry["circuit_code"]: entry for entry in data}


def load_telemetry(filename: str) -> dict:
    local_path = TMP_DIR / filename
    return download_json(TELEMETRY_BASE_URL + filename, local_path)


def build_circuit_info():
    sectors_data = json.loads(SECTORS_FILE.read_text())
    legacy_params = load_legacy_parameters()

    output: dict[str, dict] = {}
    missing_sources: list[str] = []

    for circuit_id, sector_entry in sectors_data.items():
        source = CIRCUIT_MAPPING.get(circuit_id)
        if not source:
            missing_sources.append(circuit_id)
            continue

        telemetry = load_telemetry(source.telemetry_file)
        try:
            s1 = float(telemetry["Sector1Time"])
            s2 = float(telemetry["Sector2Time"])
            s3 = float(telemetry["Sector3Time"])
        except KeyError as exc:
            raise KeyError(f"Missing sector time in {source.telemetry_file}: {exc}")

        legacy = legacy_params.get(source.legacy_code, {})

        entry = {
            "name": sector_entry.get("name"),
            "total_length": sector_entry.get("total_length"),
            "sectors": sector_entry.get("sectors"),
            "sector_times": {
                "s1": round(s1, 3),
                "s2": round(s2, 3),
                "s3": round(s3, 3),
            },
            "base_lap_seconds": round(s1 + s2 + s3, 3),
            "lap_reference": {
                "session": telemetry.get("SessionType"),
                "year": telemetry.get("Year"),
                "driver": telemetry.get("Driver"),
            },
            "surface": {
                "reference_grip": legacy.get("reference_grip"),
                "grip_multiplier": legacy.get("grip_multiplier"),
                "base_grip_coefficient": legacy.get("base_grip_coefficient"),
                "corner_speed_multiplier": legacy.get("corner_speed_multiplier"),
                "braking_multiplier": legacy.get("braking_multiplier"),
                "acceleration_multiplier": legacy.get("acceleration_multiplier"),
                "circuit_smoothness": legacy.get("circuit_smoothness"),
                "circuit_bumpiness": legacy.get("circuit_bumpiness"),
                "downforce_importance": legacy.get("downforce_importance"),
                "aerodynamic_drag": legacy.get("aerodynamic_drag"),
                "time_multiplier": legacy.get("time_multiplier"),
            },
            "tire_multipliers": {
                "soft": legacy.get("soft_tire_multiplier"),
                "medium": legacy.get("medium_tire_multiplier"),
                "hard": legacy.get("hard_tire_multiplier"),
            },
        }

        output[circuit_id] = entry

    if missing_sources:
        print("Warning: no mapping for:", ", ".join(sorted(missing_sources)))

    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {OUTPUT_FILE} with {len(output)} circuits")


if __name__ == "__main__":
    build_circuit_info()
