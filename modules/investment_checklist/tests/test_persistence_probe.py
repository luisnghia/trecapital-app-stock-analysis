from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL not configured")
    return value


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["TREC_CHECKLIST_DATABASE_URL"] = _url()
    env["TREC_DEPLOYMENT_MARKER"] = "ci-process-a"
    return env


def test_persistence_probe_survives_new_python_process():
    script = "scripts/checklist_persistence_probe.py"
    first = subprocess.run(
        [sys.executable, script, "write"],
        cwd=Path.cwd(),
        env=_env(),
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr
    lines = [line.strip() for line in first.stdout.splitlines()]
    key_line = next((line for line in lines if line.startswith("PROBE_KEY=")), None)
    assert key_line, first.stdout
    key = key_line.split("=", 1)[1]

    second_env = _env()
    second_env["TREC_DEPLOYMENT_MARKER"] = "ci-process-b"
    second = subprocess.run(
        [sys.executable, script, "verify", "--probe-key", key],
        cwd=Path.cwd(),
        env=second_env,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, second.stderr
    assert "PERSISTENCE_OK" in second.stdout
    assert f"PROBE_KEY={key}" in second.stdout
    assert "DEPLOYMENT_MARKER=ci-process-a" in second.stdout
