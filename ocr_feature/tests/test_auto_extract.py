# Run only this file (from the ocr_feature/ directory):
#     .venv/bin/python -m tests.test_auto_extract
import unittest
from datetime import datetime, timezone

from core.auto_extract import (
    AutoExtractConfig,
    SupabaseStore,
    config_from_env,
    run_once,
    start_auto_extract,
)


class FakeStore:
    """Records every call; papers already filled in are refused like the real
    conditional update would."""

    def __init__(self, papers, filled=()):
        self.papers = papers
        self.filled = set(filled)
        self.saved = {}
        self.calls = []

    def pending(self, limit, since=None):
        self.calls.append(("pending", limit, since))
        return [
            p for p in self.papers
            if p["id"] not in self.saved
            and (since is None or datetime.fromisoformat(p["captured_at"].replace("Z", "+00:00")) >= since)
        ][:limit]

    def save_extracted_text(self, submission_id, text):
        self.calls.append(("save_extracted_text", submission_id, text))
        if submission_id in self.filled:
            return False
        self.saved[submission_id] = text
        return True


def paper(i):
    return {"id": f"p{i}", "image_url": f"https://x/{i}.jpg", "captured_at": "2026-09-24T00:00:00Z"}


def quiet(_message):
    pass


class RunOnceTests(unittest.TestCase):
    def test_saves_each_pending_paper_once_with_the_cleaned_text(self):
        store = FakeStore([paper(1), paper(2)])
        extract = lambda url: {"cleaned_text": f"code from {url}"}

        saved = run_once(store, extract, {}, log=quiet)

        self.assertEqual(saved, 2)
        self.assertEqual(store.saved, {"p1": "code from https://x/1.jpg", "p2": "code from https://x/2.jpg"})

    def test_a_paper_the_teacher_filled_in_first_is_skipped_not_failed(self):
        store = FakeStore([paper(1)], filled={"p1"})
        failures = {}
        rows = []

        saved = run_once(store, lambda url: {"cleaned_text": "x"}, failures, log=quiet, record=rows.append)

        self.assertEqual(saved, 0)
        self.assertEqual(failures, {})
        self.assertEqual(rows[0]["result"], "skipped")

    def test_gives_up_on_a_paper_after_max_failures_and_keeps_going(self):
        store = FakeStore([paper(1), paper(2)])
        attempts = []

        def extract(url):
            attempts.append(url)
            if url.endswith("1.jpg"):
                raise RuntimeError("bad image")
            return {"cleaned_text": "ok"}

        failures = {}
        config = AutoExtractConfig(enabled=True, max_failures=2)
        for _ in range(4):
            run_once(store, extract, failures, config, log=quiet)

        self.assertEqual(failures, {"p1": 2})
        self.assertEqual(attempts.count("https://x/1.jpg"), 2)
        self.assertEqual(store.saved, {"p2": "ok"})

    def test_given_up_papers_do_not_starve_newer_ones(self):
        store = FakeStore([paper(1), paper(2), paper(3)])
        failures = {"p1": 3, "p2": 3}
        config = AutoExtractConfig(enabled=True, batch_size=1, max_failures=3)

        run_once(store, lambda url: {"cleaned_text": "ok"}, failures, config, log=quiet)

        self.assertEqual(store.saved, {"p3": "ok"})

    def test_never_reads_papers_captured_before_the_start_date(self):
        old = {"id": "old", "image_url": "https://x/old.jpg", "captured_at": "2026-08-24T00:00:00Z"}
        new = {"id": "new", "image_url": "https://x/new.jpg", "captured_at": "2026-09-25T09:00:00Z"}
        store = FakeStore([old, new])
        config = AutoExtractConfig(enabled=True, since=datetime(2026, 9, 25, tzinfo=timezone.utc))

        run_once(store, lambda url: {"cleaned_text": "x"}, {}, config, log=quiet)

        self.assertEqual(store.saved, {"new": "x"})

    def test_nothing_pending_does_nothing(self):
        store = FakeStore([])
        self.assertEqual(run_once(store, lambda url: {"cleaned_text": "x"}, {}, log=quiet), 0)

    def test_only_reads_pending_papers_and_writes_extracted_text(self):
        store = FakeStore([paper(1)])
        run_once(store, lambda url: {"cleaned_text": "x"}, {}, log=quiet)

        kinds = {call[0] for call in store.calls}
        self.assertEqual(kinds, {"pending", "save_extracted_text"})

    def test_records_timings_without_code_text(self):
        clock = iter([100.0, 107.5])
        rows = []
        run_once(FakeStore([paper(1)]), lambda url: {"cleaned_text": "secret code"}, {},
                 now=lambda: next(clock), log=quiet, record=rows.append)

        self.assertEqual(rows[0]["result"], "saved")
        self.assertEqual(rows[0]["extract_seconds"], 7.5)
        self.assertNotIn("secret code", str(rows[0]))


class ConfigTests(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(config_from_env({}).enabled)

    def test_on_with_true_and_interval_parsed(self):
        config = config_from_env({"AUTO_EXTRACT": "true", "AUTO_EXTRACT_INTERVAL_SECONDS": "30"})
        self.assertTrue(config.enabled)
        self.assertEqual(config.interval_seconds, 30.0)

    def test_since_defaults_to_server_start_and_can_be_set(self):
        started = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(config_from_env({}, started_at=started).since, started)
        self.assertEqual(
            config_from_env({"AUTO_EXTRACT_SINCE": "2026-09-20"}, started_at=started).since,
            datetime(2026, 9, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(config_from_env({"AUTO_EXTRACT_SINCE": "someday"}, started_at=started).since, started)

    def test_bad_interval_falls_back(self):
        self.assertEqual(config_from_env({"AUTO_EXTRACT_INTERVAL_SECONDS": "soon"}).interval_seconds, 10.0)
        self.assertEqual(config_from_env({"AUTO_EXTRACT_INTERVAL_SECONDS": "-5"}).interval_seconds, 10.0)


class StartTests(unittest.TestCase):
    def test_does_not_start_when_off(self):
        self.assertIsNone(start_auto_extract({}, lambda url: {}))

    def test_does_not_start_without_supabase_settings(self):
        self.assertIsNone(start_auto_extract({"AUTO_EXTRACT": "true"}, lambda url: {}))

    def test_starts_and_stops_cleanly(self):
        store = FakeStore([])
        worker = start_auto_extract(
            {"AUTO_EXTRACT": "true", "SUPABASE_URL": "https://x", "SUPABASE_KEY": "k",
             "AUTO_EXTRACT_INTERVAL_SECONDS": "0.05"},
            lambda url: {"cleaned_text": "x"},
            store_factory=lambda url, key: store,
            record=lambda row: None,
        )
        self.assertIsNotNone(worker)
        worker.stop(timeout=2)
        self.assertFalse(worker._thread.is_alive())
        self.assertTrue(any(call[0] == "pending" for call in store.calls))


class FakeQuery:
    """Mimics the postgrest builder chain and records what was asked for."""

    def __init__(self, log, data):
        self.log = log
        self.data = data

    def __getattr__(self, name):
        if name == "not_":
            self.log.append(("not_",))
            return self

        def call(*args):
            self.log.append((name, *args))
            return self
        return call

    def execute(self):
        self.log.append(("execute",))
        return type("Response", (), {"data": self.data})()


class FakeClient:
    def __init__(self, data):
        self.log = []
        self.data = data

    def table(self, name):
        self.log.append(("table", name))
        return FakeQuery(self.log, self.data)


class SupabaseStoreTests(unittest.TestCase):
    def test_pending_asks_only_for_unread_papers_oldest_first(self):
        client = FakeClient([{"id": "p1"}])
        since = datetime(2026, 9, 25, tzinfo=timezone.utc)
        self.assertEqual(SupabaseStore("u", "k", client=client).pending(5, since), [{"id": "p1"}])
        self.assertIn(("gte", "captured_at", "2026-09-25T00:00:00+00:00"), client.log)
        self.assertIn(("is_", "verified_text", "null"), client.log)
        self.assertIn(("or_", "extracted_text.is.null,extracted_text.eq."), client.log)
        self.assertIn(("is_", "image_url", "null"), client.log)
        self.assertIn(("order", "captured_at"), client.log)
        self.assertIn(("limit", 5), client.log)

    def test_save_writes_only_extracted_text_and_only_if_still_unread(self):
        client = FakeClient([{"id": "p1"}])
        self.assertTrue(SupabaseStore("u", "k", client=client).save_extracted_text("p1", "code"))
        self.assertIn(("update", {"extracted_text": "code"}), client.log)
        self.assertIn(("eq", "id", "p1"), client.log)
        self.assertIn(("is_", "verified_text", "null"), client.log)

    def test_save_reports_false_when_no_row_changed(self):
        client = FakeClient([])
        self.assertFalse(SupabaseStore("u", "k", client=client).save_extracted_text("p1", "code"))


if __name__ == "__main__":
    unittest.main()
