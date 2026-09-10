from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from queue import Empty, Queue
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".dana"
DB = STATE / "runtime.db"


class TTLCache:
    def __init__(self, max_items: int = 512):
        self.max_items = max_items
        self.items: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self.lock:
            item = self.items.get(key)
            if item is None or item[0] < now:
                self.items.pop(key, None)
                self.misses += 1
                return None
            self.items.move_to_end(key)
            self.hits += 1
            return item[1]

    def put(self, key: str, value: Any, ttl: float) -> None:
        with self.lock:
            self.items[key] = (time.monotonic() + ttl, value)
            self.items.move_to_end(key)
            while len(self.items) > self.max_items:
                self.items.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self.lock:
            return {"entries": len(self.items), "hits": self.hits, "misses": self.misses}


CACHE = TTLCache()
CALL_LIMIT = max(1, int(__import__("os").getenv("DANA_MAX_CONCURRENCY", "8")))
SEMAPHORE = asyncio.Semaphore(CALL_LIMIT)
QUEUE: Queue[tuple[float, str, float, int]] = Queue(maxsize=10000)
STOP = threading.Event()
WORKER_STARTED = False
WORKER_LOCK = threading.Lock()


def _conn() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("CREATE TABLE IF NOT EXISTS events(ts REAL, tool TEXT, duration_ms REAL, success INTEGER)")
    return conn


def _writer() -> None:
    conn = _conn()
    batch: list[tuple[float, str, float, int]] = []
    try:
        while not STOP.is_set():
            try:
                batch.append(QUEUE.get(timeout=0.25))
            except Empty:
                pass
            if len(batch) >= 32 or (batch and STOP.is_set()):
                conn.executemany("INSERT INTO events VALUES(?,?,?,?)", batch)
                conn.commit()
                batch.clear()
    finally:
        if batch:
            conn.executemany("INSERT INTO events VALUES(?,?,?,?)", batch)
            conn.commit()
        conn.close()


def start_writer() -> None:
    global WORKER_STARTED
    with WORKER_LOCK:
        if not WORKER_STARTED:
            threading.Thread(target=_writer, daemon=True, name="dana-telemetry").start()
            WORKER_STARTED = True


def record(tool: str, duration_ms: float, success: bool) -> None:
    start_writer()
    try:
        QUEUE.put_nowait((time.time(), tool, duration_ms, int(success)))
    except Exception:
        pass


async def bounded(coro):
    async with SEMAPHORE:
        return await coro


def runtime_stats() -> dict[str, Any]:
    return {"concurrency": CALL_LIMIT, "queue_depth": QUEUE.qsize(), "cache": CACHE.stats()}
