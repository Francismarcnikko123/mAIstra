"""Pre-extraction on arrival: read new papers in the background.

When enabled (AUTO_EXTRACT=true in .env), a thread started with the OCR server
polls Supabase for papers that have no OCR text and no teacher text yet, runs
the SAME extraction as the "Extract" button on each one, and saves
`extracted_text`. The teacher then opens a paper that is already read.

Guarantees (see docs/superpowers/plans/2026-09-24-pre-extraction-on-arrival.md):
- Never overwrites work: the save is a conditional update that only goes
  through if `extracted_text` and `verified_text` are still empty at that
  moment. A paper the teacher got to first is skipped, not an error.
- Writes `extracted_text` only -- never `verified_text`, `answers` or `status`.
  The web already shows a paper as extracted once `extracted_text` is set.
- Same pipeline and settings as the endpoint, so the recorded accuracy numbers
  still describe what teachers get.
- A paper that keeps failing is given up after a few tries (until restart) and
  stays "Needs OCR" for the teacher's manual extract.
- Only papers captured after a start date are read: by default the moment the
  server starts, or AUTO_EXTRACT_SINCE from .env to catch up after downtime.
  Older unread papers (the shared database had 204 of 209 on 2026-09-24,
  mostly test data) are never touched unless someone sets an early date.

Only stdlib is imported at module load, so tests can use it without Supabase
or PaddleOCR; the Supabase client is imported inside SupabaseStore.
"""
import csv
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol

TIMINGS_CSV = Path("outputs") / "auto_extract_timings.csv"


def _log(message: str) -> None:
    print(f"[auto-extract] {message}", flush=True)


@dataclass(frozen=True)
class AutoExtractConfig:
    enabled: bool = False
    interval_seconds: float = 10.0
    batch_size: int = 5
    max_failures: int = 3
    # Only papers captured at or after this moment. None = no limit (tests).
    since: Optional[datetime] = None


def _parse_since(value) -> Optional[datetime]:
    """An ISO date or date-time from .env, as an aware UTC datetime, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _positive(value, default, cast):
    try:
        number = cast(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def config_from_env(env: Mapping[str, str], started_at: Optional[datetime] = None) -> AutoExtractConfig:
    """Off unless AUTO_EXTRACT is true/1/yes/on. Bad numbers fall back to defaults.

    `since` is AUTO_EXTRACT_SINCE when set and valid, otherwise `started_at`
    (the server start), so a fresh start never reads the old backlog.
    """
    enabled = str(env.get("AUTO_EXTRACT", "")).strip().lower() in ("1", "true", "yes", "on")
    return AutoExtractConfig(
        enabled=enabled,
        interval_seconds=_positive(env.get("AUTO_EXTRACT_INTERVAL_SECONDS"), 10.0, float),
        since=_parse_since(env.get("AUTO_EXTRACT_SINCE")) or started_at,
    )


class PaperStore(Protocol):
    def pending(self, limit: int, since: Optional[datetime] = None) -> list[dict]: ...
    def save_extracted_text(self, submission_id: str, text: str) -> bool: ...


def _arrival_delay(captured_at, now: float) -> Optional[float]:
    """Seconds from the paper's capture time to now, or None if unparseable."""
    try:
        arrived = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if arrived.tzinfo is None:
        arrived = arrived.replace(tzinfo=timezone.utc)
    return round(now - arrived.timestamp(), 1)


def run_once(
    store: PaperStore,
    extract: Callable[[str], dict],
    failures: dict,
    config: AutoExtractConfig = AutoExtractConfig(enabled=True),
    now: Callable[[], float] = time.time,
    log: Callable[[str], None] = _log,
    record: Optional[Callable[[dict], None]] = None,
) -> int:
    """One polling pass. Returns how many papers were saved.

    `failures` maps submission id -> failed attempts and persists between
    passes; papers at `config.max_failures` are skipped from then on.
    """
    given_up = {sid for sid, count in failures.items() if count >= config.max_failures}
    # Ask for enough rows that given-up papers can't starve newer ones.
    candidates = [
        paper for paper in store.pending(config.batch_size + len(given_up), config.since)
        if paper.get("id") not in given_up
    ][: config.batch_size]

    saved = 0
    for paper in candidates:
        submission_id = paper["id"]
        started = now()
        try:
            text = extract(paper["image_url"])["cleaned_text"] or ""
            if store.save_extracted_text(submission_id, text):
                result = "saved"
                saved += 1
                failures.pop(submission_id, None)
            else:
                result = "skipped: already filled in"
        except Exception as exc:  # one bad paper must not stop the others
            failures[submission_id] = failures.get(submission_id, 0) + 1
            result = f"failed ({failures[submission_id]}/{config.max_failures}): {type(exc).__name__}"
        finished = now()
        row = {
            "submission_id": submission_id,
            "result": result.split(":")[0].split(" (")[0],
            "extract_seconds": round(finished - started, 1),
            "arrival_to_done_seconds": _arrival_delay(paper.get("captured_at"), finished),
        }
        log(
            f"{submission_id}: {result} in {row['extract_seconds']}s"
            + (f", {row['arrival_to_done_seconds']}s after arrival"
               if row["arrival_to_done_seconds"] is not None else "")
        )
        if record is not None:
            record(row)
    return saved


def csv_recorder(path: Path = TIMINGS_CSV) -> Callable[[dict], None]:
    """Append timing rows (ids and seconds only, no text) for the thesis."""
    fields = ["logged_at", "submission_id", "result", "extract_seconds", "arrival_to_done_seconds"]

    def record(row: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_file = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                if new_file:
                    writer.writeheader()
                writer.writerow({"logged_at": datetime.now(timezone.utc).isoformat(), **row})
        except OSError:
            pass  # timings are a diagnostic; never break extraction over them

    return record


class SupabaseStore:
    """Reads unextracted papers and saves OCR text with a conditional update."""

    COLUMNS = "id, image_url, captured_at"

    def __init__(self, url: str, key: str, client=None):
        if client is None:
            from supabase import create_client  # imported lazily on purpose
            client = create_client(url, key)
        self._client = client

    @staticmethod
    def _still_unread(query):
        # No teacher text, and no OCR text (NULL, or an empty string).
        return query.is_("verified_text", "null").or_("extracted_text.is.null,extracted_text.eq.")

    def pending(self, limit: int, since: Optional[datetime] = None) -> list[dict]:
        query = self._client.table("submissions").select(self.COLUMNS).not_.is_("image_url", "null")
        if since is not None:
            query = query.gte("captured_at", since.isoformat())
        response = self._still_unread(query).order("captured_at").limit(limit).execute()
        return list(response.data or [])

    def save_extracted_text(self, submission_id: str, text: str) -> bool:
        query = self._client.table("submissions").update({"extracted_text": text}).eq("id", submission_id)
        response = self._still_unread(query).execute()
        return bool(response.data)


class AutoExtractWorker:
    """Runs run_once every interval on a daemon thread until stopped."""

    def __init__(self, config, store, extract, log=_log, record=None):
        self.config = config
        self.store = store
        self.extract = extract
        self.log = log
        self.record = record
        self.failures: dict = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="auto-extract", daemon=True)

    def start(self) -> "AutoExtractWorker":
        self._thread.start()
        return self

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                run_once(self.store, self.extract, self.failures, self.config,
                         log=self.log, record=self.record)
            except Exception as exc:  # e.g. Supabase unreachable; try again next pass
                self.log(f"pass failed: {type(exc).__name__}: {exc}")
            self._stop.wait(self.config.interval_seconds)


def start_auto_extract(
    env: Mapping[str, str],
    extract: Callable[[str], dict],
    store_factory=SupabaseStore,
    record: Optional[Callable[[dict], None]] = None,
) -> Optional[AutoExtractWorker]:
    """Start the worker if AUTO_EXTRACT is on and Supabase is configured."""
    config = config_from_env(env, started_at=datetime.now(timezone.utc))
    if not config.enabled:
        return None
    url, key = env.get("SUPABASE_URL", ""), env.get("SUPABASE_KEY", "")
    if not url or not key:
        _log("AUTO_EXTRACT is on but SUPABASE_URL / SUPABASE_KEY are missing; not starting.")
        return None
    worker = AutoExtractWorker(
        config, store_factory(url, key), extract,
        record=record if record is not None else csv_recorder(),
    )
    _log(f"started: checking every {config.interval_seconds:g}s "
         f"for papers captured since {config.since.isoformat(timespec='minutes')}")
    return worker.start()
