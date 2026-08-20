import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.models.task import (
    ApiResponse,
    AsyncAcceptedResult,
    AsyncPackageRequest,
    DownloadVideoRequest,
    ExtractAudioRequest,
    ExtractInstrumentalRequest,
    TranscodeRequest,
)
from app.services.async_package_service import async_package_service
from app.services.pipeline import pipeline_service
from app.services.task_progress_store import task_progress_store
from app.services.task_store import task_store

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("/tasks", response_model=ApiResponse)
def list_tasks(limit: int = Query(default=20, ge=1, le=200)) -> ApiResponse:
    return ApiResponse(data=task_store.list_tasks(limit=limit))


@router.get("/tasks/{task_id}", response_model=ApiResponse)
def get_task(task_id: str) -> ApiResponse:
    task = task_store.get_task(task_id)
    if task is None:
        return ApiResponse(code=4040, message="task not found", data=None)
    return ApiResponse(data=task)


@router.get("/tasks/{task_id}/playback", response_model=ApiResponse)
def get_task_playback(task_id: str) -> ApiResponse:
    task = task_store.get_task(task_id)
    if task is None:
        return ApiResponse(code=4040, message="task not found", data=None)
    return ApiResponse(data={
        'taskId': task['taskId'],
        'status': task['status'],
        'masterPlaylist': task.get('publicUrls', {}).get('masterPlaylist'),
        'videoPlaylist': task.get('publicUrls', {}).get('videoPlaylist'),
        'originalAudioPlaylist': task.get('publicUrls', {}).get('originalAudioPlaylist'),
        'instrumentalAudioPlaylist': task.get('publicUrls', {}).get('instrumentalAudioPlaylist'),
    })


@router.post("/async/video-package", response_model=ApiResponse)
def submit_async_video_package(payload: AsyncPackageRequest) -> ApiResponse:
    async_package_service.submit(payload)
    data = AsyncAcceptedResult(taskId=payload.task_id, mediaId=payload.media_id, status="accepted", wsPath=f"/ws/tasks/{payload.task_id}")
    return ApiResponse(data=data.model_dump(by_alias=True))


@router.websocket("/ws/tasks/{task_id}")
async def task_status_ws(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    last_version = -1
    try:
        while True:
            event = task_progress_store.get_event(task_id)
            if event and event.get("version", -1) != last_version:
                await websocket.send_json(event)
                last_version = int(event["version"])
                if event.get("status") in {"completed", "failed"}:
                    break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@router.post("/download-video", response_model=ApiResponse)
def download_video(payload: DownloadVideoRequest) -> ApiResponse:
    return pipeline_service.download_video(payload)


@router.post("/extract-audio", response_model=ApiResponse)
def extract_audio(payload: ExtractAudioRequest) -> ApiResponse:
    return pipeline_service.extract_audio(payload)


@router.post("/transcode", response_model=ApiResponse)
def transcode(payload: TranscodeRequest) -> ApiResponse:
    return pipeline_service.transcode(payload)


@router.post("/extract-instrumental", response_model=ApiResponse)
def extract_instrumental(payload: ExtractInstrumentalRequest) -> ApiResponse:
    return pipeline_service.extract_instrumental(payload)
