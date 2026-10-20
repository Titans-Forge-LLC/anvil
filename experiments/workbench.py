"""Compatibility launcher for source checkouts. Prefer anvil-workbench after install."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anvil_workbench.workbench import *  # noqa: E402,F403 - legacy public imports


if __name__ == '__main__':
    main()
