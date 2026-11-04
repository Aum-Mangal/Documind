"""Retrieval evaluation: recall@k, MRR, page accuracy, abstention and latency per search mode.

The corpus (eval/corpus/*.md, one document per file, pages split by a <<<PAGE>>> line) is
rendered to PDFs and ingested through the real pipeline: same extraction, chunking and
embedding models as production. Each labelled question names the document and an exact
evidence phrase; a retrieved passage counts as a hit when it comes from that document and
contains the phrase.

    python -m eval.run --database-url postgresql://documind:documind@localhost:5432/documind_eval

The named database is dropped and recreated. No LLM is called: retrieval and abstention are
measured on their own, so results are deterministic and free to reproduce.
"""
import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND_DIR = EVAL_DIR.parent
PAGE_BREAK = "<<<PAGE>>>"
MODES = ["vector", "keyword", "hybrid", "hybrid+rerank", "hybrid+graph", "hybrid+graph+rerank"]
KS = (1, 3, 5, 10)


def normalise(text: str) -> str:
    return " ".join(text.lower().split())


def load_corpus() -> dict[str, list[str]]:
    corpus = {}
    for path in sorted((EVAL_DIR / "corpus").glob("*.md")):
        pages = [p.strip() for p in path.read_text(encoding="utf-8").split(PAGE_BREAK)]
        corpus[path.stem] = [p for p in pages if p]
    return corpus


def load_questions() -> list[dict]:
    lines = (EVAL_DIR / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def render_pdf(pages: list[str]) -> bytes:
    import fitz

    doc = fitz.open()
    for number, body in enumerate(pages, start=1):
        page = doc.new_page()
        # The built-in font covers Latin-1; swap the few typographic characters it lacks
        text = body.replace("—", "-").replace("’", "'")
        overflow = page.insert_textbox(fitz.Rect(56, 56, 540, 790), text, fontsize=10)
        if overflow < 0:
            raise ValueError(f"Page {number} doesn't fit on one PDF page; shorten it")
    return doc.tobytes()


def recreate_database(url: str) -> None:
    from urllib.parse import urlsplit, urlunsplit

    import asyncpg

    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    admin = urlunsplit((parts.scheme.split("+")[0], parts.netloc, "/postgres", "", ""))

    async def go():
        conn = await asyncpg.connect(admin)
        try:
            await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    asyncio.run(go())
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR,
                   env={**os.environ, "DATABASE_URL": url}, check=True, capture_output=True)


@dataclass
class ModeResult:
    ranks: list[int | None] = field(default_factory=list)
    page_hits: list[bool] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    by_type: dict[str, list[int | None]] = field(default_factory=dict)

    def recall(self, k: int, ranks=None) -> float:
        ranks = self.ranks if ranks is None else ranks
        return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)

    def mrr(self, k: int = 10) -> float:
        return sum(1 / r for r in self.ranks if r is not None and r <= k) / len(self.ranks)

    def summary(self) -> dict:
        lat = sorted(self.latencies_ms)
        return {
            **{f"recall@{k}": round(self.recall(k), 3) for k in KS},
            "mrr@10": round(self.mrr(), 3),
            "page_accuracy@1": round(sum(self.page_hits) / len(self.page_hits), 3) if self.page_hits else None,
            "latency_p50_ms": round(statistics.median(lat), 1),
            "latency_p95_ms": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 1),
            "recall@5_by_type": {t: round(self.recall(5, r), 3) for t, r in sorted(self.by_type.items())},
        }


async def evaluate(database_url: str, with_llm: bool = False) -> dict:
    from sqlalchemy import NullPool, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings, to_asyncpg_url
    from app.db.models import Chunk, Document, User
    from app.ingestion.worker import IngestionWorker
    from app.retrieval.search import hybrid_search
    from app.services.embeddings import embed_query, rerank
    from app.services.storage import get_storage

    settings = get_settings()
    corpus, questions = load_corpus(), load_questions()
    engine = create_async_engine(to_asyncpg_url(database_url), poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    # ── Ingest the corpus through the real pipeline ──
    started = time.perf_counter()
    async with sessions() as session:
        user = User(email="eval@documind.dev", password="-")
        session.add(user)
        await session.flush()
        for stem, pages in corpus.items():
            filename = f"{stem}.pdf"
            doc = Document(user_id=user.id, filename=filename, status="queued", mime_type="application/pdf",
                           summary="(evaluation: summaries skipped)")
            session.add(doc)
            await session.flush()
            doc.storage_key = f"eval/{doc.id}/{filename}"
            get_storage().put(doc.storage_key, render_pdf(pages), "application/pdf")
        await session.commit()
        user_id = user.id
    await IngestionWorker(sessions).run_until_idle()
    ingest_seconds = time.perf_counter() - started

    async with sessions() as session:
        docs = {d.filename: d for d in (await session.execute(select(Document))).scalars()}
        failed = [f"{d.filename}: {d.error}" for d in docs.values() if d.status != "ready"]
        if failed:
            raise SystemExit("Ingestion failed:\n" + "\n".join(failed))
        chunks = list((await session.execute(select(Chunk))).scalars())
    by_doc_id = {d.id: d.filename for d in docs.values()}
    text_by_doc: dict[str, str] = {}
    for c in chunks:
        text_by_doc[by_doc_id[c.document_id]] = text_by_doc.get(by_doc_id[c.document_id], "") + " " + c.content

    # Every label must be findable at all; otherwise the label (or extraction) is wrong
    answerable = [q for q in questions if q["type"] != "unanswerable"]
    unanswerable = [q for q in questions if q["type"] == "unanswerable"]
    bad = [q["id"] for q in answerable if normalise(q["evidence"]) not in normalise(text_by_doc.get(f"{q['doc']}.pdf", ""))]
    if bad:
        raise SystemExit(f"Evidence not found in the ingested text for: {', '.join(bad)}")

    # ── Score every mode ──
    results = {m: ModeResult() for m in MODES}
    # The mode the app uses; abstention and the quality gate are measured on it
    app_mode = "hybrid+graph+rerank" if settings.rrf_graph_weight > 0 else "hybrid+rerank"
    top_scores: dict[str, float] = {}
    async with sessions() as session:
        for q in questions:
            for mode in MODES:
                t0 = time.perf_counter()
                vector = embed_query(q["question"])
                candidates = await hybrid_search(
                    session, user_id, q["question"], vector, None,
                    limit=settings.retrieval_candidates, mode=mode.split("+")[0], use_graph="graph" in mode,
                )
                if mode.endswith("rerank") and candidates:
                    candidates = candidates[: settings.rerank_candidates]
                    scores = rerank(q["question"], [c.content for c in candidates])
                    order = sorted(range(len(candidates)), key=lambda i: scores[i], reverse=True)
                    candidates = [candidates[i] for i in order]
                    if mode == app_mode:
                        top_scores[q["id"]] = scores[order[0]]
                elapsed = (time.perf_counter() - t0) * 1000

                if q["type"] == "unanswerable":
                    continue
                evidence, filename = normalise(q["evidence"]), f"{q['doc']}.pdf"
                rank = next((i for i, c in enumerate(candidates[:10], start=1)
                             if c.filename == filename and evidence in normalise(c.content)), None)
                r = results[mode]
                r.ranks.append(rank)
                r.latencies_ms.append(elapsed)
                r.by_type.setdefault(q["type"], []).append(rank)
                if rank == 1:
                    top = candidates[0]
                    r.page_hits.append(top.page_start is not None and top.page_start <= q["page"] <= (top.page_end or top.page_start))
                elif candidates:
                    r.page_hits.append(False)

    end_to_end = await evaluate_answers(sessions, user_id, questions) if with_llm else None

    threshold = settings.min_rerank_score
    answered = [q for q in answerable if top_scores.get(q["id"], float("-inf")) >= threshold]
    declined = [q for q in unanswerable if top_scores.get(q["id"], float("-inf")) < threshold]
    await engine.dispose()

    return {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "corpus": {"documents": len(corpus), "pages": sum(len(p) for p in corpus.values()), "chunks": len(chunks),
                   "ingest_seconds": round(ingest_seconds, 1)},
        "questions": {"answerable": len(answerable), "unanswerable": len(unanswerable),
                      "by_type": {t: sum(1 for q in answerable if q["type"] == t) for t in sorted({q["type"] for q in answerable})}},
        "config": {"embedding_model": settings.embedding_model, "reranker_model": settings.reranker_model,
                   "chunk_target_tokens": settings.chunk_target_tokens, "candidates": settings.retrieval_candidates,
                   "min_rerank_score": threshold, "rrf_keyword_weight": settings.rrf_keyword_weight,
                   "rerank_candidates": settings.rerank_candidates, "llm_model": settings.groq_model if with_llm else None},
        "app_mode": app_mode,
        "modes": {m: results[m].summary() for m in MODES},
        "end_to_end": end_to_end,
        "abstention": {
            "answerable_answered": round(len(answered) / len(answerable), 3),
            "unanswerable_declined": round(len(declined) / len(unanswerable), 3),
            "wrongly_declined": sorted(q["id"] for q in answerable if q not in answered),
            "wrongly_answered": sorted(q["id"] for q in unanswerable if q not in declined),
            # What other thresholds would trade off, from the same scores
            "sweep": [
                {"threshold": t,
                 "answerable_answered": round(sum(top_scores.get(q["id"], float("-inf")) >= t for q in answerable) / len(answerable), 3),
                 "unanswerable_declined": round(sum(top_scores.get(q["id"], float("-inf")) < t for q in unanswerable) / len(unanswerable), 3)}
                for t in (-10.0, -9.0, -8.0, -7.0, -6.0, -5.0, -4.0, -3.0, -2.0, 0.0)
            ],
        },
    }


async def evaluate_answers(sessions, user_id: int, questions: list[dict]) -> dict:
    """The full pipeline with the real LLM: does it answer, and does it cite the right passage?"""
    import re

    from app.retrieval.answer import answer_question
    from app.services.llm import track_usage

    citation = re.compile(r"[\[【]\s*(?:Sources?\s+)?(\d+(?:\s*(?:,|and)\s*(?:Source\s+)?\d+)*)\s*[\]】]", re.I)
    rows = []
    with track_usage() as usage:
        async with sessions() as session:
            for q in questions:
                answer = await answer_question(session, user_id, q["question"], None, [])
                cited = {int(n) for group in citation.findall(answer.text) for n in re.findall(r"\d+", group)}
                correct_citation = None
                if q["type"] != "unanswerable" and not answer.abstained:
                    evidence, filename = normalise(q["evidence"]), f"{q['doc']}.pdf"
                    correct_citation = any(s.n in cited and s.filename == filename and evidence in normalise(s.text)
                                           for s in answer.sources)
                rows.append({"id": q["id"], "type": q["type"], "abstained": answer.abstained,
                             "cited": sorted(cited), "correct_citation": correct_citation})

    answerable = [r for r in rows if r["type"] != "unanswerable"]
    unanswerable = [r for r in rows if r["type"] == "unanswerable"]
    answered = [r for r in answerable if not r["abstained"]]
    return {
        "answerable_answered": round(len(answered) / len(answerable), 3),
        "answered_with_correct_citation": round(sum(bool(r["correct_citation"]) for r in answered) / max(1, len(answered)), 3),
        "unanswerable_declined": round(sum(r["abstained"] for r in unanswerable) / len(unanswerable), 3),
        "wrongly_declined": [r["id"] for r in answerable if r["abstained"]],
        "wrong_or_missing_citation": [r["id"] for r in answered if not r["correct_citation"]],
        "wrongly_answered": [r["id"] for r in unanswerable if not r["abstained"]],
        "llm_calls": usage.calls,
        "llm_tokens": usage.total_tokens,
    }


def markdown_report(r: dict) -> str:
    lines = [
        "# Retrieval evaluation",
        "",
        f"Run {r['run_at']} on a **synthetic** corpus of {r['corpus']['documents']} fictional documents "
        f"({r['corpus']['pages']} PDF pages, {r['corpus']['chunks']} chunks) with "
        f"{r['questions']['answerable']} labelled questions and {r['questions']['unanswerable']} unanswerable ones. "
        f"Embeddings `{r['config']['embedding_model']}`, reranker `{r['config']['reranker_model']}`, "
        f"top {r['config']['candidates']} candidates. Latency covers query embedding, search and (where used) reranking, "
        "on the machine that ran it.",
        "",
        "| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Page acc.@1 | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for mode, m in r["modes"].items():
        lines.append(f"| {mode} | {m['recall@1']:.0%} | {m['recall@3']:.0%} | {m['recall@5']:.0%} | {m['recall@10']:.0%} | "
                     f"{m['mrr@10']:.3f} | {m['page_accuracy@1']:.0%} | {m['latency_p50_ms']} | {m['latency_p95_ms']} |")
    types = list(r["modes"][r["app_mode"]]["recall@5_by_type"])
    lines += ["", "Recall@5 by question type:", "", "| Mode | " + " | ".join(types) + " |", "|---|" + "---|" * len(types)]
    for mode, m in r["modes"].items():
        lines.append(f"| {mode} | " + " | ".join(f"{m['recall@5_by_type'][t]:.0%}" for t in types) + " |")
    a = r["abstention"]
    lines += [
        "",
        f"Abstention ({r['app_mode']}, threshold {r['config']['min_rerank_score']}): "
        f"{a['answerable_answered']:.0%} of answerable questions answered, "
        f"{a['unanswerable_declined']:.0%} of unanswerable questions declined.",
    ]
    if a["wrongly_declined"]:
        lines.append(f"Wrongly declined: {', '.join(a['wrongly_declined'])}.")
    if a["wrongly_answered"]:
        lines.append(f"Answered although unanswerable: {', '.join(a['wrongly_answered'])}.")
    if e := r.get("end_to_end"):
        lines += [
            "",
            f"End to end with the LLM ({r['config'].get('llm_model', 'LLM')}, {e['llm_calls']} calls, {e['llm_tokens']:,} tokens): "
            f"{e['answerable_answered']:.0%} of answerable questions answered, "
            f"{e['answered_with_correct_citation']:.0%} of those citing a passage that contains the evidence, "
            f"{e['unanswerable_declined']:.0%} of unanswerable questions declined.",
        ]
        for key, label in (("wrongly_declined", "Declined although answerable"),
                           ("wrong_or_missing_citation", "Wrong or missing citation"),
                           ("wrongly_answered", "Answered although unanswerable")):
            if e[key]:
                lines.append(f"{label}: {', '.join(e[key])}.")
    lines += ["", "Threshold trade-off (reranker score below which the app declines without calling the LLM):", "",
              "| Threshold | Answerable answered | Unanswerable declined |", "|---|---|---|"]
    lines += [f"| {s['threshold']} | {s['answerable_answered']:.0%} | {s['unanswerable_declined']:.0%} |" for s in a["sweep"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", default=os.environ.get("EVAL_DATABASE_URL"), required=not os.environ.get("EVAL_DATABASE_URL"))
    parser.add_argument("--report", default=str(EVAL_DIR / "results" / "latest.md"))
    parser.add_argument("--min-recall-at-5", type=float, default=None, help="fail if the app's mode has recall@5 below this")
    parser.add_argument("--min-mrr", type=float, default=None, help="fail if the app's mode has MRR@10 below this")
    parser.add_argument("--with-llm", action="store_true",
                        help="also run every question through the LLM (uses GROQ_API_KEY; about 1.5k tokens per question)")
    args = parser.parse_args()

    # Configure the app for an isolated, LLM-free run before any app module reads settings
    os.environ.update({
        "DATABASE_URL": args.database_url,
        "SECRET_KEY": os.environ.get("SECRET_KEY") or "evaluation-only-secret-key-0123456789abcdef",
        "S3_ENDPOINT_URL": "", "REDIS_URL": "", "WORKER_ENABLED": "false",
        "LOCAL_STORAGE_DIR": tempfile.mkdtemp(prefix="documind-eval-"),
    })
    if not args.with_llm:
        os.environ["GROQ_API_KEY"] = ""  # retrieval-only runs never call the LLM
    recreate_database(args.database_url)
    result = asyncio.run(evaluate(args.database_url, with_llm=args.with_llm))

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown_report(result), encoding="utf-8")
    report.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(markdown_report(result))
    print(f"Report written to {report}")

    best = result["modes"][result["app_mode"]]
    failures = []
    if args.min_recall_at_5 is not None and best["recall@5"] < args.min_recall_at_5:
        failures.append(f"recall@5 {best['recall@5']} < {args.min_recall_at_5}")
    if args.min_mrr is not None and best["mrr@10"] < args.min_mrr:
        failures.append(f"MRR@10 {best['mrr@10']} < {args.min_mrr}")
    if failures:
        raise SystemExit("Quality gate failed: " + "; ".join(failures))


if __name__ == "__main__":
    main()
