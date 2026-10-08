"""Source-tree CLI; no package installation needed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from coverage_closure.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
