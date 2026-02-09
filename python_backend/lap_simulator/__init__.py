"""
LapSimulator – standalone physics engine for F1 Manager AI.

Implements the 8-step update_section() loop described in
docs/lap-physics-spec-v0.5.md (§3.3) and the LapSimulator runtime
loop (§3.3.1): InputMixer → update_section × N → StateCommit.

This package is intentionally decoupled from the existing RaceEngine
so it can be developed, tested and validated independently.
"""
