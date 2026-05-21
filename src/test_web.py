"""End-to-end tests for the FastAPI web UI (`hindsight.web`).

Uses FastAPI's in-process TestClient — no network, no server start. Tests
are skipped gracefully if the [web] extra is not installed (matches the
opt-in dependency posture).
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIX = ROOT.parent / "fixtures"

try:
    from fastapi.testclient import TestClient  # noqa: F401

    from hindsight.web import create_app

    _HAVE_WEB = True
except ImportError:  # pragma: no cover — exercised only without [web] extra
    _HAVE_WEB = False


@unittest.skipUnless(_HAVE_WEB, "[web] extra not installed; skipping web tests")
class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient  # noqa: PLC0415

        cls.app = create_app(FIX)
        cls.client = TestClient(cls.app)

    # ---- browse ----

    def test_index_lists_fixtures(self) -> None:
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("canonical_good.jsonl", r.text)
        self.assertIn("subagent_bench_good.json", r.text)

    # ---- show ----

    def test_show_renders_tree(self) -> None:
        r = self.client.get("/show", params={"path": "canonical_good.jsonl"})
        self.assertEqual(r.status_code, 200)
        for token in ("orchestrator", "router", "stock-analyst", "summarize"):
            self.assertIn(token, r.text, f"expected {token!r} in tree")

    def test_show_rejects_path_traversal(self) -> None:
        r = self.client.get("/show", params={"path": "../../../etc/passwd"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("escapes root", r.text)

    def test_show_404_on_missing(self) -> None:
        r = self.client.get("/show", params={"path": "does_not_exist.jsonl"})
        self.assertEqual(r.status_code, 404)

    # ---- diff ----

    def test_diff_result_finds_router_divergence(self) -> None:
        r = self.client.get(
            "/diff/result",
            params={"a": "canonical_good.jsonl", "b": "canonical_bad.jsonl"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("llm:router", r.text)
        self.assertIn("response", r.text)
        self.assertIn("diverged", r.text)

    def test_diff_clean_on_self_diff(self) -> None:
        r = self.client.get(
            "/diff/result",
            params={"a": "canonical_good.jsonl", "b": "canonical_good.jsonl"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("clean", r.text)

    # ---- JSON API ----

    def test_api_run_returns_jsonl_records(self) -> None:
        r = self.client.get("/api/run", params={"path": "canonical_good.jsonl"})
        self.assertEqual(r.status_code, 200)
        records = r.json()
        # 1 header + 7 steps = 8 records.
        self.assertEqual(len(records), 8)
        self.assertEqual(records[0]["type"], "header")

    def test_api_stats_matches_cli_stats(self) -> None:
        from hindsight.ingest_jsonl import ingest  # noqa: PLC0415
        from hindsight.stats import stats as cli_stats  # noqa: PLC0415

        r = self.client.get("/api/stats", params={"path": "canonical_good.jsonl"})
        self.assertEqual(r.status_code, 200)
        expected = json.loads(json.dumps(cli_stats(ingest(FIX / "canonical_good.jsonl"))))
        self.assertEqual(r.json(), expected)

    def test_api_diff_returns_divergence_dict(self) -> None:
        r = self.client.get(
            "/api/diff",
            params={"a": "canonical_good.jsonl", "b": "canonical_bad.jsonl"},
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertFalse(d["clean"])
        self.assertEqual(d["first_divergent_field"], "response")
        self.assertEqual(d["first_divergent_path"], ["agent:orchestrator", "llm:router"])

    # ---- replay ----

    def test_replay_mock_roundtrips_via_redirect(self) -> None:
        r = self.client.post(
            "/replay",
            data={"path": "canonical_good.jsonl", "from_step": "s3"},
            follow_redirects=False,
        )
        self.assertEqual(r.status_code, 303)
        location = r.headers["location"]
        self.assertIn(":replay:", location)
        # Follow the redirect — the show page must render the 7-step tree.
        r2 = self.client.get(location)
        self.assertEqual(r2.status_code, 200)
        for token in ("orchestrator", "router", "stock-analyst", "summarize"):
            self.assertIn(token, r2.text)
        # The replayed run is also reachable via /api/run.
        replay_path = location.split("path=", 1)[1]
        r3 = self.client.get("/api/run", params={"path": replay_path})
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(len(r3.json()), 8)

    # ---- static ----

    def test_static_css_served(self) -> None:
        r = self.client.get("/static/style.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/css", r.headers["content-type"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
