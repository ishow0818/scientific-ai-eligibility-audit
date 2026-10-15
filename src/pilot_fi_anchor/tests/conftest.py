"""Make the repository root importable so tests can import pilot_fi_anchor."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
