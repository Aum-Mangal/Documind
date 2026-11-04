"""In-process fan-out of document progress events to open SSE streams.

The worker runs in the same process as the API, so an asyncio queue per subscriber is
enough. Progress is also written to the documents table, so a page that reconnects (or a
second API instance) still sees the latest state. With several API instances this is the
piece to swap for Redis pub/sub.
"""
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ProgressBus:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, document_id: int, event: dict) -> None:
        for queue in list(self._subscribers.get(document_id, ())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # a stalled client misses intermediate progress; the final state still reaches it

    @asynccontextmanager
    async def subscribe(self, document_id: int) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[document_id].add(queue)
        try:
            yield queue
        finally:
            self._subscribers[document_id].discard(queue)
            if not self._subscribers[document_id]:
                del self._subscribers[document_id]


progress_bus = ProgressBus()
