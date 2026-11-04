# Retrieval evaluation

Run 2026-11-04T10:03:13+00:00 on a **synthetic** corpus of 6 fictional documents (25 PDF pages, 16 chunks) with 66 labelled questions and 8 unanswerable ones. Embeddings `BAAI/bge-small-en-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`, top 30 candidates. Latency covers query embedding, search and (where used) reranking, on the machine that ran it.

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Page acc.@1 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| vector | 82% | 97% | 98% | 100% | 0.894 | 82% | 9.3 | 17.6 |
| keyword | 67% | 94% | 96% | 98% | 0.802 | 67% | 8.5 | 14.3 |
| hybrid | 82% | 97% | 98% | 100% | 0.896 | 82% | 8.8 | 16.1 |
| hybrid+rerank | 89% | 97% | 98% | 100% | 0.936 | 89% | 411.6 | 623.9 |
| hybrid+graph | 73% | 86% | 98% | 100% | 0.822 | 73% | 9.6 | 22.9 |
| hybrid+graph+rerank | 89% | 97% | 98% | 100% | 0.936 | 89% | 414.8 | 587.6 |

Recall@5 by question type:

| Mode | distractor | exact | lookup | numeric | paraphrase |
|---|---|---|---|---|---|
| vector | 100% | 100% | 100% | 100% | 94% |
| keyword | 100% | 100% | 100% | 100% | 83% |
| hybrid | 100% | 100% | 100% | 100% | 94% |
| hybrid+rerank | 100% | 100% | 100% | 100% | 94% |
| hybrid+graph | 100% | 100% | 100% | 100% | 94% |
| hybrid+graph+rerank | 100% | 100% | 100% | 100% | 94% |

Abstention (hybrid+rerank, threshold -9.0): 98% of answerable questions answered, 38% of unanswerable questions declined.
Wrongly declined: hr-13.
Answered although unanswerable: none-02, none-03, none-04, none-07, none-08.

Threshold trade-off (reranker score below which the app declines without calling the LLM):

| Threshold | Answerable answered | Unanswerable declined |
|---|---|---|
| -10.0 | 98% | 38% |
| -9.0 | 98% | 38% |
| -8.0 | 96% | 38% |
| -7.0 | 94% | 38% |
| -6.0 | 89% | 38% |
| -5.0 | 85% | 50% |
| -4.0 | 83% | 62% |
| -3.0 | 80% | 62% |
| -2.0 | 80% | 62% |
| 0.0 | 64% | 88% |
