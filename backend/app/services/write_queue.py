"""
Batch write queue — decouples real-time broadcast from disk persistence.

OPTIMIZATION (Phase 5): Sensor data is queued and flushed to the DB in
batches on a background timer.  The WebSocket broadcast happens immediately
(sub-millisecond), so the driver's cuboid overlay is never delayed by disk I/O.

Think of it like a GPU command buffer: you batch draw calls and submit once,
rather than flushing after every triangle.
"""
import asyncio
import logging
from typing import Callable, Awaitable, Any
from collections import deque

logger = logging.getLogger(__name__)


class WriteQueue:
    """Accumulates DB-write work items and flushes them in batches."""

    def __init__(self, flush_interval_ms: int = 500, max_batch_size: int = 64):
        self._queue: deque = deque()
        self._flush_interval = flush_interval_ms / 1000.0
        self._max_batch = max_batch_size
        self._task: asyncio.Task | None = None
        self._running = False
        self._flush_fn: Callable[[list], Awaitable[Any]] | None = None

    def set_flush_callback(self, fn: Callable[[list], Awaitable[Any]]):
        """Set the async function that receives a batch of work items."""
        self._flush_fn = fn

    def enqueue(self, item: Any):
        """Add a work item (non-blocking, lock-free for single-producer)."""
        self._queue.append(item)

    async def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"WriteQueue started (interval={self._flush_interval*1000:.0f}ms, "
            f"batch={self._max_batch})"
        )

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final drain
        await self._flush()
        logger.info("WriteQueue stopped, final flush done")

    async def _run(self):
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush()

    async def _flush(self):
        if not self._queue or not self._flush_fn:
            return
        # Drain up to max_batch items
        batch = []
        while self._queue and len(batch) < self._max_batch:
            batch.append(self._queue.popleft())
        if batch:
            try:
                await self._flush_fn(batch)
            except Exception as e:
                logger.error(f"WriteQueue flush error: {e}")

    @property
    def pending(self) -> int:
        return len(self._queue)


write_queue = WriteQueue()
