"""Direct unit coverage for network-path helpers in boards/capture/intake."""
from __future__ import annotations

import io
import hashlib
import os
import socket
import sys
import tempfile
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from ats_agent import boards
from ats_agent.intake import resolve_source
from ats_agent.capture import (
    CaptureError,
    capture_cached,
    capture_url,
    clean_capture,
    fetch_many,
    validate_public_https_url,
)


class PoliteGetTests(unittest.TestCase):
    def setUp(self):
        boards._last_request_at.clear()
        dns = patch("ats_agent.capture.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ])
        dns.start()
        self.addCleanup(dns.stop)

    def test_success_parses_json(self):
        response = io.BytesIO(b'{"ok": true}')
        context_manager = type("CM", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *_a: False,
            "status": 200,
            "read": lambda self, limit=-1: response.read(limit),
        })()
        with patch.object(boards._OPENER, "open", return_value=context_manager):
            payload = boards._polite_get_json("https://boards-api.greenhouse.io/v1/x")
        self.assertEqual(payload, {"ok": True})

    def test_non_https_refused(self):
        with self.assertRaises(boards.BoardError):
            boards._polite_get_json("http://insecure.example.com/x")

    def test_board_policy_rejects_redirects_and_private_dns_before_fetch(self):
        with self.assertRaisesRegex(boards.BoardError, "redirects"):
            boards._NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://127.0.0.1/")
        with patch("ats_agent.capture.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]), patch.object(boards._OPENER, "open") as fetch:
            with self.assertRaisesRegex(boards.BoardError, "public IP"):
                boards._polite_get_json("https://boards-api.greenhouse.io/v1/x")
            fetch.assert_not_called()
        for url in ("https://evil.test/?next=https://jobs.lever.co/acme",
                    "https://user@jobs.lever.co/acme", "https://jobs.lever.co:0/acme"):
            self.assertIsNone(boards.detect_board(url))

    def test_long_retry_after_defers_without_sleeping(self):
        import urllib.error
        error = urllib.error.HTTPError("https://example.com", 429, "busy", {"Retry-After": "3600"}, None)
        with patch.object(boards._OPENER, "open", side_effect=error) as fetch, \
             patch.object(boards.time, "sleep") as sleep:
            with self.assertRaisesRegex(boards.BoardError, "retry budget exhausted"):
                boards._polite_get_json("https://example.com/api")
        self.assertEqual(fetch.call_count, 1)
        sleep.assert_not_called()

    def test_500_retries_then_raises(self):
        import urllib.error

        attempts = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            attempts.append(1)
            raise urllib.error.HTTPError(request.full_url, 500, "boom", None, None)

        with patch.object(boards.time, "sleep"), \
             patch.object(boards._OPENER, "open", side_effect=fake_urlopen):
            with self.assertRaises(boards.BoardError):
                boards._polite_get_json("https://x.example.com/api")
        self.assertEqual(len(attempts), boards.MAX_ATTEMPTS)

    def test_non_retryable_and_invalid_json_responses_fail_closed(self):
        error = urllib.error.HTTPError("https://example.com", 404, "missing", {}, None)
        with patch.object(boards._OPENER, "open", side_effect=error) as fetch:
            with self.assertRaisesRegex(boards.BoardError, "404"):
                boards._polite_get_json("https://example.com/api")
        self.assertEqual(fetch.call_count, 1)

        body = io.BytesIO(b"not json")
        response = type("CM", (), {
            "__enter__": lambda self: self,
            "__exit__": lambda self, *_args: False,
            "read": lambda self, limit=-1: body.read(limit),
        })()
        with patch.object(boards._OPENER, "open", return_value=response):
            with self.assertRaisesRegex(boards.BoardError, "non-JSON"):
                boards._polite_get_json("https://example.com/api")

    def test_pacing_deadline_rejects_before_fetch(self):
        boards._last_request_at["example.com"] = 100.0
        with patch.object(boards, "resolve_public_https_url", return_value=(
            "https://example.com/api", ()
        )), patch.object(boards.time, "monotonic", side_effect=[0.0, 0.0, 0.0]), \
             patch.object(boards._OPENER, "open") as fetch:
            with self.assertRaisesRegex(boards.BoardError, "pacing"):
                boards._polite_get_json("https://example.com/api")
        fetch.assert_not_called()

    def test_pinned_handler_and_scoped_opening_keep_validated_addresses(self):
        address = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        url = "https://boards.example.com/jobs"
        handler = boards._PinnedHTTPSHandler()
        request = urllib.request.Request(url)
        with patch.object(handler, "do_open", return_value="opened") as open_request, \
             patch.object(boards, "resolve_public_https_url", return_value=(url, (address,))) as resolve:
            self.assertEqual(handler.https_open(request), "opened")
            factory = open_request.call_args.args[0]
            self.assertEqual(factory("boards.example.com")._addresses, (address,))
            resolve.assert_called_once_with(url)

        boards._transport_state.resolution = (url, (address,))
        try:
            with patch.object(handler, "do_open", return_value="opened"), \
                 patch.object(boards, "resolve_public_https_url") as resolve:
                self.assertEqual(handler.https_open(request), "opened")
                resolve.assert_not_called()
        finally:
            del boards._transport_state.resolution

        with patch.object(boards, "resolve_public_https_url", side_effect=ValueError("private")):
            with self.assertRaisesRegex(boards.BoardError, "private"):
                handler.https_open(request)

        with patch.object(boards._OPENER, "open", return_value="opened"):
            self.assertEqual(
                boards._open_pinned(request, timeout=1.0, url=url, addresses=(address,)),
                "opened",
            )
        self.assertFalse(hasattr(boards._transport_state, "resolution"))

    def test_pinned_connection_retries_addresses_and_refuses_proxy_tunnel(self):
        from ats_agent.boards import _PinnedHTTPSConnection

        addresses = (
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443)),
        )
        first, second = MagicMock(), MagicMock()
        first.connect.side_effect = OSError("unreachable")
        context = MagicMock()
        with patch("ats_agent.boards.socket.socket", side_effect=[first, second]):
            connection = _PinnedHTTPSConnection("boards.example.com", addresses=addresses)
            connection._context = context
            connection.connect()
        first.close.assert_called_once()
        second.connect.assert_called_once_with(("93.184.216.35", 443))

        tunnel = _PinnedHTTPSConnection("boards.example.com", addresses=addresses)
        tunnel._tunnel_host = "proxy.example.com"
        with self.assertRaisesRegex(OSError, "proxy tunnelling"):
            tunnel.connect()

    def test_response_reader_returns_complete_body_and_rejects_oversize(self):
        from ats_agent.boards import _read_limited

        response = MagicMock()
        response.read.side_effect = [b"one", b"two", b""]
        peer = MagicMock()
        with patch.object(boards, "_response_socket", return_value=peer):
            self.assertEqual(_read_limited(response, boards.time.monotonic() + 1), b"onetwo")
        peer.settimeout.assert_called()

        large = MagicMock()
        large.read.return_value = b"x" * (4 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(boards.BoardError, "4 MiB"):
            _read_limited(large, boards.time.monotonic() + 1)

    def test_fetch_board_url_dispatches_only_recognized_provider(self):
        with patch.object(boards, "fetch_lever", return_value=[{"id": "lever-1"}]) as fetch:
            self.assertEqual(
                boards.fetch_board_url("https://jobs.lever.co/example"),
                [{"id": "lever-1"}],
            )
        fetch.assert_called_once_with("example")
        with self.assertRaisesRegex(boards.BoardError, "recognized"):
            boards.fetch_board_url("https://example.com/jobs")


class CaptureCacheTests(unittest.TestCase):
    @staticmethod
    def _resolver(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", 443, 0, 0)),
        ]

    def test_public_https_validator_accepts_only_global_dns_answers(self):
        calls = []

        def resolver(host, port, *, type):  # noqa: A002
            calls.append((host, port, type))
            return self._resolver()

        value = validate_public_https_url(
            "https://example.com:8443/job", resolver=resolver
        )

        self.assertEqual(value, "https://example.com:8443/job")
        self.assertEqual(calls, [("example.com", 8443, socket.SOCK_STREAM)])

    def test_public_https_validator_canonicalizes_idna_before_dns_and_pinning(self):
        from ats_agent.capture import _pinned_resolve_entry, resolve_public_https_url

        calls = []
        unicode_host = "täst.example"
        ascii_host = unicode_host.encode("idna").decode("ascii")

        def resolver(host, port, *, type):  # noqa: A002
            calls.append((host, port, type))
            return self._resolver()

        url, answers = resolve_public_https_url(
            f"https://{unicode_host}/role", resolver=resolver
        )

        self.assertEqual(url, f"https://{ascii_host}/role")
        self.assertEqual(calls, [(ascii_host, 443, socket.SOCK_STREAM)])
        self.assertTrue(_pinned_resolve_entry(url, answers).startswith(f"{ascii_host}:443:"))

    def test_pinned_resolve_entry_keeps_ipv4_and_ipv6_answers(self):
        from ats_agent.capture import _pinned_resolve_entry

        entry = _pinned_resolve_entry("https://example.com/job", tuple(self._resolver()))

        self.assertTrue(entry.startswith("example.com:443:"))
        self.assertIn("93.184.216.34", entry)
        self.assertIn("[2606:2800:220:1:248:1893:25c8:1946]", entry)

    def test_scrapling_interpreter_uses_console_script_or_fails_closed(self):
        from ats_agent.capture import _scrapling_interpreter

        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "scrapling"
            launcher.write_text("#!/opt/scrapling/python -s\n", encoding="utf-8")
            self.assertEqual(_scrapling_interpreter(str(launcher)), "/opt/scrapling/python")

            launcher.write_text("#!/usr/bin/env pinned-python\n", encoding="utf-8")
            with patch("ats_agent.capture.shutil.which", return_value="/opt/pinned/python"):
                self.assertEqual(_scrapling_interpreter(str(launcher)), "/opt/pinned/python")

            launcher.write_bytes(b"not a Python console script")
            with self.assertRaisesRegex(CaptureError, "Python console script"):
                _scrapling_interpreter(str(launcher))

    def test_public_https_validator_rejects_unsafe_urls(self):
        cases = (
            "http://example.com/job",
            "https:///job",
            "https://user@example.com/job",
            "https://@example.com/job",
            "https://:@example.com/job",
            "https://example.com./job",
            "https://93.184.216.34/job",
            "https://example.com/\nprivate",
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "public HTTPS"):
                    validate_public_https_url(value, resolver=self._resolver)

    def test_public_https_validator_rejects_mixed_private_dns_answers(self):
        def resolver(*_args, **_kwargs):
            return self._resolver() + [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
            ]

        with self.assertRaisesRegex(ValueError, "public IP"):
            validate_public_https_url("https://example.com/job", resolver=resolver)

    def test_capture_rejects_private_host_before_scrapling_or_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "missing" / "capture.txt"
            private = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))
            ]
            with patch("ats_agent.capture.socket.getaddrinfo", return_value=private), \
                 patch("ats_agent.capture.shutil.which") as which, \
                 patch("ats_agent.capture.subprocess.run") as run:
                with self.assertRaisesRegex(CaptureError, "public IP"):
                    capture_url(
                        "https://metadata.example/job",
                        destination,
                        source_type="job_posting",
                    )
            which.assert_not_called()
            run.assert_not_called()
            self.assertFalse(destination.parent.exists())

    def test_cache_ttl_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            recorded = []

            def fake_capture(url, destination, *, source_type):
                recorded.append(url)
                destination.write_text(f"content for {url}", encoding="utf-8")
                return {"url": url, "path": str(destination), "sha256": hashlib.sha256(
                            f"content for {url}".encode("utf-8")
                        ).hexdigest(),
                        "captured_at": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc).isoformat(),
                        "method": "test", "source_type": source_type,
                        "extraction_status": "captured"}

            with patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
                 patch("ats_agent.capture.capture_url", side_effect=fake_capture):
                first = capture_cached("https://example.com/a", cache,
                                       source_type="t")
                second = capture_cached("https://example.com/a", cache,
                                        source_type="t")
            self.assertEqual(len(recorded), 1)
            self.assertEqual(first["cache"], "miss")
            self.assertEqual(second["cache"], "hit")

    def test_cached_copy_replaces_destination_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            protected = root / "resume.txt"
            protected.write_text("candidate source must remain intact\n", encoding="utf-8")
            destination = root / "capture.txt"
            destination.symlink_to(protected)

            def fake_capture(url, path, *, source_type):  # noqa: ANN001
                body = b"safe cached capture"
                path.write_bytes(body)
                return {
                    "url": url,
                    "path": str(path),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "captured_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(),
                    "method": "test",
                    "source_type": source_type,
                    "extraction_status": "captured",
                }

            with patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
                 patch("ats_agent.capture.capture_url", side_effect=fake_capture):
                result = capture_cached(
                    "https://example.com/safe-copy",
                    cache,
                    source_type="job_posting",
                    destination=destination,
                )

            self.assertEqual(protected.read_text(encoding="utf-8"), "candidate source must remain intact\n")
            self.assertFalse(destination.is_symlink())
            self.assertEqual(destination.read_text(encoding="utf-8"), "safe cached capture")
            self.assertEqual(Path(str(result["path"])), destination)

    def test_cache_hit_does_not_repeat_dns_or_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"

            def fake_capture(url, destination, *, source_type):
                destination.write_text("cached body", encoding="utf-8")
                return {
                    "url": url,
                    "path": str(destination),
                    "sha256": hashlib.sha256(b"cached body").hexdigest(),
                    "captured_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(),
                    "method": "test",
                    "source_type": source_type,
                    "extraction_status": "captured",
                }

            with patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
                 patch("ats_agent.capture.capture_url", side_effect=fake_capture):
                capture_cached("https://example.com/cached", cache, source_type="job_posting")
            with patch("ats_agent.capture.socket.getaddrinfo", side_effect=AssertionError("re-resolved")), \
                 patch("ats_agent.capture.capture_url", side_effect=AssertionError("recaptured")):
                result = capture_cached("https://example.com/cached", cache, source_type="job_posting")

        self.assertEqual(result["cache"], "hit")

    def test_cache_and_batch_deduplicate_idna_and_default_port_variants(self):
        unicode_url = "https://täst.example/role"
        ascii_url = "https://xn--tst-qla.example/role"
        default_port_url = "https://xn--tst-qla.example:443/role"
        calls: list[str] = []
        batch_texts: list[str] = []

        def fake_capture(url, destination, *, source_type):  # noqa: ANN001
            calls.append(url)
            body = f"content for {url}".encode("utf-8")
            destination.write_bytes(body)
            return {
                "url": url,
                "path": str(destination),
                "sha256": hashlib.sha256(body).hexdigest(),
                "captured_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "method": "test",
                "source_type": source_type,
                "extraction_status": "captured",
            }

        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
             patch("ats_agent.capture.capture_url", side_effect=fake_capture):
            root = Path(tmp)
            first = capture_cached(unicode_url, root / "cache", source_type="job_posting")
            second = capture_cached(ascii_url, root / "cache", source_type="job_posting")
            third = capture_cached(default_port_url, root / "cache", source_type="job_posting")
            batch = fetch_many(
                [
                    (unicode_url, root / "one.txt"),
                    (ascii_url, root / "two.txt"),
                    (default_port_url, root / "three.txt"),
                ],
                source_type="job_posting",
                workers=2,
                use_cache=False,
            )
            batch_texts = [Path(str(item["path"])).read_text() for item in batch if isinstance(item, dict)]

        self.assertEqual(first["cache"], "miss")
        self.assertEqual(second["cache"], "hit")
        self.assertEqual(third["cache"], "hit")
        self.assertEqual(calls, [ascii_url, ascii_url])
        self.assertTrue(all(isinstance(item, dict) for item in batch))
        self.assertEqual(batch_texts, [
            f"content for {ascii_url}",
            f"content for {ascii_url}",
            f"content for {ascii_url}",
        ])

    def test_cache_hit_still_enforces_url_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"

            with self.assertRaisesRegex(CaptureError, "public HTTPS"):
                capture_cached(
                    "http://127.0.0.1/private",
                    cache,
                    source_type="job_posting",
                )

            self.assertFalse(cache.exists())

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

    def test_fetch_many_deduplicates_and_materializes_each_destination(self):
        calls = []

        def fake_capture(url, destination, *, source_type):
            calls.append(url)
            destination.write_text("shared capture", encoding="utf-8")
            return {"url": url, "path": str(destination)}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [
                ("https://good.example.com/1", root / "a.txt"),
                ("https://good.example.com/1", root / "b.txt"),
            ]
            with patch("ats_agent.capture.capture_url", side_effect=fake_capture):
                results = fetch_many(items, source_type="t", workers=2, use_cache=False)
            self.assertEqual(calls, ["https://good.example.com/1"])
            self.assertEqual([Path(str(item["path"])).read_text() for item in results], [
                "shared capture",
                "shared capture",
            ])

    def test_fetch_many_paces_same_host_workers(self):
        from ats_agent import capture

        capture._last_scrape_at.clear()
        self.addCleanup(capture._last_scrape_at.clear)
        started: list[float] = []

        def fake_run(command, **_kwargs):
            started.append(time.monotonic())
            Path(command[4]).write_text(
                "Python data analysis is required for this analyst role today.\n",
                encoding="utf-8",
            )
            return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"ATS_CAPTURE_FAST_PACE": ""}), \
             patch.object(capture, "MIN_HOST_INTERVAL_SECONDS", 0.04), \
             patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
             patch("ats_agent.capture.shutil.which", return_value="scrapling"), \
             patch("ats_agent.capture.subprocess.run", side_effect=fake_run):
            root = Path(tmp)
            results = fetch_many(
                [
                    ("https://same.example/one", root / "one.txt"),
                    ("https://same.example/two", root / "two.txt"),
                    ("https://same.example/three", root / "three.txt"),
                ],
                source_type="job_posting",
                workers=3,
                use_cache=False,
            )

        self.assertTrue(all(isinstance(result, dict) for result in results))
        self.assertEqual(len(started), 3)
        self.assertGreaterEqual(started[1] - started[0], 0.025)
        self.assertGreaterEqual(started[2] - started[1], 0.025)

    def test_clean_capture_still_delegates(self):
        text = "skip to content\nReal clause here\nReal clause here\n"
        cleaned = clean_capture(text)
        self.assertIn("Real clause here", cleaned)
        self.assertNotIn("skip to content", cleaned)

    def test_clean_capture_trims_linkedin_recommendation_chrome(self):
        cleaned = clean_capture(
            "Role requirements\nPython is required\nSimilar jobs\nProcurement Analyst jobs\n"
        )

        self.assertEqual(cleaned, "Role requirements\nPython is required\n")

    def test_empty_static_capture_never_escalates_to_browser_fetch(self):
        commands = []

        def fake_run(command, **_kwargs):
            commands.append(command)
            destination = Path(command[4])
            destination.write_text("", encoding="utf-8")
            return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
             patch("ats_agent.capture.shutil.which", return_value="scrapling"), \
             patch("ats_agent.capture.subprocess.run", side_effect=fake_run), \
             patch("ats_agent.capture._sleep"):
            with self.assertRaisesRegex(CaptureError, "empty or insufficient"):
                capture_url(
                    "https://example.com/job",
                    Path(tmp) / "capture.txt",
                    source_type="job_posting",
                    attempts=2,
                )

        self.assertEqual(len(commands), 2)
        self.assertTrue(all("Session(curl_options" in command[2] for command in commands))
        self.assertTrue(all("DynamicFetcher" not in command[2] for command in commands))

    def test_capture_pins_validated_dns_answers_for_the_scrapling_runtime(self):
        public_one = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        public_two = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443))]
        commands = []

        def fake_run(command, **_kwargs):
            commands.append(command)
            Path(command[4]).write_text(
                "Python is required for this public analyst role today.", encoding="utf-8"
            )
            return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"ATS_CAPTURE_FAST_PACE": "1"}), \
             patch("ats_agent.capture.socket.getaddrinfo", side_effect=[public_one, public_two]), \
             patch("ats_agent.capture.shutil.which", return_value="scrapling"), \
             patch("ats_agent.capture.subprocess.run", side_effect=fake_run):
            destination = Path(tmp) / "capture.txt"
            result = capture_url(
                "https://example.com/rebound", destination, source_type="job_posting", attempts=1
            )

        self.assertEqual(result["extraction_status"], "captured")
        self.assertEqual(len(commands), 1)
        self.assertIn("CurlOpt.RESOLVE", commands[0][2])
        self.assertIn("Session(curl_options", commands[0][2])
        self.assertIn("allow_redirects=False", commands[0][2])
        self.assertIn("verify=True", commands[0][2])
        self.assertIn("ResponseFactory.from_http_request", commands[0][2])
        self.assertNotIn("Fetcher.get", commands[0][2])
        self.assertEqual(commands[0][-1], "example.com:443:93.184.216.35")

    def test_pinned_scrapling_child_stops_oversized_body_during_streaming(self):
        from ats_agent.capture import (
            MAX_CAPTURE_BYTES,
            SCRAPLING_PIN,
            _PINNED_SCRAPLING_CAPTURE,
        )

        captured: dict[str, object] = {}

        class FakeCurlOpt:
            RESOLVE = "resolve"
            MAXFILESIZE_LARGE = "maxfilesize"

        class FakeSession:
            def __init__(self, *, curl_options):  # noqa: ANN001
                captured["curl_options"] = curl_options

            def __enter__(self):  # noqa: ANN201
                return self

            def __exit__(self, *_args):  # noqa: ANN001, ANN201
                return False

            def get(self, *_args, **kwargs):  # noqa: ANN001, ANN201
                captured["request"] = kwargs
                if captured.get("header_limit"):
                    raise RuntimeError("Exceeded the maximum allowed file size")
                kwargs["content_callback"](b"x" * (MAX_CAPTURE_BYTES + 1))
                raise AssertionError("oversized response callback should abort the request")

        class FakeConvertor:
            @staticmethod
            def write_content_to_file(*_args, **_kwargs):  # noqa: ANN001, ANN201
                raise AssertionError("oversized response must not be converted or written")

        class FakeResponseFactory:
            @staticmethod
            def from_http_request(*_args, **_kwargs):  # noqa: ANN001, ANN201
                raise AssertionError("oversized response must not be converted")

        curl_cffi = types.ModuleType("curl_cffi")
        curl_cffi.CurlOpt = FakeCurlOpt
        curl_requests = types.ModuleType("curl_cffi.requests")
        curl_requests.Session = FakeSession
        scrapling = types.ModuleType("scrapling")
        scrapling.__version__ = SCRAPLING_PIN
        scrapling_core = types.ModuleType("scrapling.core")
        scrapling_shell = types.ModuleType("scrapling.core.shell")
        scrapling_shell.Convertor = FakeConvertor
        scrapling_engines = types.ModuleType("scrapling.engines")
        scrapling_toolbelt = types.ModuleType("scrapling.engines.toolbelt")
        scrapling_convertor = types.ModuleType("scrapling.engines.toolbelt.convertor")
        scrapling_convertor.ResponseFactory = FakeResponseFactory
        modules = {
            "curl_cffi": curl_cffi,
            "curl_cffi.requests": curl_requests,
            "scrapling": scrapling,
            "scrapling.core": scrapling_core,
            "scrapling.core.shell": scrapling_shell,
            "scrapling.engines": scrapling_engines,
            "scrapling.engines.toolbelt": scrapling_toolbelt,
            "scrapling.engines.toolbelt.convertor": scrapling_convertor,
        }

        with patch.dict(sys.modules, modules, clear=False), patch.object(
            sys,
            "argv",
            ["capture", "https://example.com/role", "capture.txt", "10", "1", "example.com:443:93.184.216.34"],
        ):
            with self.assertRaisesRegex(SystemExit, "response exceeds the maximum capture size"):
                exec(_PINNED_SCRAPLING_CAPTURE, {"__name__": "__main__"})  # noqa: S102  # nosec B102

            captured["header_limit"] = True
            with self.assertRaisesRegex(SystemExit, "response exceeds the maximum capture size"):
                exec(_PINNED_SCRAPLING_CAPTURE, {"__name__": "__main__"})  # noqa: S102  # nosec B102

        self.assertEqual(
            captured["curl_options"],
            {FakeCurlOpt.RESOLVE: ["example.com:443:93.184.216.34"], FakeCurlOpt.MAXFILESIZE_LARGE: MAX_CAPTURE_BYTES},
        )
        self.assertIn("content_callback", captured["request"])

    def test_capture_ignores_ambient_proxy_and_tls_trust_variables(self):
        from ats_agent.capture import _capture_environment

        with patch.dict(
            os.environ,
            {
                "HTTPS_PROXY": "http://proxy.invalid",
                "NO_PROXY": "example.com",
                "SSL_CERT_FILE": "/tmp/untrusted-ca.pem",
                "SSL_CERT_DIR": "/tmp/untrusted-certs",
                "CURL_CA_BUNDLE": "/tmp/untrusted-curl-ca.pem",
                "REQUESTS_CA_BUNDLE": "/tmp/untrusted-requests-ca.pem",
                "PYTHONPATH": "/tmp/untrusted-python-modules",
                "PYTHONUSERBASE": "/tmp/untrusted-python-userbase",
            },
        ):
            environment = _capture_environment()

        for name in (
            "HTTPS_PROXY",
            "NO_PROXY",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "CURL_CA_BUNDLE",
            "REQUESTS_CA_BUNDLE",
            "PYTHONPATH",
            "PYTHONUSERBASE",
        ):
            self.assertNotIn(name, environment)
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")

    def test_capture_rejects_oversized_output_before_decoding(self):
        from ats_agent import capture

        def fake_scrape(_executable, _url, temporary, **_kwargs):
            temporary.write_bytes(b"x" * 33)

        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.validate_public_https_url", return_value="https://example.com/job"), \
             patch("ats_agent.capture.require_scrapling", return_value="scrapling"), \
             patch("ats_agent.capture.MAX_CAPTURE_BYTES", 32), \
             patch("ats_agent.capture._scrape_once", side_effect=fake_scrape) as scrape:
            destination = Path(tmp) / "capture.txt"
            with self.assertRaisesRegex(CaptureError, "Scrapling capture exceeds"):
                capture.capture_url("https://example.com/job", destination, source_type="job_posting", attempts=3)
            self.assertFalse(destination.exists())
            self.assertFalse(list(Path(tmp).glob(".*")))
        self.assertEqual(scrape.call_count, 1)

    def test_capture_writes_only_complete_clean_output(self):
        def fake_run(command, **kwargs):
            Path(command[4]).write_text(
                "Python data analysis is required for this analyst role today.\n",
                encoding="utf-8",
            )
            self.assertNotIn("HTTPS_PROXY", kwargs["env"])
            return type("Completed", (), {"returncode": 0, "stderr": "", "stdout": ""})()

        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, {"ATS_CAPTURE_FAST_PACE": "1", "HTTPS_PROXY": "http://proxy.invalid"}), \
             patch("ats_agent.capture.socket.getaddrinfo", side_effect=self._resolver), \
             patch("ats_agent.capture.shutil.which", return_value="scrapling"), \
             patch("ats_agent.capture.subprocess.run", side_effect=fake_run):
            destination = Path(tmp) / "capture.txt"
            result = capture_url("https://example.com/job", destination, source_type="job_posting")
            self.assertEqual(result["extraction_status"], "captured")
            self.assertTrue(destination.is_file())
            self.assertFalse(list(Path(tmp).glob(".*.tmp")))

    def test_capture_uses_a_scrapling_supported_temporary_suffix(self):
        seen: list[Path] = []

        def fake_scrape(_executable, _url, temporary, **_kwargs):
            seen.append(temporary)
            temporary.write_text(
                "Python data analysis is required for this analyst role today.\n",
                encoding="utf-8",
            )

        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.validate_public_https_url", return_value="https://example.com/job"), \
             patch("ats_agent.capture.require_scrapling", return_value="scrapling"), \
             patch("ats_agent.capture._scrape_once", side_effect=fake_scrape):
            destination = Path(tmp) / "cache.tmp"
            capture_url("https://example.com/job", destination, source_type="job_posting")
            self.assertTrue(destination.is_file())

        self.assertEqual([path.suffix for path in seen], [".txt"])

    def test_capture_stops_after_permanent_http_error_and_deadline(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.validate_public_https_url", return_value="https://example.com/job"), \
             patch("ats_agent.capture.require_scrapling", return_value="scrapling"), \
             patch("ats_agent.capture._scrape_once", side_effect=CaptureError("HTTP 404")) as scrape:
            with self.assertRaisesRegex(CaptureError, "HTTP 404"):
                capture_url(
                    "https://example.com/job", Path(tmp) / "capture.txt",
                    source_type="job_posting", attempts=3,
                )
        self.assertEqual(scrape.call_count, 1)

        with tempfile.TemporaryDirectory() as tmp, \
             patch("ats_agent.capture.CAPTURE_DEADLINE_SECONDS", 0), \
             patch("ats_agent.capture.validate_public_https_url", return_value="https://example.com/job"), \
             patch("ats_agent.capture.require_scrapling", return_value="scrapling"), \
             patch("ats_agent.capture.time.monotonic", side_effect=[0.0, 0.0]):
            with self.assertRaisesRegex(CaptureError, "deadline"):
                capture_url("https://example.com/job", Path(tmp) / "capture.txt", source_type="job_posting")

    def test_corrupt_cache_retries_capture_and_cached_fetch_many_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()
            key = hashlib.sha256(b"https://example.com/corrupt").hexdigest()[:24]
            (cache / f"{key}.json").write_text("{", encoding="utf-8")
            (cache / f"{key}.txt").write_text("old", encoding="utf-8")

            def fake_capture(url, destination, *, source_type):
                destination.write_text("fresh body", encoding="utf-8")
                return {
                    "url": url,
                    "path": str(destination),
                    "sha256": hashlib.sha256(b"fresh body").hexdigest(),
                    "captured_at": __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(),
                    "method": "test",
                    "source_type": source_type,
                    "extraction_status": "captured",
                }

            with patch("ats_agent.capture.validate_public_https_url", return_value="https://example.com/corrupt"), \
                 patch("ats_agent.capture.capture_url", side_effect=fake_capture) as capture:
                result = capture_cached("https://example.com/corrupt", cache, source_type="job_posting")
            self.assertEqual(result["cache"], "miss")
            capture.assert_called_once()

            cached_body = root / "cached.txt"
            cached_body.write_text("cached", encoding="utf-8")
            with patch(
                "ats_agent.capture.capture_cached",
                return_value={"url": "https://example.com/a", "path": str(cached_body)},
            ) as cached:
                result = fetch_many(
                    [("https://example.com/a", root / "a.txt")],
                    source_type="job_posting", cache_dir=cache,
                )
            self.assertEqual(result, [{"url": "https://example.com/a", "path": str(root / "a.txt")}])
            cached.assert_called_once()

    def test_pinned_board_connection_uses_validated_numeric_peer(self):
        from ats_agent.boards import _PinnedHTTPSConnection

        address = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        raw_socket = MagicMock()
        wrapped_socket = MagicMock()
        context = MagicMock()
        context.wrap_socket.return_value = wrapped_socket
        with patch("ats_agent.boards.socket.socket", return_value=raw_socket):
            connection = _PinnedHTTPSConnection("boards.example.com", addresses=(address,))
            connection._context = context
            connection.connect()

        raw_socket.connect.assert_called_once_with(("93.184.216.34", 443))
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname="boards.example.com")
        self.assertIs(connection.sock, wrapped_socket)

    def test_board_response_deadline_covers_trickling_body(self):
        from ats_agent.boards import _read_limited

        response = type("Response", (), {"read": lambda self, _size: b"x"})()
        with patch("ats_agent.boards.time.monotonic", side_effect=[0.0, 46.0]):
            with self.assertRaisesRegex(TimeoutError, "deadline"):
                _read_limited(response, 45.0)


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
            self.assertEqual(resolve_source(str(root / "ops.md"))["kind"], "url_list")


if __name__ == "__main__":
    unittest.main()
