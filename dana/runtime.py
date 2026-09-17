from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class RuntimeTask:
    id: str
    name: str
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


class TaskRuntime:
    """Bounded async DAG runtime used by Dana's orchestration tools."""

    def __init__(self, workers: int = 5) -> None:
        self.workers = max(1, min(128, int(workers)))
        self._semaphore = asyncio.Semaphore(self.workers)
        self._lock = asyncio.Lock()
        self._active = 0
        self._completed = 0
        self._failed = 0
        self._queued = 0

    async def _run_one(
        self,
        task: RuntimeTask,
        runner: Callable[[RuntimeTask], Awaitable[Any]],
    ) -> None:
        async with self._semaphore:
            async with self._lock:
                self._active += 1
                self._queued = max(0, self._queued - 1)
            task.status = "running"
            task.started_at = time.time()
            try:
                task.result = await runner(task)
                task.status = "done"
                self._completed += 1
            except Exception as exc:  # pragma: no cover - caller-facing safety boundary
                task.status = "failed"
                task.error = f"{type(exc).__name__}: {exc}"
                self._failed += 1
            finally:
                task.finished_at = time.time()
                async with self._lock:
                    self._active = max(0, self._active - 1)

    async def execute(
        self,
        tasks: list[RuntimeTask],
        runner: Callable[[RuntimeTask], Awaitable[Any]],
        fail_fast: bool = False,
    ) -> dict[str, Any]:
        by_id = {task.id: task for task in tasks}
        if len(by_id) != len(tasks):
            raise ValueError("Task IDs must be unique")
        for task in tasks:
            missing = [dep for dep in task.depends_on if dep not in by_id]
            if missing:
                raise ValueError(f"Task '{task.id}' depends on missing task(s): {missing}")

        self._queued += len(tasks)
        pending = set(by_id)
        running: dict[str, asyncio.Task[None]] = {}
        while pending or running:
            ready = [
                by_id[task_id]
                for task_id in list(pending)
                if all(by_id[dep].status == "done" for dep in by_id[task_id].depends_on)
            ]
            blocked = [
                by_id[task_id]
                for task_id in list(pending)
                if any(by_id[dep].status == "failed" for dep in by_id[task_id].depends_on)
            ]
            for task in blocked:
                task.status = "blocked"
                task.error = "A dependency failed"
                pending.discard(task.id)
                self._queued = max(0, self._queued - 1)

            for task in ready:
                pending.discard(task.id)
                running[task.id] = asyncio.create_task(self._run_one(task, runner))

            if fail_fast and any(t.status == "failed" for t in tasks):
                for task_id in pending:
                    by_id[task_id].status = "cancelled"
                pending.clear()

            if running:
                done, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
                finished_ids = [task_id for task_id, future in running.items() if future in done]
                for task_id in finished_ids:
                    await running.pop(task_id)
            elif pending:
                # No task can become ready: this is a dependency cycle.
                cycle = sorted(pending)
                raise ValueError(f"Task dependency cycle detected: {cycle}")

        return {
            "tasks": [task_to_dict(task) for task in tasks],
            "summary": {
                "total": len(tasks),
                "done": sum(t.status == "done" for t in tasks),
                "failed": sum(t.status == "failed" for t in tasks),
                "blocked": sum(t.status == "blocked" for t in tasks),
                "workers": self.workers,
                "max_parallelism": self.workers,
            },
        }

    def status(self) -> dict[str, int]:
        return {
            "workers": self.workers,
            "active": self._active,
            "idle": max(0, self.workers - self._active),
            "queued": self._queued,
            "completed": self._completed,
            "failed": self._failed,
        }


def task_to_dict(task: RuntimeTask) -> dict[str, Any]:
    duration_ms = None
    if task.started_at is not None and task.finished_at is not None:
        duration_ms = round((task.finished_at - task.started_at) * 1000, 2)
    return {
        "id": task.id,
        "name": task.name,
        "status": task.status,
        "depends_on": task.depends_on,
        "payload": task.payload,
        "result": task.result,
        "error": task.error,
        "duration_ms": duration_ms,
    }


def parse_plan(plan: dict[str, Any]) -> list[RuntimeTask]:
    raw_tasks = plan.get("tasks") or plan.get("steps")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Plan must contain a non-empty 'tasks' or 'steps' list")
    tasks: list[RuntimeTask] = []
    for index, raw in enumerate(raw_tasks, 1):
        if isinstance(raw, str):
            raw = {"name": raw}
        if not isinstance(raw, dict):
            raise ValueError(f"Task {index} must be an object or string")
        task_id = str(raw.get("id") or f"task-{index}")
        deps = raw.get("depends_on", raw.get("dependencies", []))
        if isinstance(deps, str):
            deps = [deps]
        if not isinstance(deps, list):
            raise ValueError(f"Task '{task_id}' dependencies must be a list")
        tasks.append(
            RuntimeTask(
                id=task_id,
                name=str(raw.get("name") or raw.get("description") or task_id),
                depends_on=[str(x) for x in deps],
                payload=dict(raw.get("payload") or {}),
            )
        )
    return tasks


def new_task_id(prefix: str = "task") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def workspace_context(path: str) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    files = []
    for item in root.rglob("*"):
        if not item.is_file() or any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in item.parts):
            continue
        files.append(str(item.relative_to(root)))
        if len(files) >= 500:
            break
    manifests = [name for name in files if Path(name).name in {"pyproject.toml", "requirements.txt", "package.json", "composer.json", "Dockerfile", "docker-compose.yml", "Cargo.toml", "go.mod"}]
    return {"path": str(root), "files": files, "file_count_sampled": len(files), "manifests": manifests}


def compact_error(exc: Exception) -> dict[str, str]:
    text = str(exc)
    return {"type": type(exc).__name__, "message": text[:2000], "retryable": str(type(exc).__name__) in {"TimeoutError", "ConnectionError"}}
