"""Shared setup for the Prism MCP integration tests (real Prism, the test Prism project).

Run: $env:PRISM_UNITY_IT=1; tools/run_py_tests.ps1 -Pattern "test_*_it.py"
The test project comes from tools/make_test_prism_project.py.
"""

import os
import tempfile

from integration import test_products_it as products_it

RUN = products_it.RUN
SKIP_REASON = "set PRISM_UNITY_IT=1 and create the test Prism project"
TEST_PROJECT = products_it.TEST_PROJECT

_session = None


def session():
    """One Session over the one PrismCore this test process uses, pinned to the test project."""
    global _session
    if _session is None:
        from prism_mcp.session import Session

        _session = Session(core_factory=products_it.core, audit_path=os.path.join(tempfile.mkdtemp(), "audit.log"))
    return _session


def users_current_project():
    import json

    with open(os.path.expanduser("~/Documents/Prism2/Prism.json"), encoding="utf-8") as f:
        return json.load(f)["globals"]["current project"]
