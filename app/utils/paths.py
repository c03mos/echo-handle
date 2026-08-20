from pathlib import Path

from app.core.config import settings


def resolve_media_path(media_path: str) -> Path:
    path = Path(media_path)
    if path.is_absolute():
        return path
    return Path(settings.data_dir).joinpath(path).resolve()


def ensure_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
