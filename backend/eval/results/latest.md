# Retrieval evaluation

Run 2026-11-04T09:43:55+00:00 on a **synthetic** corpus of 6 fictional documents (25 PDF pages, 16 chunks) with 66 labelled questions and 8 unanswerable ones. Embeddings `BAAI/bge-small-en-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`, top 30 candidates. Latency covers query embedding, search and (where used) reranking, on the machine that ran it.

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | Page acc.@1 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| vector | 82% | 97% | 98% | 100% | 0.894 | 82% | 8.0 | 9.1 |
| keyword | 67% | 94% | 96% | 98% | 0.802 | 67% | 7.1 | 8.5 |
| hybrid | 82% | 97% | 98% | 100% | 0.896 | 82% | 7.2 | 8.5 |
| hybrid+rerank | 89% | 97% | 98% | 100% | 0.936 | 89% | 324.3 | 362.8 |

Recall@5 by question type:

| Mode | distractor | exact | lookup | numeric | paraphrase |
|---|---|---|---|---|---|
| vector | 100% | 100% | 100% | 100% | 94% |
| keyword | 100% | 100% | 100% | 100% | 83% |
| hybrid | 100% | 100% | 100% | 100% | 94% |
| hybrid+rerank | 100% | 100% | 100% | 100% | 94% |

Abstention (hybrid+rerank, threshold -9.0): 98% of answerable questions answered, 38% of unanswerable questions declined.
Wrongly declined: hr-13.
Answered although unanswerable: none-02, none-03, none-04, none-07, none-08.

End to end with the LLM (openai/gpt-oss-20b, 70 calls, 107,745 tokens): 97% of answerable questions answered, 100% of those citing a passage that contains the evidence, 100% of unanswerable questions declined.
Declined although answerable: board-15, hr-13.

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
