import json
import subprocess
from pathlib import Path

from app.utils.paths import ensure_output_dir


class YtDlpService:
    PLATFORM_ARGS = {
        'youtube': [],
        'bilibili': [],
        'tiktok': [],
        'douyin': [],
        'twitter': [],
        'x': [],
        'instagram': [],
        'generic': [],
    }

    def is_available(self) -> bool:
        try:
            completed = subprocess.run(['python', '-m', 'yt_dlp', '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
            return bool(completed.stdout.strip())
        except (OSError, subprocess.CalledProcessError):
            return False

    def download(
        self,
        platform: str,
        url: str,
        output_dir: str,
        media_id: str | None = None,
        format_selector: str | None = None,
        extract_audio: bool = False,
        audio_format: str | None = None,
        cookies_file: str | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        headers: dict[str, str] | None = None,
        subtitles: bool = False,
        subtitle_languages: list[str] | None = None,
        playlist_items: str | None = None,
        extra_args: list[str] | None = None,
    ) -> dict[str, object]:
        if not self.is_available():
            return {'error': 'yt-dlp is not installed; run `python -m pip install yt-dlp`'}

        output_root = ensure_output_dir(output_dir)
        before = {p.resolve() for p in output_root.glob('*')}
        if media_id:
            output_template = str((output_root / f'{media_id}.%(ext)s').resolve())
        else:
            output_template = str((output_root / '%(title).180B [%(id)s].%(format_id)s.%(ext)s').resolve())
        command = ['python', '-m', 'yt_dlp', '--no-warnings', '--newline', '-o', output_template]
        command.extend(self.PLATFORM_ARGS.get(platform.lower(), []))

        if format_selector:
            command.extend(['-f', format_selector])
        if extract_audio:
            command.append('-x')
        if audio_format:
            command.extend(['--audio-format', audio_format])
        if cookies_file:
            command.extend(['--cookies', cookies_file])
        if user_agent:
            command.extend(['--user-agent', user_agent])
        if referer:
            command.extend(['--referer', referer])
        for key, value in (headers or {}).items():
            command.extend(['--add-header', f'{key}:{value}'])
        if subtitles:
            command.append('--write-subs')
            if subtitle_languages:
                command.extend(['--sub-langs', ','.join(subtitle_languages)])
        if playlist_items:
            command.extend(['--playlist-items', playlist_items])
        if extra_args:
            command.extend(extra_args)
        command.append(url)

        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            stderr = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            stdout = exc.stdout if isinstance(exc, subprocess.CalledProcessError) else ''
            return {'error': stderr or str(exc), 'stdout': stdout}

        after = {p.resolve() for p in output_root.glob('*')}
        downloaded_paths = sorted(after - before)
        if media_id:
            downloaded_paths = self._normalize_media_id_outputs(output_root, downloaded_paths, media_id)
        downloaded = [str(path) for path in downloaded_paths]
        return {
            'platform': platform,
            'source_url': url,
            'output_dir': str(output_root.resolve()),
            'downloaded_files': downloaded,
            'video_file': self._pick_video_file(downloaded_paths),
            'audio_file': self._pick_audio_file(downloaded_paths),
            'stdout': completed.stdout,
            'command': json.dumps(command, ensure_ascii=False),
        }

    @staticmethod
    def _pick_video_file(files: list[Path]) -> str | None:
        candidates = [path for path in files if path.suffix.lower() in {'.mp4', '.mkv', '.mov', '.webm', '.m4v'} and '.f' in path.name]
        if not candidates:
            candidates = [path for path in files if path.suffix.lower() in {'.mp4', '.mkv', '.mov', '.webm', '.m4v'}]
        if candidates:
            return str(sorted(candidates, key=lambda item: item.stat().st_size, reverse=True)[0])
        return None

    @staticmethod
    def _pick_audio_file(files: list[Path]) -> str | None:
        candidates = [path for path in files if path.suffix.lower() in {'.m4a', '.aac', '.mp3', '.wav', '.flac', '.opus'}]
        if candidates:
            return str(sorted(candidates, key=lambda item: item.stat().st_size, reverse=True)[0])
        return None

    def _normalize_media_id_outputs(self, output_root: Path, files: list[Path], media_id: str) -> list[Path]:
        normalized: list[Path] = []
        used_targets: set[Path] = set()
        video_file = self._pick_video_path(files)
        audio_file = self._pick_audio_path(files)

        for index, source in enumerate(sorted(files)):
            target = self._build_target_path(output_root, source, media_id, index, video_file, audio_file)
            if source == target:
                normalized.append(source)
                used_targets.add(target)
                continue
            while target in used_targets or target.exists():
                target = target.with_name(f'{target.stem}_{index}{target.suffix}')
            source.replace(target)
            normalized.append(target)
            used_targets.add(target)

        return sorted(normalized)

    def _build_target_path(
        self,
        output_root: Path,
        source: Path,
        media_id: str,
        index: int,
        video_file: Path | None,
        audio_file: Path | None,
    ) -> Path:
        suffix = source.suffix.lower()
        if video_file and source == video_file:
            return output_root / f'{media_id}{suffix}'
        if audio_file and source == audio_file:
            return output_root / f'{media_id}.source{suffix}'
        if source.name.startswith(f'{media_id}.'):
            return source
        return output_root / f'{media_id}.asset{index}{suffix}'

    @staticmethod
    def _pick_video_path(files: list[Path]) -> Path | None:
        candidates = [path for path in files if path.suffix.lower() in {'.mp4', '.mkv', '.mov', '.webm', '.m4v'} and '.f' in path.name]
        if not candidates:
            candidates = [path for path in files if path.suffix.lower() in {'.mp4', '.mkv', '.mov', '.webm', '.m4v'}]
        if candidates:
            return sorted(candidates, key=lambda item: item.stat().st_size, reverse=True)[0]
        return None

    @staticmethod
    def _pick_audio_path(files: list[Path]) -> Path | None:
        candidates = [path for path in files if path.suffix.lower() in {'.m4a', '.aac', '.mp3', '.wav', '.flac', '.opus'}]
        if candidates:
            return sorted(candidates, key=lambda item: item.stat().st_size, reverse=True)[0]
        return None


yt_dlp_service = YtDlpService()
