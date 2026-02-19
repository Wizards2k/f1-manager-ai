#!/usr/bin/env python3
"""
Brake Component Validation Report Runner

Run this from the python_backend directory to generate comprehensive
brake validation reports.
"""
import sys
from pathlib import Path

# Add reports to path
REPORTS_PATH = Path(__file__).parent.parent / "reports" / "calibration"
sys.path.insert(0, str(REPORTS_PATH))

from brake_validation_report import main

if __name__ == "__main__":
    main()
