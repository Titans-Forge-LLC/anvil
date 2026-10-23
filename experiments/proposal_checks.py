"""Compatibility imports for the canonical installed check runner."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anvil_workbench.proposal_checks import *  # noqa: E402,F403
