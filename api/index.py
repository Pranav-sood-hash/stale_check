import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)
_backend = os.path.join(_root, "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from backend.main import api, app

__all__ = ["api", "app"]

