"""Tests for verify-claims. Stdlib only, like the tool: `python3 -m unittest discover tests`."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_claims import checks, runner, schema  # noqa: E402
from verify_claims.cli import main  # noqa: E402

PY = sys.executable


def claim(**over):
    base = {
        "id": "demo",
        "claim": "the demo prints 42",
        "value": "42",
        "metric": "the number printed by the demo",
        "method": "run python3 -c 'print(42)'",
        "repro": f"{PY} -c \"print(42)\"",
        "evidence": "https://example.invalid/demo",
        "as_of": "2026-09-13",
        "check": {"cmd": f'{PY} -c "print(42)"', "expect": {"equals": "42"}},
    }
    base.update(over)
    return base


def document(*claims_, **over):
    doc = {"project": "demo", "updated": "2026-09-13", "claims": list(claims_) or [claim()]}
    doc.update(over)
    return doc


class WriteRepo:
    """A throwaway repo with a claims file, so the CLI is exercised end to end."""

    def __init__(self, doc):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / "claims.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")

    def cleanup(self):
        self.dir.cleanup()


# ── shape ────────────────────────────────────────────────────────────────────


class ShapeTest(unittest.TestCase):
    def test_valid_document(self):
        self.assertEqual(schema.validate_document(document(), Path("claims.json")), [])

    def test_missing_date_is_an_error(self):
        doc = document()
        del doc["updated"]
        doc["claims"][0].pop("as_of")
        errors = schema.validate_document(doc, Path("claims.json"))
        self.assertTrue(any("as_of" in e for e in errors), errors)

    def test_claim_without_check_is_an_error(self):
        c = claim()
        del c["check"]
        errors = schema.validate_document(document(c), Path("claims.json"))
        self.assertTrue(any("no 'check'" in e for e in errors), errors)

    def test_manual_and_cmd_together_are_an_error(self):
        c = claim(check={"manual": "needs a GPU", "cmd": "true"})
        errors = schema.validate_document(document(c), Path("claims.json"))
        self.assertTrue(any("both 'manual' and 'cmd'" in e for e in errors), errors)

    def test_manual_needs_a_reason(self):
        errors = schema.validate_document(document(claim(check={"manual": "  "})), Path("claims.json"))
        self.assertTrue(any("non-empty reason" in e for e in errors), errors)

    def test_unknown_expect_key_is_an_error(self):
        c = claim(check={"cmd": "true", "expect": {"contain": "x"}})
        errors = schema.validate_document(document(c), Path("claims.json"))
        self.assertTrue(any("unknown key(s) ['contain']" in e for e in errors), errors)

    def test_duplicate_ids_are_an_error(self):
        errors = schema.validate_document(document(claim(), claim()), Path("claims.json"))
        self.assertTrue(any("duplicate id" in e for e in errors), errors)

    def test_unknown_extra_keys_are_tolerated(self):
        c = claim()
        c["notes"] = "harmless"
        c["check"]["note"] = "harmless too"
        self.assertEqual(schema.validate_document(document(c), Path("claims.json")), [])


# ── assertions ───────────────────────────────────────────────────────────────


class EvaluateTest(unittest.TestCase):
    def test_equals_strips(self):
        self.assertEqual(checks.evaluate(" 42 \n", 0, {"equals": "42"}), [])

    def test_equals_reports_the_drift(self):
        failures = checks.evaluate("41\n", 0, {"equals": "42"})
        self.assertEqual(len(failures), 1)
        self.assertIn("41", failures[0])

    def test_contains_and_not_contains(self):
        self.assertEqual(checks.evaluate("a b c", 0, {"contains": ["a", "c"], "not_contains": ["z"]}), [])
        self.assertTrue(checks.evaluate("a b", 0, {"contains": ["z"]}))
        self.assertTrue(checks.evaluate("a z", 0, {"not_contains": ["z"]}))

    def test_regex_multiline(self):
        self.assertEqual(checks.evaluate("line\n14 files\n", 0, {"regex": r"^\d+ files$"}), [])
        self.assertTrue(checks.evaluate("no count here", 0, {"regex": r"^\d+ files$"}))

    def test_expected_nonzero_exit_code(self):
        self.assertEqual(checks.evaluate("", 1, {"exit_code": 1}), [])
        self.assertTrue(checks.evaluate("", 0, {"exit_code": 1}))


# ── running ──────────────────────────────────────────────────────────────────


class RunnerTest(unittest.TestCase):
    def test_passing_claim(self):
        repo = WriteRepo(document())
        try:
            result = runner.run_claim(document()["claims"][0], repo.root, 30)
        finally:
            repo.cleanup()
        self.assertEqual(result.status, "ok")

    def test_drifted_number_fails(self):
        """The whole point: the file says 42, the command now prints 41."""
        c = claim(check={"cmd": f'{PY} -c "print(41)"', "expect": {"equals": "42"}})
        repo = WriteRepo(document(c))
        try:
            result = runner.run_claim(document(c)["claims"][0], repo.root, 30)
        finally:
            repo.cleanup()
        self.assertEqual(result.status, "fail")
        self.assertIn("42", result.detail)

    def test_manual_claim_is_not_run(self):
        c = claim(check={"manual": "needs an API key"})
        repo = WriteRepo(document(c))
        try:
            result = runner.run_claim(document(c)["claims"][0], repo.root, 30)
        finally:
            repo.cleanup()
        self.assertEqual(result.status, "manual")
        self.assertEqual(result.detail, "needs an API key")

    def test_timeout_is_an_error_status(self):
        c = claim(check={"cmd": f'{PY} -c "import time; time.sleep(5)"', "timeout": 0.4})
        repo = WriteRepo(document(c))
        try:
            result = runner.run_claim(document(c)["claims"][0], repo.root, 30)
        finally:
            repo.cleanup()
        self.assertEqual(result.status, "error")
        self.assertIn("timed out", result.detail)

    def test_sequential_commands_use_the_last(self):
        code, out, _, _ = runner.run_commands([f'{PY} -c "print(1)"', f'{PY} -c "print(2)"'], Path("."), 30)
        self.assertEqual((code, out.strip()), (0, "2"))

    def test_strict_mode_fails_on_manual(self):
        self.assertEqual(checks.exit_code_for([runner.CheckResult("a", "ok")], False), 0)
        self.assertEqual(checks.exit_code_for([runner.CheckResult("a", "manual")], False), 0)
        self.assertEqual(checks.exit_code_for([runner.CheckResult("a", "manual")], True), 1)
        self.assertEqual(checks.exit_code_for([runner.CheckResult("a", "fail")], False), 1)


# ── cli ──────────────────────────────────────────────────────────────────────


class CliTest(unittest.TestCase):
    def test_run_passes_and_reports(self):
        repo = WriteRepo(document())
        try:
            code = main(["--root", str(repo.root), "run"])
            self.assertEqual(code, 0)
        finally:
            repo.cleanup()

    def test_run_fails_when_a_number_drifted(self):
        c = claim(check={"cmd": f'{PY} -c "print(41)"', "expect": {"equals": "42"}})
        repo = WriteRepo(document(c))
        try:
            self.assertEqual(main(["--root", str(repo.root), "run"]), 1)
        finally:
            repo.cleanup()

    def test_invalid_shape_refuses_to_run(self):
        c = claim()
        del c["check"]
        repo = WriteRepo(document(c))
        try:
            self.assertEqual(main(["--root", str(repo.root), "run"]), 2)
            self.assertEqual(main(["--root", str(repo.root), "check"]), 1)
        finally:
            repo.cleanup()

    def test_json_report_shape(self):
        repo = WriteRepo(document())
        try:
            out = subprocess.run(
                [PY, "-m", "verify_claims", "--root", str(repo.root), "run", "--json"],
                capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
            )
        finally:
            repo.cleanup()
        self.assertEqual(out.returncode, 0, out.stderr)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["summary"]["ok"], 1)
        self.assertEqual(payload["claims"][0]["status"], "ok")

    def test_missing_file_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["--root", tmp, "run"]), 2)


if __name__ == "__main__":
    unittest.main()
