from pathlib import Path

from app.models.task import (
    ApiResponse,
    DownloadVideoRequest,
    DownloadVideoResult,
    ExtractAudioRequest,
    ExtractAudioResult,
    ExtractInstrumentalRequest,
    ExtractInstrumentalResult,
    TranscodeRequest,
    TranscodeResult,
)
from app.services.async_package_service import async_package_service
from app.services.ffmpeg_service import ffmpeg_service
from app.services.onnx_service import onnx_service
from app.services.task_store import task_store
from app.services.yt_dlp_service import yt_dlp_service
from app.utils.paths import ensure_output_dir, resolve_media_path


class PipelineService:
    def extract_audio(self, payload: ExtractAudioRequest) -> ApiResponse:
        input_path = resolve_media_path(payload.input_file)
        if not input_path.exists():
            return ApiResponse(code=4004, message=f"input file not found: {input_path}", data=None)
        output_dir = ensure_output_dir(payload.output_dir)
        output_file = output_dir / f"{input_path.stem}.{payload.output_audio_format}"
        task_store.record_start(payload.task_id, "extract-audio", str(input_path), payload.model_dump(by_alias=True))
        execute_result = ffmpeg_service.extract_audio(str(input_path), str(output_file), audio_codec=payload.audio_codec, sample_rate=payload.sample_rate, bitrate=payload.bitrate)
        if "error" in execute_result:
            response = ApiResponse(code=5001, message=execute_result["error"], data=None)
            task_store.record_finish(payload.task_id, "failed", response.model_dump(), error_message=execute_result["error"])
            return response
        probe = ffmpeg_service.probe(str(input_path))
        duration = self._parse_duration(probe)
        data = ExtractAudioResult(taskId=payload.task_id, outputFile=str(output_file), duration=duration)
        response = ApiResponse(data=data.model_dump(by_alias=True))
        task_store.record_finish(payload.task_id, "completed", response.model_dump(), output_files=[str(output_file)])
        return response

    def transcode(self, payload: TranscodeRequest) -> ApiResponse:
        input_path = resolve_media_path(payload.input_file)
        if not input_path.exists():
            return ApiResponse(code=4004, message=f"input file not found: {input_path}", data=None)
        output_dir = ensure_output_dir(payload.output_dir)
        output_file = output_dir / f"{input_path.stem}.{payload.output_format}"
        task_store.record_start(payload.task_id, "transcode", str(input_path), payload.model_dump(by_alias=True))
        execute_result = ffmpeg_service.transcode(str(input_path), str(output_file), video_codec=payload.video_codec, audio_codec=payload.audio_codec, resolution=payload.resolution, bitrate=payload.bitrate)
        if "error" in execute_result:
            response = ApiResponse(code=5002, message=execute_result["error"], data=None)
            task_store.record_finish(payload.task_id, "failed", response.model_dump(), error_message=execute_result["error"])
            return response
        data = TranscodeResult(taskId=payload.task_id, outputFile=str(output_file))
        response = ApiResponse(data=data.model_dump(by_alias=True))
        task_store.record_finish(payload.task_id, "completed", response.model_dump(), output_files=[str(output_file)])
        return response

    def extract_instrumental(self, payload: ExtractInstrumentalRequest) -> ApiResponse:
        input_path = resolve_media_path(payload.input_file)
        if not input_path.exists():
            return ApiResponse(code=4004, message=f"input file not found: {input_path}", data=None)
        task_store.record_start(payload.task_id, "extract-instrumental", str(input_path), payload.model_dump(by_alias=True))
        infer_result = onnx_service.infer(str(input_path), task_type="extract_instrumental", stem_mode=payload.stem_mode, output_format=payload.output_format, output_dir=str(payload.output_dir))
        if "error" in infer_result:
            response = ApiResponse(code=5004, message=infer_result["error"], data=None)
            task_store.record_finish(payload.task_id, "failed", response.model_dump(), error_message=infer_result["error"])
            return response
        instrumental_file = infer_result["instrumental_file"]
        vocal_file = infer_result.get("vocal_file")
        data = ExtractInstrumentalResult(taskId=payload.task_id, instrumentalFile=str(instrumental_file), vocalFile=vocal_file)
        response = ApiResponse(data=data.model_dump(by_alias=True))
        output_files = [str(instrumental_file)]
        if vocal_file:
            output_files.append(vocal_file)
        task_store.record_finish(payload.task_id, "completed", response.model_dump(), output_files=output_files)
        return response

    def download_video(self, payload: DownloadVideoRequest) -> ApiResponse:
        output_dir = ensure_output_dir(payload.output_dir)
        task_store.record_start(payload.task_id, "download-video", payload.url, payload.model_dump(by_alias=True))
        result = yt_dlp_service.download(platform=payload.platform, url=payload.url, output_dir=str(output_dir), media_id=payload.media_id, format_selector=payload.format_selector, extract_audio=payload.extract_audio, audio_format=payload.audio_format, cookies_file=payload.cookies_file, user_agent=payload.user_agent, referer=payload.referer, headers=payload.headers, subtitles=payload.subtitles, subtitle_languages=payload.subtitle_languages, playlist_items=payload.playlist_items, extra_args=payload.extra_args)
        if "error" in result:
            response = ApiResponse(code=5005, message=str(result["error"]), data=None)
            task_store.record_finish(payload.task_id, "failed", response.model_dump(), error_message=str(result["error"]))
            return response
        data = DownloadVideoResult(taskId=payload.task_id, mediaId=payload.media_id, platform=payload.platform, sourceUrl=payload.url, outputDir=str(output_dir), downloadedFiles=result.get('downloaded_files', []), stdout=str(result.get('stdout', '')))
        response = ApiResponse(data=data.model_dump(by_alias=True))
        task_store.record_finish(payload.task_id, "completed", response.model_dump(), output_files=result.get('downloaded_files', []))
        return response

    @staticmethod
    def _parse_duration(probe_result: dict[str, str]) -> float | None:
        raw = probe_result.get("raw")
        if not raw:
            return None
        for line in raw.splitlines():
            if line.startswith("duration="):
                try:
                    return float(line.split("=", maxsplit=1)[1])
                except ValueError:
                    return None
        return None


pipeline_service = PipelineService()
