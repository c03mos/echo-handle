from threading import Lock
from typing import Any


class TaskProgressStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, dict[str, Any]] = {}

    def set_event(self, task_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            current = self._events.get(task_id, {})
            version = int(current.get("version", 0)) + 1
            self._events[task_id] = {**payload, "version": version}

    def get_event(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            event = self._events.get(task_id)
            return dict(event) if event else None


task_progress_store = TaskProgressStore()
