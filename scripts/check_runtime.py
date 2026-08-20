from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings


def check_path(label: str, path_str: str) -> None:
    path = settings.resolve_path(path_str)
    status = "OK" if path.exists() else "MISSING"
    print(f"[{status}] {label}: {path}")


def check_yt_dlp() -> None:
    try:
        completed = subprocess.run(['python', '-m', 'yt_dlp', '--version'], capture_output=True, text=True, check=True)
        print(f"[OK] yt_dlp: {completed.stdout.strip()}")
    except (OSError, subprocess.CalledProcessError):
        print('[MISSING] yt_dlp: python -m yt_dlp --version failed')


def main() -> None:
    check_path("ffmpeg", settings.ffmpeg_bin)
    check_path("ffprobe", settings.ffprobe_bin)
    check_path("data_dir", settings.data_dir)
    check_path("echo_data_dir", settings.echo_data_dir)
    check_path("kim_model", settings.kim_model_path)
    check_yt_dlp()


if __name__ == "__main__":
    main()
