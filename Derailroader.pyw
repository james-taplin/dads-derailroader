"""Double-click launcher for the source distribution (Python 3.11+ with Tk)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rr2dv.gui import main

raise SystemExit(main())
