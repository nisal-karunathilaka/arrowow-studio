"""
Arrowow Studio — Background Job Runner
======================================

Streamlit reruns its script top-to-bottom on every interaction and blocks during a
synchronous call. A full live render is 5 × (1–3 min) Veo calls, so running it inline
would freeze the UI for ~10 minutes with no progress.

This module runs a segment in a daemon thread and exposes its live log + status through
a process-global registry. The Streamlit page polls `get(job_id)` on each rerun and
short-sleeps + reruns while status == "running", giving a live progress feed without any
extra dependency.

Thread-safety: the worker only appends to `job.logs` (list append is atomic under the
GIL) and assigns `job.result`/`job.status` once at the end; the UI thread only reads.
The ADK session object is owned by the worker for the job's duration and read by the UI
only after status flips to "done".
"""
from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Awaitable, Callable, Optional

# job_id -> Job
_JOBS: dict[str, "Job"] = {}


class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.status = "running"          # running | done | error
        self.logs: list[str] = []
        self.result = None
        self.error: Optional[str] = None
        self.started_at = time.time()
        self.ended_at: Optional[float] = None

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    @property
    def elapsed(self) -> float:
        return (self.ended_at or time.time()) - self.started_at


def start(job_id: str, coro_factory: Callable[[Callable[[str], None]], Awaitable]) -> "Job":
    """Start `coro_factory(log)` in a background thread. `coro_factory` receives a thread-safe
    `log(str)` callback and returns an awaitable that does the work."""
    job = Job(job_id)
    _JOBS[job_id] = job

    def _worker():
        try:
            asyncio.run(coro_factory(job.log))
            job.status = "done"
        except Exception as e:  # surface the failure to the UI instead of dying silently
            job.error = f"{e}\n{traceback.format_exc()}"
            job.status = "error"
            job.log(f"[error] {e}")
        finally:
            job.ended_at = time.time()

    threading.Thread(target=_worker, daemon=True, name=f"job:{job_id}").start()
    return job


def get(job_id: Optional[str]) -> Optional["Job"]:
    return _JOBS.get(job_id) if job_id else None


def clear(job_id: str) -> None:
    _JOBS.pop(job_id, None)
