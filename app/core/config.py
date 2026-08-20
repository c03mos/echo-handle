from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


def detect_public_base_url(default_port: int = 8000) -> str:
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return f"http://{ip}:{default_port}"
    except OSError:
        pass
    return f"http://127.0.0.1:{default_port}"


class Settings(BaseSettings):
    app_name: str = "echo-handle"
    app_env: str = "dev"
    data_dir: str = "../Data"
    processed_data_dir: str = "../Data"
    echo_data_dir: str = "../echo_data"
    handle_db_path: str = "../echo_data/handle.db"
    model_zoo_dir: str = "../modelZoo"
    kim_model_path: str = "../modelZoo/Kim_Vocal_2/Kim_Vocal_2.onnx"
    public_base_url: str = detect_public_base_url()
    static_mount_path: str = "/static"
    arrangement_base_url: str = "http://localhost:8081"
    arrangement_callback_timeout_seconds: int = 10
    instrumental_max_concurrency: int = 1
    ffmpeg_bin: str = "../_internal/ffmpeg/bin/ffmpeg.exe"
    ffprobe_bin: str = "../_internal/ffmpeg/bin/ffprobe.exe"
    onnx_model_path: str = "models/model.onnx"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (BASE_DIR / path).resolve()


settings = Settings()
