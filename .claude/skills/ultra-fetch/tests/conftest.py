"""Put the skill's scripts/ directory on sys.path so `ultra_fetch` imports.

The package is deliberately not installed (it is not a distributable), so tests
locate it by path rather than by import machinery.
"""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
