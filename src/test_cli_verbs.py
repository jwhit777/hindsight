"""End-to-end CLI tests for `hindsight ci diff` and `hindsight validate`.

Run:
    python3 -m unittest test_cli_verbs
    # or via discovery:
    python3 -m unittest discover -s src -p 'test_*.py'

Exit-code contract documented here:
  * `hindsight ci diff ... --gate`  exits 1 when diverged, 0 otherwise.
  * `hindsight ci diff ...`          always exits 0 (report-only).
  * `hindsight validate <path>`      exits 0 on success, 2 on schema failure.
  * `hindsight validate <missing>`   passes through SystemExit(1) raised by
    _auto_ingest (the "no such file" guard).  We do NOT remap it to 2 because
    a missing file is a caller error (wrong path), not a schema error.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
FIX = ROOT.parent / "fixtures"

# Canonical module path so this works from any cwd.
_CLI = [sys.executable, "-m", "hindsight.cli"]
# Make the package importable when running standalone.
_ENV_PYTHONPATH = str(ROOT)


def _run(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI with extra PYTHONPATH=src and capture output."""
    import os
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{_ENV_PYTHONPATH}:{existing}" if existing else _ENV_PYTHONPATH
    return subprocess.run(
        _CLI + list(args),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class CiDiffTests(unittest.TestCase):

    # ---- 1: clean diff with --gate exits 0 ----

    def test_ci_diff_clean_exits_0(self):
        """ci diff of a file against itself is clean — exit 0 even with --gate."""
        result = _run(
            "ci", "diff",
            str(FIX / "canonical_good.jsonl"),
            str(FIX / "canonical_good.jsonl"),
            "--gate",
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 on clean diff with --gate\nstderr={result.stderr}",
        )
        self.assertIn("clean", result.stderr)

    # ---- 2: diverged diff with --gate exits 1 ----

    def test_ci_diff_diverged_exits_1(self):
        """ci diff of good vs bad with --gate exits 1 and reports divergence on stderr."""
        result = _run(
            "ci", "diff",
            str(FIX / "canonical_good.jsonl"),
            str(FIX / "canonical_bad.jsonl"),
            "--gate",
        )
        self.assertEqual(
            result.returncode, 1,
            f"expected exit 1 on diverged diff with --gate\nstderr={result.stderr}",
        )
        self.assertIn("diverged", result.stderr)

    # ---- 3: diverged diff WITHOUT --gate exits 0 ----

    def test_ci_diff_diverged_without_gate_exits_0(self):
        """ci diff without --gate is report-only — exits 0 even when diverged."""
        result = _run(
            "ci", "diff",
            str(FIX / "canonical_good.jsonl"),
            str(FIX / "canonical_bad.jsonl"),
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 on diverged diff without --gate\nstderr={result.stderr}",
        )
        self.assertIn("diverged", result.stderr)

    # ---- 4: --md flag emits Markdown header ----

    def test_ci_diff_md_format(self):
        """With --md the stdout payload starts with the Markdown diff report header."""
        result = _run(
            "ci", "diff",
            str(FIX / "canonical_good.jsonl"),
            str(FIX / "canonical_bad.jsonl"),
            "--md",
        )
        self.assertEqual(
            result.returncode, 0,
            f"unexpected non-zero exit\nstderr={result.stderr}",
        )
        self.assertIn("# Diff report", result.stdout)

    # ---- 4b: default (JSON) format is valid JSON ----

    def test_ci_diff_json_format(self):
        """Without --md the stdout payload is valid JSON with the expected keys."""
        result = _run(
            "ci", "diff",
            str(FIX / "canonical_good.jsonl"),
            str(FIX / "canonical_bad.jsonl"),
        )
        import json
        payload = json.loads(result.stdout)
        self.assertIn("clean", payload)
        self.assertFalse(payload["clean"])


class ValidateTests(unittest.TestCase):

    # ---- 5: good file exits 0 with "OK" on stdout ----

    def test_validate_good_exits_0(self):
        """validate on a well-formed trace exits 0 and prints OK to stdout."""
        result = _run("validate", str(FIX / "canonical_good.jsonl"))
        self.assertEqual(
            result.returncode, 0,
            f"expected exit 0 on valid trace\nstderr={result.stderr}",
        )
        self.assertIn("OK", result.stdout)

    # ---- 6: missing file — _auto_ingest raises SystemExit(1) ----

    def test_validate_missing_file_exits_nonzero(self):
        """validate on a non-existent path exits non-zero.

        _auto_ingest raises SystemExit("hindsight: no such file: ...") which
        Python maps to exit code 1.  We deliberately do NOT remap this to 2
        because it is a caller error (wrong path), not a schema violation.
        The test only asserts non-zero so as not to couple to the exact code.
        """
        result = _run("validate", "/tmp/this-file-does-not-exist.jsonl")
        self.assertNotEqual(
            result.returncode, 0,
            "expected non-zero exit for missing file",
        )

    # ---- bonus: validate on all good fixtures ----

    def test_validate_all_good_fixtures(self):
        """Every *_good.jsonl fixture validates cleanly."""
        good_fixtures = sorted(FIX.glob("*_good.jsonl"))
        self.assertTrue(good_fixtures, "no good fixtures found")
        for fix in good_fixtures:
            with self.subTest(fixture=fix.name):
                result = _run("validate", str(fix))
                self.assertEqual(
                    result.returncode, 0,
                    f"expected exit 0 for {fix.name}\nstderr={result.stderr}",
                )
                self.assertIn("OK", result.stdout)

    # ---- bonus: stderr summary contains path info ----

    def test_validate_good_stdout_contains_step_count(self):
        """stdout summary line includes 'steps' and 'kinds'."""
        result = _run("validate", str(FIX / "canonical_good.jsonl"))
        self.assertIn("steps", result.stdout)
        self.assertIn("kinds", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
