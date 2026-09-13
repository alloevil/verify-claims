"""Command line: run the receipts behind a claims.json file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import coverage, report, runner, schema
from .checks import exit_code_for

DEFAULT_FILES = (
    "claims.json",
    "docs/claims.json",
    ".claims/claims.json",
    "dist/claims.json",
)


def find_claims(explicit: str | None, root: Path) -> Path | None:
    """The claims file to use, or None (after printing why) when there is none."""
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            print(f"error: no such claims file: {path}", file=sys.stderr)
            return None
        return path
    for candidate in DEFAULT_FILES:
        path = root / candidate
        if path.exists():
            return path
    print(
        f"error: no claims file found under {root}; looked for {', '.join(DEFAULT_FILES)} "
        "(pass one explicitly)",
        file=sys.stderr,
    )
    return None


def cmd_list(args, root: Path, path: Path, doc: dict) -> int:
    claims = doc.get("claims", [])
    for claim in claims:
        check = claim.get("check") or {}
        kind = "manual" if check.get("manual") else "check"
        print(f"{claim.get('id', '?'):<32} {kind:<7} {claim.get('value', '')[:60]}")
    print(f"{len(claims)} claims in {path}")
    return 0


def cmd_check(args, root: Path, path: Path, doc: dict) -> int:
    errors = schema.validate_document(doc, path)
    for err in errors:
        print(f"error: {err}", file=sys.stderr)
    print(f"{path}: {len(doc.get('claims', []))} claims, {len(errors)} shape problem(s)")
    return 1 if errors else 0


def cmd_run(args, root: Path, path: Path, doc: dict) -> int:
    errors = schema.validate_document(doc, path)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print("refusing to run: fix the shape first (or run the `check` subcommand)", file=sys.stderr)
        return 2

    only = set(args.only.split(",")) if args.only else None
    skip = set(args.skip.split(",")) if args.skip else set()
    results = []
    for claim in doc["claims"]:
        cid = claim.get("id", "?")
        if only and cid not in only:
            continue
        if cid in skip:
            continue
        results.append(runner.run_claim(claim, root, args.timeout))

    project = doc.get("project") or path.parent.name
    as_of = next((str(doc[f]) for f in schema.DATE_FIELDS if isinstance(doc.get(f), str) and doc[f].strip()), "")
    if args.json:
        print(report.format_json(str(project), str(path), as_of, results, args.strict))
    else:
        print(report.format_text(str(project), str(path), as_of, results, args.strict))
    return exit_code_for(results, args.strict)


def cmd_coverage(args, root: Path, path: Path, doc: dict) -> int:
    """Which published numbers no claim covers — a to-do list, not a verdict."""
    readmes = [Path(r) for r in (args.readme or [])] or [r for r in (root / n for n in coverage.SCOPE) if r.exists()]
    if not readmes:
        print(f"no README found under {root} (looked for {', '.join(coverage.SCOPE)})", file=sys.stderr)
        return 2
    claims = doc.get("claims", [])
    total = len(claims)
    machine = sum(1 for c in claims if "manual" not in (c.get("check") or {}))
    print(f"coverage · {doc.get('project') or root.name} · {path}")
    print(f"  claims: {total} ({machine} machine-checked, {total - machine} manual)")
    grand_c = grand_u = 0
    for readme in readmes:
        covered, uncovered = coverage.report(readme, claims, args.first_screen)
        grand_c += len(covered)
        grand_u += len(uncovered)
        pct = round(100 * len(covered) / max(1, len(covered) + len(uncovered)))
        print(f"  {readme.name}: {len(covered)} covered · {len(uncovered)} unclaimed ({pct}% covered)")
        shown = uncovered if args.max == 0 else uncovered[: args.max]
        for m in shown:
            print(f"    L{m.line:<4} {m.number:<14} {m.text}")
        if args.max and len(uncovered) > args.max:
            print(f"    … {len(uncovered) - args.max} more")
    pct = round(100 * grand_c / max(1, grand_c + grand_u))
    print(f"  total: {grand_c} covered · {grand_u} unclaimed ({pct}% covered) — candidates, not verdicts")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify-claims",
        description="Run the receipts in a claims.json file: every published number carries a command that must still reproduce it.",
    )
    parser.add_argument("--root", default=".", help="repository root the commands run in (default: .)")
    parser.add_argument("-f", "--file", default=None, help="claims file (default: the first of " + ", ".join(DEFAULT_FILES) + ")")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run every claim's check")
    run.add_argument("--strict", action="store_true", help="also fail on claims marked manual (no machine check)")
    run.add_argument("--json", action="store_true", help="machine-readable report")
    run.add_argument("--timeout", type=float, default=runner.DEFAULT_TIMEOUT, help="per-command timeout in seconds")
    run.add_argument("--only", default=None, help="comma-separated claim ids to run")
    run.add_argument("--skip", default=None, help="comma-separated claim ids to skip")

    cov = sub.add_parser("coverage", help="report which numbers in the README nothing claims")
    cov.add_argument("--readme", action="append", default=None,
                     help="README to scan (repeatable; default: the ones that exist)")
    cov.add_argument("--first-screen", type=int, default=None, metavar="LINES",
                     help="only consider the first N lines (what a reader sees first)")
    cov.add_argument("--max", type=int, default=25, help="how many uncovered numbers to list (0 = all)")

    check = sub.add_parser("check", help="validate the shape only, run nothing")
    check.add_argument("--json", action="store_true", help="accepted for symmetry; output is text")
    sub.add_parser("list", help="list claims and whether each is machine-checked")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "run"
    if args.command is None:
        args.strict = False
        args.json = False
        args.timeout = runner.DEFAULT_TIMEOUT
        args.only = None
        args.skip = None

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"error: --root is not a directory: {root}", file=sys.stderr)
        return 2
    path = find_claims(args.file, root)
    if path is None:
        return 2

    try:
        doc = schema.load(path)
    except Exception as exc:  # malformed JSON is a reportable failure, not a traceback
        print(f"error: {path}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print(f"error: {path}: top level must be an object", file=sys.stderr)
        return 2

    if command == "list":
        return cmd_list(args, root, path, doc)
    if command == "coverage":
        return cmd_coverage(args, root, path, doc)
    if command == "check":
        return cmd_check(args, root, path, doc)
    return cmd_run(args, root, path, doc)


if __name__ == "__main__":
    raise SystemExit(main())
