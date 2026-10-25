"""`npx compliancelint init` brings the scanner to the npm package's version (series-2 take, 2026-10-24, QA #33).

init found an older pip install (1.3.1) and used it as it was, while the npm package was 1.3.3: the take machine ran
an old scanner without any notice. Now an older pip-installed scanner is upgraded to the package's version (or init
warns with the command when the upgrade fails), and the uvx configuration names the package's version.

The functions are tested through node (bin/init.js exports them when it is required instead of run).
"""
import json
import os
import shutil
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INIT = os.path.join(REPO, "bin", "init.js").replace("\\", "/")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _node(script: str):
    out = subprocess.run(["node", "-e", f"const init = require({json.dumps(INIT)});\n{script}"],
                         capture_output=True, text=True, timeout=60, cwd=REPO)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_requiring_init_does_not_run_it():
    assert _node("console.log(JSON.stringify(Object.keys(init).sort()))") == sorted(
        ["compareVersions", "ensureScannerVersion", "uvxConfig", "PACKAGE_VERSION"])


def test_compare_versions():
    assert _node("console.log(JSON.stringify([init.compareVersions('1.3.1', '1.3.3'), "
                 "init.compareVersions('1.3.10', '1.3.3'), init.compareVersions('1.3.3', '1.3.3')]))") == [-1, 1, 0]


def test_an_older_scanner_is_upgraded_to_the_package_version():
    calls, note = _node(
        "const calls = []; const note = init.ensureScannerVersion('1.3.1', '1.3.4', (cmd) => calls.push(cmd));"
        "console.log(JSON.stringify([calls, note]))")
    assert calls == ["pip install --upgrade compliancelint==1.3.4"]
    assert "1.3.1" in note and "1.3.4" in note


def test_the_same_or_a_newer_scanner_is_left_alone():
    assert _node(
        "const calls = []; const a = init.ensureScannerVersion('1.3.4', '1.3.4', (c) => calls.push(c));"
        "const b = init.ensureScannerVersion('1.4.0', '1.3.4', (c) => calls.push(c));"
        "console.log(JSON.stringify([calls, a, b]))") == [[], None, None]


def test_a_failed_upgrade_warns_with_the_command():
    note = _node(
        "const note = init.ensureScannerVersion('1.3.1', '1.3.4', () => { throw new Error('no pip'); });"
        "console.log(JSON.stringify(note))")
    assert "pip install --upgrade compliancelint==1.3.4" in note


def test_uvx_runs_the_package_version():
    cfg = _node("console.log(JSON.stringify(init.uvxConfig('1.3.4')))")
    assert cfg["command"] == "uvx"
    assert cfg["args"] == ["--from", "compliancelint==1.3.4", "compliancelint-server"]


def test_package_version_is_the_package_json_version():
    with open(os.path.join(REPO, "package.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    assert _node("console.log(JSON.stringify(init.PACKAGE_VERSION))") == version
