"""Upload → queue → worker → chunks, against a real database."""
from datetime import UTC, datetime, timedelta

import fitz
from sqlalchemy import func, select, text, update

from app.db.models import Chunk, Document
from tests.integration.conftest import make_user, run

REPORT_PAGES = [
    "Halden & Rowe quarterly report. Revenue rose 14 percent in the third quarter, led by the Lisbon "
    "office, where new enterprise contracts added 4.2 million dollars. Part number ZX-4471 shipped early.",
    "The board appointed Maria Okafor as chief operating officer, effective November. Daniel Weiss "
    "will lead the new Porto office.",
    "The Atlas product launch moved to next quarter because Northwind Supply could not deliver the "
    "revised components on time.",
]


def make_pdf(pages: list[str] = REPORT_PAGES) -> bytes:
    doc = fitz.open()
    for body in pages:
        doc.new_page().insert_textbox(fitz.Rect(72, 72, 520, 760), body)
    return doc.tobytes()


def upload(api, headers, name="report.pdf", data=None):
    return api.post("/api/documents", headers=headers, files={"file": (name, data or make_pdf(), "application/pdf")})


def doc_row(session_factory, doc_id):
    async def get():
        async with session_factory() as session:
            return await session.get(Document, doc_id)
    return run(get())


def chunk_rows(session_factory, doc_id):
    async def get():
        async with session_factory() as session:
            return list((await session.execute(
                select(Chunk).where(Chunk.document_id == doc_id).order_by(Chunk.ord))).scalars())
    return run(get())


def test_upload_is_queued_then_processed_into_page_numbered_chunks(api, worker, session_factory):
    headers = make_user(api)
    response = upload(api, headers)
    assert response.status_code == 202
    body = response.json()
    assert body["duplicate"] is False
    doc_id = body["document"]["id"]
    assert body["document"]["status"] == "queued"

    assert run(worker.run_until_idle()) == 1

    doc = doc_row(session_factory, doc_id)
    assert (doc.status, doc.progress, doc.error, doc.page_count) == ("ready", 100, None, 3)
    assert doc.summary == "A short summary."
    chunks = chunk_rows(session_factory, doc_id)
    assert chunks and all(c.embedding is not None and len(c.embedding) == 384 for c in chunks)
    assert chunks[0].page_start == 1 and chunks[-1].page_end == 3
    assert "Maria Okafor" in " ".join(c.content for c in chunks)

    # The original is stored and downloadable byte for byte
    original = api.get(f"/api/documents/{doc_id}/file", headers=headers)
    assert original.status_code == 200 and original.content.startswith(b"%PDF-")
    assert "report.pdf" in original.headers["content-disposition"]


def test_the_same_file_twice_is_stored_once(api, worker):
    headers = make_user(api)
    data = make_pdf()
    first = upload(api, headers, data=data).json()["document"]["id"]
    second = upload(api, headers, name="renamed.pdf", data=data)
    assert second.status_code == 200
    assert second.json() == {**second.json(), "duplicate": True}
    assert second.json()["document"]["id"] == first
    # ...but another user can upload the same file
    other = make_user(api, "other@documind.dev")
    assert upload(api, other, data=data).status_code == 202


def test_a_pdf_without_text_fails_with_a_clear_message(api, worker, session_factory):
    headers = make_user(api)
    blank = fitz.open()
    blank.new_page()
    doc_id = upload(api, headers, name="blank.pdf", data=blank.tobytes()).json()["document"]["id"]
    run(worker.run_until_idle())
    doc = doc_row(session_factory, doc_id)
    assert doc.status == "failed"
    assert doc.error and ("No readable text" in doc.error or "OCR" in doc.error)
    assert chunk_rows(session_factory, doc_id) == []


def test_temporary_failures_retry_with_backoff(api, worker, session_factory, monkeypatch):
    import app.ingestion.pipeline as pipeline

    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]

    real_embed = pipeline.embed_passages
    calls = {"n": 0}

    def flaky(texts, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model server hiccup")
        return real_embed(texts, **kwargs)

    monkeypatch.setattr(pipeline, "embed_passages", flaky)

    run(worker.run_until_idle())
    doc = doc_row(session_factory, doc_id)
    assert doc.status == "queued" and doc.attempts == 1
    assert doc.run_after > datetime.now(UTC) + timedelta(seconds=20)
    assert "retrying" in doc.error

    # Not due yet: nothing is picked up
    assert run(worker.run_until_idle()) == 0

    async def make_due():
        async with session_factory() as session:
            await session.execute(update(Document).where(Document.id == doc_id).values(run_after=func.now()))
            await session.commit()
    run(make_due())
    run(worker.run_until_idle())
    doc = doc_row(session_factory, doc_id)
    assert (doc.status, doc.attempts, doc.error) == ("ready", 2, None)


def test_gives_up_after_the_last_attempt(api, worker, session_factory, monkeypatch):
    import app.ingestion.pipeline as pipeline
    from app.core.config import get_settings

    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]
    monkeypatch.setattr(pipeline, "embed_passages", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("always")))

    async def make_due():
        async with session_factory() as session:
            await session.execute(update(Document).where(Document.id == doc_id).values(run_after=func.now()))
            await session.commit()

    for _ in range(get_settings().ingest_max_attempts):
        run(worker.run_until_idle())
        run(make_due())
    doc = doc_row(session_factory, doc_id)
    assert doc.status == "failed" and "Try reprocessing" in doc.error


def test_a_job_left_processing_by_a_crash_is_picked_up_again(api, worker, session_factory):
    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]

    async def simulate_crash(minutes_ago):
        async with session_factory() as session:
            await session.execute(text(
                "UPDATE documents SET status='processing', attempts=1, locked_at=now() - make_interval(mins => :m) WHERE id=:id"
            ), {"m": minutes_ago, "id": doc_id})
            await session.commit()

    run(simulate_crash(1))
    assert run(worker.run_until_idle()) == 0  # still locked by the (supposedly) live worker
    run(simulate_crash(60))
    assert run(worker.run_until_idle()) == 1
    assert doc_row(session_factory, doc_id).status == "ready"


def test_concurrent_workers_never_claim_the_same_document(api, worker, session_factory):
    import asyncio

    from app.ingestion.worker import IngestionWorker

    headers = make_user(api)
    ids = {upload(api, headers, name=f"r{i}.pdf", data=make_pdf([f"Report number {i}. " * 20])).json()["document"]["id"]
           for i in range(4)}

    async def claim_all():
        workers = [IngestionWorker(session_factory) for _ in range(4)]
        return await asyncio.gather(*(w._claim() for w in workers))

    claimed = [job[0] for job in run(claim_all()) if job]
    assert sorted(claimed) == sorted(ids)  # four workers, four different documents


def test_documents_from_before_file_storage_are_rebuilt_from_saved_text(api, worker, session_factory):
    make_user(api)

    async def legacy_doc():
        async with session_factory() as session:
            doc = Document(user_id=1, filename="old.txt", raw_text="An old note about the Lisbon office. " * 5,
                           summary="Kept summary.", status="queued")
            session.add(doc)
            await session.commit()
            return doc.id

    doc_id = run(legacy_doc())
    run(worker.run_until_idle())
    doc = doc_row(session_factory, doc_id)
    assert doc.status == "ready" and doc.summary == "Kept summary."
    assert chunk_rows(session_factory, doc_id)


def test_reprocess_and_delete(api, worker, session_factory):
    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]
    assert api.post(f"/api/documents/{doc_id}/reprocess", headers=headers).status_code == 409  # still queued
    run(worker.run_until_idle())

    assert api.post(f"/api/documents/{doc_id}/reprocess", headers=headers).json()["status"] == "queued"
    run(worker.run_until_idle())
    assert doc_row(session_factory, doc_id).status == "ready"

    other = make_user(api, "intruder@documind.dev")
    assert api.delete(f"/api/documents/{doc_id}", headers=other).status_code == 404

    assert api.delete(f"/api/documents/{doc_id}", headers=headers).status_code == 204
    assert doc_row(session_factory, doc_id) is None
    assert chunk_rows(session_factory, doc_id) == []
    assert api.get(f"/api/documents/{doc_id}/file", headers=headers).status_code == 404


def test_progress_stream_reports_the_final_state(api, worker):
    headers = make_user(api)
    doc_id = upload(api, headers).json()["document"]["id"]
    run(worker.run_until_idle())
    with api.stream("GET", f"/api/documents/{doc_id}/events", headers=headers) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        first = next(line for line in response.iter_lines() if line.startswith("data:"))
    assert '"status": "ready"' in first and '"progress": 100' in first
