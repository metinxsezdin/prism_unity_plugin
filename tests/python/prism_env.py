"""Makes the installed Prism's Scripts and Python libraries importable in tests.

Only modules that import Prism or Qt (the Prism_Unity_* plugin files) need this.
"""

import os
import sys

PRISM_ROOT = os.environ.get("PRISM_ROOT", r"C:\Program Files\Prism2")

_paths = [
    os.path.join(PRISM_ROOT, "Scripts"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python313"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python3"),
    os.path.join(PRISM_ROOT, "PythonLibs", "Python3", "PySide"),
]
for _p in reversed(_paths):
    if _p not in sys.path:
        sys.path.insert(1, _p)

PRISM_AVAILABLE = os.path.isdir(os.path.join(PRISM_ROOT, "Scripts"))
