"""Download the embedding and reranker models (run at Docker build time).

Model names come from the same environment variables the app reads, with the app's defaults.
"""
import os

from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

embedding = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
reranker = os.environ.get("RERANKER_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")

list(TextEmbedding(model_name=embedding).embed(["warm up"]))
list(TextCrossEncoder(model_name=reranker).rerank("warm up", ["warm up"]))
print(f"Downloaded {embedding} and {reranker} to {os.environ.get('FASTEMBED_CACHE_PATH')}")
