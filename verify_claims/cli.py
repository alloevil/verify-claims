"""Command line: run the receipts behind a claims.json file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import coverage, index_page, report, runner, schema
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


def cmd_index(args, root: Path, path: Path, doc: dict) -> int:
    """One page summarising every guarded repository, built from their own claims files."""
    import datetime
    import urllib.request

    repos = list(args.repo or [])
    list_file = Path(args.list_file) if args.list_file else root / "docs" / "repos.txt"
    if not repos and list_file.exists():
        repos = [ln.strip() for ln in list_file.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.startswith("#")]
    if not repos:
        print("no repositories: pass --repo owner/name or provide --list-file", file=sys.stderr)
        return 2

    def fetch(url: str) -> str:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - fixed https URL
            return r.read().decode("utf-8")

    rows = []
    for repo in repos:
        short = repo.split("/")[-1]
        if args.path:
            local = Path(args.path) / short
            candidates = [local / "claims.json", local / "docs" / "claims.json",
                          local / ".claims" / "claims.json", local / "dist" / "claims.json"]
            source = next((str(c) for c in candidates if c.exists()), None)
            if source is None:
                rows.append(index_page.Row(short, repo, None, None, None, "-", "no local claims file"))
                continue
        else:
            source = f"https://raw.githubusercontent.com/{repo}/{args.ref}/claims.json"
        try:
            if args.path:
                doc_j = index_page.read_claims(source, fetch=fetch)
            else:
                doc_j = None
                last = None
                for rel in ("claims.json", "docs/claims.json", ".claims/claims.json",
                            "dist/claims.json"):
                    url = f"https://raw.githubusercontent.com/{repo}/{args.ref}/{rel}"
                    try:
                        doc_j = index_page.read_claims(url, fetch=fetch)
                        break
                    except Exception as exc:  # try the next documented location
                        last = exc
                if doc_j is None:
                    raise last if last else RuntimeError("no claims file found")
        except Exception as exc:  # unreachable file, invalid JSON, network down
            rows.append(index_page.Row(short, repo, None, None, None, "-", f"{type(exc).__name__}"))
            continue
        rows.append(index_page.row_for(repo, doc_j))

    note = args.note or (f"read from local clones under `{args.path}`" if args.path
                         else f"read from `raw.githubusercontent.com` at `{args.ref}`")
    text = index_page.render(rows, datetime.date.today().isoformat(), note)
    if args.out == "-":
        print(text)
    else:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out} · {len(text.splitlines())} lines")
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

    idx = sub.add_parser("index", help="render one page covering every guarded repository")
    idx.add_argument("--repo", action="append", default=None,
                     help="owner/name (repeatable); default: read the list from --list-file")
    idx.add_argument("--list-file", default=None, help="one owner/name per line")
    idx.add_argument("--ref", default="HEAD", help="git ref to fetch (default HEAD; pin a tag for a fixed page)")
    idx.add_argument("--path", default=None,
                     help="read each repository from <path>/<name> instead of the network")
    idx.add_argument("--out", default="-", help="output file, or - for stdout")
    idx.add_argument("--note", default=None,
                     help="how this page was produced (defaults to a description of the source)")

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
    if command == "index":
        return cmd_index(args, root, path, doc)
    if command == "check":
        return cmd_check(args, root, path, doc)
    return cmd_run(args, root, path, doc)


if __name__ == "__main__":
    raise SystemExit(main())
