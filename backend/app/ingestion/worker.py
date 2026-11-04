"""The ingestion worker: a crash-safe job queue on the documents table.

Jobs are claimed with FOR UPDATE SKIP LOCKED, so several workers (or API instances) never
process the same document twice. A job left 'processing' by a crash is picked up again once
its lock is older than INGEST_STALE_MINUTES. Failures retry with exponential backoff.

The worker doesn't poll on a timer: uploads wake it directly, and when idle it sleeps until
the next scheduled retry (or a long safety-net interval). That keeps a serverless database
like Neon free to scale to zero.
"""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.models import Document
from app.db.session import SessionLocal
from app.ingestion.pipeline import process_document, set_state
from app.services.ocr import ExtractionError

logger = logging.getLogger(__name__)

RETRY_BASE_SECONDS = 30

_CLAIM_SQL = text("""
    UPDATE documents
       SET status = 'processing', stage = 'parsing', progress = 0,
           locked_at = now(), attempts = attempts + 1, updated_at = now()
     WHERE id = (
           SELECT id FROM documents
            WHERE (status = 'queued' AND run_after <= now())
               OR (status = 'processing' AND locked_at < now() - make_interval(mins => :stale_minutes))
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1)
 RETURNING id, attempts
""")


class IngestionWorker:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory
        self._wake = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._run(), name="ingestion-worker")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except TimeoutError:
                self._task.cancel()
            self._task = None

    def wake(self) -> None:
        self._wake.set()

    async def run_until_idle(self) -> int:
        """Process every job that is ready now. Returns how many were handled."""
        handled = 0
        while not self._stopping and (job := await self._claim()):
            await self._handle(*job)
            handled += 1
        return handled

    async def _run(self) -> None:
        while not self._stopping:
            # Clear before looking for work, so a wake-up during the drain isn't lost
            self._wake.clear()
            try:
                await self.run_until_idle()
                timeout = await self._seconds_until_next_job()
            except Exception:
                logger.exception("Ingestion worker loop failed; retrying shortly")
                timeout = 10
            if self._stopping:
                break
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
            except TimeoutError:
                pass

    async def _claim(self) -> tuple[int, int] | None:
        async with self.session_factory() as session:
            row = (await session.execute(_CLAIM_SQL, {"stale_minutes": get_settings().ingest_stale_minutes})).first()
            await session.commit()
        return (row.id, row.attempts) if row else None

    async def _seconds_until_next_job(self) -> float | None:
        settings = get_settings()
        stale = timedelta(minutes=settings.ingest_stale_minutes)
        async with self.session_factory() as session:
            next_retry = (await session.execute(
                select(func.min(Document.run_after)).where(Document.status == "queued")
            )).scalar()
            next_stale = (await session.execute(
                select(func.min(Document.locked_at)).where(Document.status == "processing")
            )).scalar()
            now = (await session.execute(select(func.now()))).scalar()

        waits = [(t - now).total_seconds() for t in (next_retry, next_stale + stale if next_stale else None) if t]
        if settings.worker_idle_poll_seconds > 0:
            waits.append(settings.worker_idle_poll_seconds)
        return max(1.0, min(waits)) if waits else None

    async def _handle(self, doc_id: int, attempts: int) -> None:
        settings = get_settings()
        if attempts > settings.ingest_max_attempts:
            # Kept crashing the worker itself (e.g. out of memory) before it could record a failure
            await self._fail(doc_id, "Processing stopped repeatedly. Try reprocessing the document.")
            return
        try:
            await process_document(self.session_factory, doc_id)
        except ExtractionError as e:
            await self._fail(doc_id, str(e))
        except Exception:
            logger.exception("Processing document %s failed (attempt %d)", doc_id, attempts)
            if attempts >= settings.ingest_max_attempts:
                await self._fail(doc_id, f"Processing failed after {attempts} attempts. Try reprocessing the document.")
            else:
                delay = RETRY_BASE_SECONDS * 2 ** (attempts - 1)
                await set_state(
                    self.session_factory, doc_id, status="queued", stage=None, progress=0, locked_at=None,
                    error="A temporary error interrupted processing; retrying shortly.",
                    run_after=func.now() + timedelta(seconds=delay),
                )

    async def _fail(self, doc_id: int, message: str) -> None:
        await set_state(self.session_factory, doc_id, status="failed", stage=None, locked_at=None, error=message)


worker = IngestionWorker()
