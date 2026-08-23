"""Direct unit coverage for network-path helpers in boards/capture/intake."""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ats_agent import boards
from ats_agent.intake import resolve_source
from ats_agent.capture import CaptureError, capture_cached, clean_capture, fetch_many


class PoliteGetTests(unittest.TestCase):
    def setUp(self):
        boards._last_request_at.clear()

    def test_success_parses_json(self):
        response = io.BytesIO(b'{"ok": true}')
        context_manager = type("CM", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *_a: False,
            "status": 200,
            "read": lambda self: response.read(),
        })()
        with patch("ats_agent.boards.urllib.request.urlopen", return_value=context_manager):
            payload = boards._polite_get_json("https://boards-api.greenhouse.io/v1/x")
        self.assertEqual(payload, {"ok": True})

    def test_non_https_refused(self):
        with self.assertRaises(boards.BoardError):
            boards._polite_get_json("http://insecure.example.com/x")

    def test_500_retries_then_raises(self):
        import urllib.error

        attempts = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            attempts.append(1)
            raise urllib.error.HTTPError(request.full_url, 500, "boom", None, None)

        with patch.object(boards.time, "sleep"), \
             patch("ats_agent.boards.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(boards.BoardError):
                boards._polite_get_json("https://x.example.com/api")
        self.assertEqual(len(attempts), boards.MAX_ATTEMPTS)


class CaptureCacheTests(unittest.TestCase):
    def test_cache_ttl_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            recorded = []

            def fake_capture(url, destination, *, source_type):
                recorded.append(url)
                destination.write_text(f"content for {url}", encoding="utf-8")
                return {"url": url, "path": str(destination), "sha256": "abc",
                        "captured_at": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc).isoformat(),
                        "method": "test", "source_type": source_type,
                        "extraction_status": "captured"}

            with patch("ats_agent.capture.capture_url", side_effect=fake_capture):
                first = capture_cached("https://example.com/a", cache,
                                       source_type="t")
                second = capture_cached("https://example.com/a", cache,
                                        source_type="t")
            self.assertEqual(len(recorded), 1)
            self.assertEqual(first["cache"], "miss")
            self.assertEqual(second["cache"], "hit")

    def test_fetch_many_preserves_order_and_errors(self):
        def fake_capture(url, destination, *, source_type):
            if "bad" in url:
                raise CaptureError(f"failed for {url}")
            destination.write_text("text", encoding="utf-8")
            return {"url": url, "path": str(destination)}

        items = [
            ("https://good.example.com/1", Path(tempfile.mkdtemp()) / "a.txt"),
            ("https://bad.example.com/2", Path(tempfile.mkdtemp()) / "b.txt"),
        ]
        with patch("ats_agent.capture.capture_url", side_effect=fake_capture):
            results = fetch_many(items, source_type="t", workers=2, use_cache=False)
        self.assertIn("good.example.com", str(results[0]))
        self.assertIsInstance(results[1], CaptureError)

    def test_clean_capture_still_delegates(self):
        text = "skip to content\nReal clause here\nReal clause here\n"
        cleaned = clean_capture(text)
        self.assertIn("Real clause here", cleaned)
        self.assertNotIn("skip to content", cleaned)


class ResolveSourceFileTests(unittest.TestCase):
    def test_file_kinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "jobs.json").write_text('{"jobs": [{"id":"a","job_url":"https://x"}]}')
            (root / "links.txt").write_text("https://jobs.lever.co/ramp\n")
            (root / "posting.md").write_text("We need SQL skills.\nBachelor required.\n")
            (root / "ops.md").write_text("- [ ] https://x | C | R\n")
            self.assertEqual(resolve_source(str(root / "jobs.json"))["kind"], "json_export")
            self.assertEqual(resolve_source(str(root / "links.txt"))["kind"], "url_list")
            self.assertEqual(resolve_source(str(root / "posting.md"))["kind"], "jd_text")
            self.assertEqual(resolve_source(str(root / "ops.md"))["kind"], "career_ops")


if __name__ == "__main__":
    unittest.main()
