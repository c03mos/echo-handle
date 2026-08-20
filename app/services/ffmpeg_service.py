import subprocess
from pathlib import Path

from app.core.config import settings
from app.utils.paths import ensure_output_dir


class FfmpegService:
    def probe(self, media_path: str) -> dict[str, str]:
        target = Path(media_path)
        if not target.exists():
            return {"error": f"media not found: {media_path}"}
        command = [settings.ffprobe_bin, "-v", "error", "-show_format", "-show_streams", str(target)]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            return {"error": str(exc)}
        return {"raw": completed.stdout}

    def extract_audio(self, input_file: str, output_file: str, audio_codec: str | None = None, sample_rate: int | None = None, bitrate: str | None = None) -> dict[str, str]:
        output_path = Path(output_file)
        ensure_output_dir(output_path.parent)
        command = [settings.ffmpeg_bin, "-y", "-i", input_file, "-vn"]
        if audio_codec:
            command.extend(["-acodec", audio_codec])
        if sample_rate:
            command.extend(["-ar", str(sample_rate)])
        if bitrate:
            command.extend(["-b:a", bitrate])
        command.append(str(output_path))
        return self._run(command, str(output_path))

    def transcode(self, input_file: str, output_file: str, video_codec: str | None = None, audio_codec: str | None = None, resolution: str | None = None, bitrate: str | None = None) -> dict[str, str]:
        output_path = Path(output_file)
        ensure_output_dir(output_path.parent)
        command = [settings.ffmpeg_bin, "-y", "-i", input_file]
        if video_codec:
            command.extend(["-vcodec", video_codec])
        if audio_codec:
            command.extend(["-acodec", audio_codec])
        if resolution:
            command.extend(["-s", resolution])
        if bitrate:
            command.extend(["-b:v", bitrate])
        command.append(str(output_path))
        return self._run(command, str(output_path))

    def pcm_44k_stereo(self, input_file: str, output_file: str) -> dict[str, str]:
        output_path = Path(output_file)
        ensure_output_dir(output_path.parent)
        command = [settings.ffmpeg_bin, "-y", "-i", input_file, "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(output_path)]
        return self._run(command, str(output_path))

    def build_multi_audio_hls(self, video_file: str, original_audio_file: str, instrumental_audio_file: str, output_dir: str, master_name: str = "master.m3u8") -> dict[str, str]:
        output_root = ensure_output_dir(output_dir)
        video_playlist = output_root / "video.m3u8"
        original_playlist = output_root / "audio_original.m3u8"
        instrumental_playlist = output_root / "audio_instrumental.m3u8"
        master_playlist = output_root / master_name

        video_segment = output_root / "video_%03d.ts"
        original_segment = output_root / "audio_original_%03d.ts"
        instrumental_segment = output_root / "audio_instrumental_%03d.ts"

        video_cmd = [
            settings.ffmpeg_bin, "-y", "-i", video_file,
            "-map", "0:v:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-level", "4.1",
            "-g", "48",
            "-keyint_min", "48",
            "-sc_threshold", "0",
            "-force_key_frames", "expr:gte(t,n_forced*6)",
            "-an",
            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(video_segment),
            str(video_playlist),
        ]
        original_cmd = [
            settings.ffmpeg_bin, "-y", "-i", original_audio_file,
            "-map", "0:a:0",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-b:a", "192k",
            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(original_segment),
            str(original_playlist),
        ]
        instrumental_cmd = [
            settings.ffmpeg_bin, "-y", "-i", instrumental_audio_file,
            "-map", "0:a:0",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-b:a", "192k",
            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(instrumental_segment),
            str(instrumental_playlist),
        ]

        for command, target in ((video_cmd, video_playlist), (original_cmd, original_playlist), (instrumental_cmd, instrumental_playlist)):
            result = self._run(command, str(target))
            if "error" in result:
                return result

        master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"audio\",NAME=\"original\",LANGUAGE=\"zh\",DEFAULT=YES,AUTOSELECT=YES,URI=\"audio_original.m3u8\"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID=\"audio\",NAME=\"instrumental\",LANGUAGE=\"zxx\",DEFAULT=NO,AUTOSELECT=YES,URI=\"audio_instrumental.m3u8\"
#EXT-X-STREAM-INF:BANDWIDTH=2800000,AVERAGE-BANDWIDTH=2200000,CODECS=\"avc1.640029,mp4a.40.2\",RESOLUTION=1920x1080,AUDIO=\"audio\"
video.m3u8
"""
        master_playlist.write_text(master_content, encoding="utf-8")
        return {
            "master_playlist": str(master_playlist),
            "video_playlist": str(video_playlist),
            "original_audio_playlist": str(original_playlist),
            "instrumental_audio_playlist": str(instrumental_playlist),
        }

    def build_muxed_hls(self, video_file: str, audio_file: str, output_dir: str, master_name: str = "master.m3u8") -> dict[str, str]:
        output_root = ensure_output_dir(output_dir)
        stream_playlist = output_root / "stream.m3u8"
        master_playlist = output_root / master_name
        segment_pattern = output_root / "stream_%03d.ts"

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            video_file,
            "-i",
            audio_file,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-g",
            "48",
            "-keyint_min",
            "48",
            "-sc_threshold",
            "0",
            "-force_key_frames",
            "expr:gte(t,n_forced*6)",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-f",
            "hls",
            "-hls_time",
            "6",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(segment_pattern),
            str(stream_playlist),
        ]
        result = self._run(command, str(stream_playlist))
        if "error" in result:
            return result

        master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-STREAM-INF:BANDWIDTH=2800000,AVERAGE-BANDWIDTH=2200000,CODECS=\"avc1.640029,mp4a.40.2\",RESOLUTION=1920x1080
stream.m3u8
"""
        master_playlist.write_text(master_content, encoding="utf-8")
        return {
            "master_playlist": str(master_playlist),
            "video_playlist": str(stream_playlist),
        }

    def build_single_mp4_hls(self, input_file: str, output_dir: str, master_name: str = "master.m3u8") -> dict[str, str]:
        output_root = ensure_output_dir(output_dir)
        stream_playlist = output_root / "stream.m3u8"
        master_playlist = output_root / master_name
        segment_pattern = output_root / "stream_%03d.ts"

        command = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            input_file,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "-level",
            "4.1",
            "-g",
            "48",
            "-keyint_min",
            "48",
            "-sc_threshold",
            "0",
            "-force_key_frames",
            "expr:gte(t,n_forced*6)",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-f",
            "hls",
            "-hls_time",
            "6",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(segment_pattern),
            str(stream_playlist),
        ]
        result = self._run(command, str(stream_playlist))
        if "error" in result:
            return result

        master_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-STREAM-INF:BANDWIDTH=2800000,AVERAGE-BANDWIDTH=2200000,CODECS=\"avc1.640029,mp4a.40.2\",RESOLUTION=1920x1080
stream.m3u8
"""
        master_playlist.write_text(master_content, encoding="utf-8")
        return {
            "master_playlist": str(master_playlist),
            "video_playlist": str(stream_playlist),
        }

    @staticmethod
    def _run(command: list[str], output_file: str) -> dict[str, str]:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, cwd=Path.cwd())
        except (OSError, subprocess.CalledProcessError) as exc:
            stderr = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            return {"error": stderr or str(exc)}
        return {"output_file": output_file, "stderr": completed.stderr}


ffmpeg_service = FfmpegService()
