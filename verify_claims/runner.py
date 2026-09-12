"""Command execution for a claim's receipt."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from .checks import CheckResult, evaluate

DEFAULT_TIMEOUT = 120.0


def run_commands(cmds: list[str], cwd: Path, timeout: float) -> tuple[int, str, str, float]:
    """Run each command in turn through the shell; return the last one's result.

    Sequential commands are for setup steps (e.g. build then print), which is why
    only the final command's output is matched.
    """
    code, out, err, elapsed = 1, "", "", 0.0
    for cmd in cmds:
        started = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy(),
            )
            code, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            out = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            err = f"timed out after {timeout:g}s"
            return 124, out, err, elapsed
        elapsed = time.monotonic() - started
        if code != 0:
            break
    return code, out, err, elapsed


def run_claim(claim: dict, root: Path, default_timeout: float) -> CheckResult:
    cid = str(claim.get("id", "?"))
    check = claim.get("check") or {}

    if check.get("manual"):
        return CheckResult(claim_id=cid, status="manual", detail=str(check["manual"]))

    raw_cmd = check.get("cmd")
    cmds = [raw_cmd] if isinstance(raw_cmd, str) else list(raw_cmd or [])
    if not cmds:
        return CheckResult(claim_id=cid, status="error", detail="no command to run")

    cwd = root / check["dir"] if check.get("dir") else root
    timeout = float(check.get("timeout", default_timeout))
    code, out, err, elapsed = run_commands(cmds, cwd, timeout)

    if code == 124:
        return CheckResult(cid, "error", f"timed out after {timeout:g}s", cmds[-1], code, elapsed, out, err)

    failures = evaluate(out, code, check.get("expect"))
    if failures:
        detail = "; ".join(failures)
        status = "error" if code not in (0, (check.get("expect") or {}).get("exit_code", 0)) else "fail"
        return CheckResult(cid, status, detail, cmds[-1], code, elapsed, out, err, failures)
    return CheckResult(cid, "ok", "", cmds[-1], code, elapsed, out, err)
