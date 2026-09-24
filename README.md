# verify-claims

<p align="center">
  <img src="./assets/readme/hero.svg?v=20260915" width="100%" alt="verify-claims — runs the receipts behind a claims.json file: every published number must still be printed by the command next to it. The panel shows this repository's own run: 7 machine-checked, 7 ok.">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen.svg" alt="Dependencies: none">
  <img src="https://img.shields.io/badge/license-MIT-00ccff.svg" alt="License">
</p>

**The problem this exists for.** A README says "283 restaurants and 312 visits", a dashboard says "6,395 records across 89 benchmarks", a changelog says "167 releases". Six months later the number is wrong, and nothing failed — because the number was written by hand into prose while the data moved underneath it. A claim with no command behind it is not evidence, it is a rumour that happens to be formatted.

`verify-claims` makes the command part of the claim. A `claims.json` file lists every published number with the command that produces it and what that command's output must contain. The tool runs them; if the output no longer matches, the job fails.

## The format

```jsonc
{
  "project": "foodmap",
  "updated": "2026-09-13",
  "claims": [
    {
      "id": "dataset-size",
      "claim": "The repository ships 283 restaurants and 312 visits.",
      "value": "283 restaurants / 312 visits",
      "metric": "counts read from data/*/restaurants.json",
      "method": "node counts the two files and prints the two totals",
      "repro": "node -e \"...\"",
      "evidence": "data/陈晓卿/restaurants.json",
      "as_of": "2026-09-13",

      "check": {
        "cmd": "node -e \"...\"",          // string or list (setup steps, then the one that prints)
        "expect": { "equals": "283 312" }, // equals | contains | not_contains | regex | exit_code
        "timeout": 60,                     // seconds, default 120
        "dir": "scripts"                   // optional, relative to --root
      }
    },
    {
      "id": "live-site-shows-the-same-number",
      "claim": "The deployed page shows the same total.",
      "value": "same as data.json",
      "metric": "the rendered page",
      "method": "requires fetching the deployment",
      "repro": "curl -s https://example.invalid/",
      "evidence": "https://example.invalid/",
      "as_of": "2026-09-13",

      "check": { "manual": "needs network access to the deployed page; the deploy job checks it, not this one" }
    }
  ]
}
```

Rules the tool enforces, and nothing else:

- **A claim must say how it can be checked** — either `check.cmd` + `check.expect`, or `check.manual` with a written reason. Neither is a shape error, and a file with shape errors refuses to run (exit 2) instead of reporting a green tick.
- **One of `as_of` / `verified` / `updated`** per claim: the date the number was last true for. A number without a date cannot be judged stale.
- **Unknown extra keys are tolerated.** A standard that rejects harmless extras does not get adopted.

The shape is taken from the claims files already used across [codeblast](https://github.com/alloevil/codeblast), [paired-eval](https://github.com/alloevil/paired-eval), [foodmap](https://github.com/alloevil/foodmap), [deepresearch-arms-lab](https://github.com/alloevil/deepresearch-arms-lab) and [github-discovery](https://github.com/alloevil/github-discovery) — the same fields, with the executable part added.

## Use it

```bash
# from this repo
python3 -m verify_claims --root . run

# or install it
pip install "git+https://github.com/alloevil/verify-claims@v0.1.0"
verify-claims --root . run

verify-claims --root . list     # which claims are machine-checked, which are manual
verify-claims --root . check    # shape only, runs nothing
verify-claims --root . coverage # which numbers in the README nothing claims (a to-do list)
verify-claims --root . index    # one page covering every repository this guards
```

Exit codes: **0** every machine check passed · **1** a claim no longer reproduces (or, with `--strict`, a claim has no machine check) · **2** the file's shape is invalid, so nothing was run.

Options: `--strict` · `--json` · `--timeout` · `--only id1,id2` · `--skip id1` · `-f path/to/claims.json` (the default search order is `claims.json`, `docs/claims.json`, `.claims/claims.json`, `dist/claims.json`).

### Linting for time-bomb claims

`lint` is an advisory scan for machine-checked claims whose values look like changing counts or
current data. It deliberately does not fail CI: versions, protocol constants, dated snapshots, and
relation checks are legitimate fixed values. The output is a review queue, not a verdict.

```bash
verify-claims --root . lint
```

Replace a flagged absolute count with a relation check (`card == data`, `sitemap == generated pages`)
or attach a dated snapshot. The linter intentionally has false positives; a human decides whether
the value is stable or whether the claim should be rewritten.

### Coverage: what the gate cannot see

A gate defends the numbers somebody wrote down. It is silent about the numbers nobody did — and
"we gated our figures" is exactly the kind of statement that deserves a look. `coverage` reads the
README's prose, pulls out number-like tokens (`42%`, `28/28`, `250 rows`, `72 条`), and prints the
ones no claim mentions. It always exits **0**: it is a to-do list, not a gate.

```bash
verify-claims --root . coverage --max 10        # the ten most prominent unclaimed numbers
verify-claims --root . coverage --first-screen 40   # only what a reader sees before scrolling
```

Read it as a heuristic, and read its blind spots first:

- **Words are invisible.** "seven platforms" and "七种日志格式" carry no digits; the report cannot
  see them either way.
- **Not every number is a figure.** An example's `50MB`, an HTTP `503`, a `24 小时` uptime statement,
  a CSS `width="100%"` all show up as candidates. This repository's own report leads with the three
  illustration numbers from its worked example — `283 restaurants`, `312 visits`, `6,395 records` —
  none of which should ever be claimed, because they describe another project's data.
- **It says nothing about truth.** That is `run`'s job; coverage only knows whether a number was
  claimed, not whether the claim holds.
- **Fenced code, links, image tags and badge lines are skipped** — they are examples or furniture.
  Table rows are *kept*: a generated table is still a published figure.

So the output is an upper bound on the work left, ordered by where a reader looks, not a
completeness score. Across the 22 repositories this tool guards it currently lists 78 unclaimed
candidates against 176 claimed ones; most of the 78 are the decorative kind above, which is why this
is a backlog to be triaged rather than a defect count.

### The portfolio page

The gates live in 22 repositories, so "are your numbers checked?" is spread across 22 CI runs nobody
opens. `index` reads each repository's own claims file (the list is `docs/repos.txt`) and renders one
table: how many claims, how many machine-checked, how many still manual, and when that file was last
updated. [`docs/index.md`](docs/index.md) is the current output.

```bash
verify-claims index --out docs/index.md            # from raw.githubusercontent.com at HEAD
verify-claims index --ref v0.1.2 --out page.md     # pinned to one tag, so the page is reproducible
verify-claims index --path ../ --out page.md       # from local clones, no network
```

It is regenerated weekly by `.github/workflows/index.yml` and is never hand-edited: a row comes from
the repository it describes. A sibling that cannot be fetched shows up as `unreachable: <error>`
instead of disappearing, because a dropped row would make the portfolio look smaller than it is. The
page is not a gate — nothing fails when a repository is unreachable — so `claims.json` only asserts
that its own summary line equals the sum of the rows under it.

### As a GitHub Action

```yaml
- uses: actions/checkout@v4
- uses: alloevil/verify-claims@v0.1.0
  with:
    strict: "false"     # "true" also fails on claims that no command checks
```

The action runs the tool from its own checkout (`PYTHONPATH`), so nothing is installed from a registry that could lag the ref you pinned. Output `summary` carries the one-line result.

## What a failure looks like

```
$ python3 -m verify_claims --root example run      # after example/data.json changed behind the claim
  ok   ... (other claims)
  FAIL dataset-size                     [fail] equals: expected '283312', got '284312'
  1 machine-checked · 0 ok · 1 failed · 0 error · 1 manual
  FAILED — a published number no longer reproduces; fix the number or the code, not the gate.
```

The gate never rewrites your text. It tells you which published number stopped being true, and leaves the choice between fixing the number, fixing the code, or marking the claim manual with a reason.

## Releases

`v0.1.0` · `v0.1.1` (a failed assertion now reports the command's actual output) · `0.1.2` in the
manifest, its tag held until a PyPI publisher exists (adds `coverage`). Tags are the
release unit — consumers reference `alloevil/verify-claims@vX.Y.Z`; there is no floating tag on
purpose, because a moving ref would mean a gate that changes without a commit in the repository
it guards.

Note on the first two tags: they predate the release workflow and their manifest was still `0.1.0`,
which the workflow now refuses by design (tag ≠ manifest). `0.1.2` is the first version whose tag
and manifest agree, and it is held until the PyPI pending publisher exists.

Publishing runs from `.github/workflows/release.yml` on a version tag, through PyPI Trusted
Publishing (OIDC), so no API token lives in this repository. The workflow refuses a tag that does
not match `pyproject.toml`, runs the tests and this repo's own claims first, and `twine check`s
the artifacts before upload. One-time setup on PyPI: add a pending publisher for
`alloevil/verify-claims`, workflow `release.yml`, environment `pypi`.

## This repository checks itself

`claims.json` at the repository root states seven claims about this tool — that it has no dependencies, that the CLI exposes the documented subcommands, that the version matches the manifest, that the example passes, that `--strict` really fails on a manual claim, that the shape validator refuses a claim with no check, and that the test suite has the number of tests the file says. CI runs that file, then deliberately breaks a number and requires the run to fail.

```
$ python3 -m verify_claims --root . run
7 machine-checked · 7 ok · 0 failed · 0 error · 0 manual
```

## Where the numbers came from

[**docs/measurement.md**](docs/measurement.md) is the audit this tool was built out of: 16
repositories, **553 checkable claims, 131 of which did not stand up (24%)**, listed per repository
with the worst finding and the commit that fixed it. It also records the ten checks I wrote wrongly
while doing it — about one wrong check per thirteen wrong claims — and the limitations of the
measurement (one auditor, not a random sample, softer verdicts excluded).

The report's own arithmetic is a claim in this repository's `claims.json`: edit a row without
editing the totals and the gate fails.

## What it catches, with real examples

[**docs/case-studies.md**](docs/case-studies.md) collects the failure modes this tool was built from — every case is a number that was actually published in one of the author's repositories and did not stand up: a hardcoded star count inside the generator that re-renders it daily, a "daily cron" that never existed, a `--check` that failed every day without a rebuild, a link checker that excluded the directory holding the broken link, a `~20 s` estimate against a measured 71 s. It also records the five checks *I* wrote wrongly while writing it, and what caught each.

## Scope

- It does not scrape text for numbers, and it does not judge whether a claim is meaningful. It runs what you wrote down, and reports what happened.
- It does not replace a test suite: a claim check is a receipt for a published number, not a unit test.
- Commands run with your shell and your environment, in the repository you point it at. Read a claims file before you run it, exactly as you would a Makefile.

## License

MIT
