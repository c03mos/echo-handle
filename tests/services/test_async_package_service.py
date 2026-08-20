from pathlib import Path

from app.services.async_package_service import async_package_service
from app.services.ffmpeg_service import ffmpeg_service


def test_build_skip_instrumental_hls_uses_muxed_hls_for_m4a(monkeypatch) -> None:
    expected = {"master_playlist": "master.m3u8", "video_playlist": "stream.m3u8"}

    def fake_build_muxed_hls(video_file: str, audio_file: str, output_dir: str) -> dict[str, str]:
        assert video_file == "video.mp4"
        assert audio_file == str(Path("work") / "media.m4a")
        assert output_dir == str(Path("work") / "hls")
        return expected

    monkeypatch.setattr(ffmpeg_service, "build_muxed_hls", fake_build_muxed_hls)

    result = async_package_service._build_skip_instrumental_hls(
        video_file="video.mp4",
        source_audio_file="audio.m4a",
        original_audio=Path("work") / "media.m4a",
        output_root=Path("work"),
    )

    assert result == expected


def test_build_skip_instrumental_hls_uses_single_mp4_hls_without_m4a(monkeypatch) -> None:
    expected = {"master_playlist": "master.m3u8", "video_playlist": "stream.m3u8"}

    def fake_build_single_mp4_hls(input_file: str, output_dir: str) -> dict[str, str]:
        assert input_file == "video.mp4"
        assert output_dir == str(Path("work") / "hls")
        return expected

    monkeypatch.setattr(ffmpeg_service, "build_single_mp4_hls", fake_build_single_mp4_hls)

    result = async_package_service._build_skip_instrumental_hls(
        video_file="video.mp4",
        source_audio_file=None,
        original_audio=Path("work") / "media.m4a",
        output_root=Path("work"),
    )

    assert result == expected
