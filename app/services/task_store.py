import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


class TaskStore:
    def __init__(self) -> None:
        self.db_path = Path(settings.handle_db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_file TEXT NOT NULL,
                    output_files TEXT,
                    request_json TEXT NOT NULL,
                    response_json TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def record_start(self, task_id: str, task_type: str, input_file: str, request_payload: dict[str, Any]) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO task_runs (
                    task_id, task_type, status, input_file, request_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, task_type, "processing", input_file, json.dumps(request_payload, ensure_ascii=False), now, now),
            )

    def update_status(self, task_id: str, status: str, response_payload: dict[str, Any] | None = None, output_files: list[str] | None = None, error_message: str | None = None) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE task_runs
                SET status = ?, output_files = COALESCE(?, output_files), response_json = COALESCE(?, response_json), error_message = ?, updated_at = ?
                WHERE id = (
                    SELECT id FROM task_runs WHERE task_id = ? ORDER BY id DESC LIMIT 1
                )
                """,
                (
                    status,
                    json.dumps(output_files, ensure_ascii=False) if output_files is not None else None,
                    json.dumps(response_payload, ensure_ascii=False) if response_payload is not None else None,
                    error_message,
                    now,
                    task_id,
                ),
            )

    def record_finish(self, task_id: str, status: str, response_payload: dict[str, Any] | None, output_files: list[str] | None = None, error_message: str | None = None) -> None:
        self.update_status(task_id, status, response_payload=response_payload, output_files=output_files, error_message=error_message)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM task_runs WHERE task_id = ? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM task_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        response_json = json.loads(row["response_json"]) if row["response_json"] else None
        outputs = json.loads(row["output_files"] or "[]")
        entrypoints = TaskStore._extract_entrypoints(response_json)
        public_urls = TaskStore._build_public_urls(entrypoints)
        return {
            "id": row["id"],
            "taskId": row["task_id"],
            "taskType": row["task_type"],
            "status": row["status"],
            "inputFile": row["input_file"],
            "outputFiles": outputs,
            "entrypoints": entrypoints,
            "publicUrls": public_urls,
            "requestJson": json.loads(row["request_json"]) if row["request_json"] else None,
            "responseJson": response_json,
            "errorMessage": row["error_message"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _extract_entrypoints(response_json: dict[str, Any] | None) -> dict[str, str]:
        if not response_json:
            return {}
        outputs = response_json.get("outputs")
        if outputs is None and isinstance(response_json.get("data"), dict):
            outputs = response_json["data"].get("outputs")
        if not isinstance(outputs, dict):
            return {}
        keys = ["masterPlaylist", "videoPlaylist", "originalAudioPlaylist", "instrumentalAudioPlaylist", "downloadedVideo", "originalAudio", "instrumentalAudio", "vocalAudio"]
        return {key: value for key, value in outputs.items() if key in keys and isinstance(value, str)}

    @staticmethod
    def _build_public_urls(entrypoints: dict[str, str]) -> dict[str, str]:
        data_root = Path(settings.data_dir).resolve()
        base = settings.public_base_url.rstrip('/') + settings.static_mount_path
        public: dict[str, str] = {}
        for key, value in entrypoints.items():
            try:
                relative = Path(value).resolve().relative_to(data_root).as_posix()
            except ValueError:
                continue
            public[key] = f"{base}/{relative}"
        return public

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


task_store = TaskStore()
