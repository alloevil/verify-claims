"""Text and JSON reports."""

from __future__ import annotations

import json

from .checks import CheckResult, summarise

MARK = {"ok": "ok  ", "fail": "FAIL", "error": "ERR ", "manual": "    "}
EXIT = {"ok": 0, "fail": 1, "error": 1, "manual": 0}


def _one_line(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_text(project: str, source: str, as_of: str, results: list[CheckResult], strict: bool) -> str:
    counts = summarise(results)
    head = f"verify-claims · {project} · as of {as_of}" if as_of else f"verify-claims · {project}"
    lines = [head, f"  source: {source}"]
    for r in results:
        detail = r.detail
        if r.status == "manual":
            detail = f"not machine-checked — {detail}"
        elif r.status == "ok":
            detail = f"{r.duration_s:.1f}s"
        elif r.status in ("fail", "error"):
            detail = f"[{r.status}] {detail}"
            if r.exit_code not in (None, 0):
                detail += f" (exit {r.exit_code})"
        lines.append(f"  {MARK.get(r.status, '?')} {r.claim_id:<32} {_one_line(detail)}")
    lines.append(
        f"  {counts['checked']} machine-checked · {counts['ok']} ok · {counts['fail']} failed · "
        f"{counts['error']} error · {counts['manual']} manual"
    )
    if counts["fail"] or counts["error"]:
        lines.append("  FAILED — a published number no longer reproduces; fix the number or the code, not the gate.")
    elif counts["manual"] and strict:
        lines.append("  FAILED (strict) — claims without a machine check are failures in strict mode.")
    elif counts["manual"]:
        lines.append("  passed; the manual entries above are the remaining gap (run with --strict to fail on them).")
    else:
        lines.append("  passed — every published number reproduced.")
    return "\n".join(lines)


def format_json(project: str, source: str, as_of: str, results: list[CheckResult], strict: bool) -> str:
    counts = summarise(results)
    return json.dumps(
        {
            "project": project,
            "source": source,
            "as_of": as_of,
            "strict": strict,
            "summary": counts,
            "claims": [
                {
                    "id": r.claim_id,
                    "status": r.status,
                    "detail": r.detail,
                    "cmd": r.cmd,
                    "exit_code": r.exit_code,
                    "duration_s": round(r.duration_s, 3),
                    "failures": r.failures,
                }
                for r in results
            ],
        },
        indent=2,
        ensure_ascii=False,
    )
