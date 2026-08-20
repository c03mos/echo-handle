from typing import Any

import httpx

from app.core.config import settings


class ArrangementClient:
    def register_task_resources(self, task_id: str, media_key: str, resources: list[dict[str, str]]) -> dict[str, Any]:
        url = f"{settings.arrangement_base_url.rstrip('/')}/api/tasks/{task_id}/resources"
        payload = {
            "mediaKey": media_key,
            "resources": resources,
        }
        try:
            response = httpx.post(url, json=payload, timeout=settings.arrangement_callback_timeout_seconds)
            return {
                "status_code": response.status_code,
                "url": url,
                "payload": payload,
                "response_text": response.text,
            }
        except httpx.HTTPError as exc:
            return {"error": str(exc), "url": url, "payload": payload}

    def callback_task_result(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{settings.arrangement_base_url.rstrip('/')}/api/tasks/{task_id}/callback"
        try:
            response = httpx.post(url, json=payload, timeout=settings.arrangement_callback_timeout_seconds)
            return {"status_code": response.status_code, "url": url, "response_text": response.text}
        except httpx.HTTPError as exc:
            return {"error": str(exc), "url": url}


arrangement_client = ArrangementClient()
