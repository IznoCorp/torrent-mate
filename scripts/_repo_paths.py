"""Where the repository keeps the maquette and the contract, named once.

The guards under ``scripts/`` and the tests that read the maquette each used to
spell ``ROOT / "frontend" / "maquette"`` themselves, so moving the maquette meant
finding every copy. They import these constants instead, and a move edits this
file alone.

The harness under ``frontend/maquette/harness`` does not import it: it runs from
a served copy outside the checkout, where ``scripts/`` is not beside it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MAQUETTE = ROOT / "frontend" / "maquette"
DESIGN = MAQUETTE / "design"
DESIGN_SRC = DESIGN / "src"
HARNESS = MAQUETTE / "harness"
CONTRACT_DIR = ROOT / "contract"
CONTRACT = CONTRACT_DIR / "openapi.json"
SERVED_CONTRACT = CONTRACT_DIR / "openapi.generated.json"
