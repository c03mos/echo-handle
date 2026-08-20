from pathlib import Path
import subprocess

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/runtime")
def runtime_health() -> dict[str, object]:
    ffmpeg = Path(settings.ffmpeg_bin).resolve()
    ffprobe = Path(settings.ffprobe_bin).resolve()
    kim_model = Path(settings.kim_model_path).resolve()
    db_path = Path(settings.handle_db_path).resolve()
    try:
        yt_dlp_version = subprocess.run(['python', '-m', 'yt_dlp', '--version'], capture_output=True, text=True, check=True).stdout.strip()
        yt_dlp_available = True
    except (OSError, subprocess.CalledProcessError):
        yt_dlp_version = None
        yt_dlp_available = False
    return {
        "status": "ok",
        "paths": {
            "ffmpeg": {"path": str(ffmpeg), "exists": ffmpeg.exists()},
            "ffprobe": {"path": str(ffprobe), "exists": ffprobe.exists()},
            "kimModel": {"path": str(kim_model), "exists": kim_model.exists()},
            "handleDb": {"path": str(db_path), "exists": db_path.exists()},
        },
        "tools": {
            "ytDlp": {"available": yt_dlp_available, "version": yt_dlp_version},
            "websocket": {"available": True},
        },
    }
