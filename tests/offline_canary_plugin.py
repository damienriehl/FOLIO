"""Opt-in pytest guard and structured receipt for the offline canary."""

from __future__ import annotations

import json
import os
import socket
import subprocess
from pathlib import Path

_collected: list[str] = []
_outcomes: dict[str, str] = {}
_real_popen = subprocess.Popen


def _deny_network(*args, **kwargs):
    raise RuntimeError("offline canary denied network access")


def _guarded_popen(args, *pargs, **kwargs):
    command = [str(item) for item in (args if isinstance(args, (list, tuple)) else [args])]
    allowed = any(item.endswith("scripts/run_ontology_hydration_qa.py") for item in command) and "--replay" in command
    if not allowed:
        raise RuntimeError(f"offline canary denied unexpected child command: {command[0]}")
    return _real_popen(args, *pargs, **kwargs)


def pytest_configure(config):
    socket.socket.connect = _deny_network
    socket.create_connection = _deny_network
    subprocess.Popen = _guarded_popen


def pytest_collection_finish(session):
    _collected.extend(item.nodeid for item in session.items)


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    if hasattr(report, "wasxfail"):
        outcome = "xpassed" if report.passed else "xfailed"
    else:
        outcome = report.outcome
    _outcomes[report.nodeid] = outcome


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("FOLIO_OFFLINE_RECEIPT")
    if path:
        Path(path).write_text(json.dumps({"collected": _collected, "outcomes": _outcomes}, sort_keys=True))
