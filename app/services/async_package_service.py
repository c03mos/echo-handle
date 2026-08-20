from __future__ import annotations

import threading
from pathlib import Path

from app.models.task import AsyncPackageRequest
from app.services.arrangement_client import arrangement_client
from app.services.ffmpeg_service import ffmpeg_service
from app.services.onnx_service import onnx_service
from app.services.task_progress_store import task_progress_store
from app.services.task_store import task_store
from app.services.yt_dlp_service import yt_dlp_service
from app.utils.paths import ensure_output_dir
from app.core.config import settings


_instrumental_limit = max(1, int(settings.instrumental_max_concurrency))
_instrumental_semaphore = threading.Semaphore(_instrumental_limit)


class AsyncPackageService:
    def submit(self, payload: AsyncPackageRequest) -> None:
        request_data = payload.model_dump(by_alias=True)
        resolved_url = self._resolve_url(payload)
        request_data["resolvedUrl"] = resolved_url
        task_store.record_start(payload.task_id, "async-video-package", resolved_url, request_data)
        self._emit(payload.task_id, payload.media_id, "queued", "accepted", 0, detail="task accepted")
        worker = threading.Thread(target=self._run_task, args=(payload, resolved_url), daemon=True)
        worker.start()

    def _run_task(self, payload: AsyncPackageRequest, resolved_url: str) -> None:
        outputs: dict[str, str] = {}
        callback_result: dict[str, object] | None = None
        output_root = ensure_output_dir(Path(payload.output_dir) / payload.media_id)
        try:
            self._emit(payload.task_id, payload.media_id, "running", "download", 10, detail="starting download")
            task_store.update_status(payload.task_id, "downloading")
            download_result = yt_dlp_service.download(
                platform=payload.platform,
                url=resolved_url,
                output_dir=str(output_root),
                media_id=payload.media_id,
                format_selector=payload.format_selector,
                cookies_file=payload.cookies_file,
                user_agent=payload.user_agent,
                referer=payload.referer,
                headers=payload.headers,
                extra_args=payload.extra_args,
            )
            if "error" in download_result:
                raise RuntimeError(str(download_result["error"]))

            video_file = download_result.get("video_file")
            source_audio_file = download_result.get("audio_file")
            if not video_file:
                raise RuntimeError("download completed but no video stream file was found")
            outputs["downloadedVideo"] = str(video_file)
            if source_audio_file:
                outputs["downloadedAudio"] = str(source_audio_file)
            self._emit(payload.task_id, payload.media_id, "running", "downloaded", 30, detail=Path(str(video_file)).name, outputs=outputs)
            task_store.update_status(payload.task_id, "downloaded", response_payload={"outputs": outputs}, output_files=list(outputs.values()))

            original_audio = output_root / f"{payload.media_id}.m4a"
            self._emit(payload.task_id, payload.media_id, "running", "extract-audio", 45, detail="extracting original audio", outputs=outputs)
            if source_audio_file:
                transcode_result = ffmpeg_service.transcode(str(source_audio_file), str(original_audio), audio_codec='aac')
            else:
                transcode_result = ffmpeg_service.extract_audio(str(video_file), str(original_audio), audio_codec='aac', bitrate='192k')
            if "error" in transcode_result:
                raise RuntimeError(str(transcode_result["error"]))
            outputs["originalAudio"] = str(original_audio)
            task_store.update_status(payload.task_id, "audio_extracted", response_payload={"outputs": outputs}, output_files=list(outputs.values()))

            if payload.skip_instrumental_extraction:
                self._emit(payload.task_id, payload.media_id, "running", "skip-instrumental", 60, detail="instrumental extraction skipped", outputs=outputs)
                self._emit(payload.task_id, payload.media_id, "running", "package-hls", 80, detail="building hls package", outputs=outputs)
                hls_result = self._build_skip_instrumental_hls(video_file, source_audio_file, original_audio, output_root)
                if "error" in hls_result:
                    raise RuntimeError(str(hls_result["error"]))
                outputs.update(
                    {
                        "masterPlaylist": hls_result["master_playlist"],
                        "videoPlaylist": hls_result["video_playlist"],
                    }
                )
                callback_result = self._register_arrangement_resources(payload.task_id, payload.media_id, outputs)
                final_payload = {
                    "taskId": payload.task_id,
                    "mediaId": payload.media_id,
                    "outputs": outputs,
                    "arrangementResourcesCallback": callback_result,
                    "skipInstrumentalExtraction": True,
                }
                task_store.record_finish(payload.task_id, "completed", final_payload, output_files=list(outputs.values()))
                self._emit(payload.task_id, payload.media_id, "completed", "done", 100, detail="task completed without instrumental extraction", outputs=outputs)
                return

            instrumental_result = self._run_instrumental_step(payload, original_audio, output_root, outputs)
            if "error" in instrumental_result:
                raise RuntimeError(str(instrumental_result["error"]))
            instrumental_file = self._rename_output(Path(instrumental_result["instrumental_file"]), output_root / f"{payload.media_id}.instrumental.wav")
            outputs["instrumentalAudio"] = str(instrumental_file)
            if instrumental_result.get("vocal_file"):
                vocal_file = self._rename_output(Path(instrumental_result["vocal_file"]), output_root / f"{payload.media_id}.vocals.wav")
                outputs["vocalAudio"] = str(vocal_file)
            task_store.update_status(payload.task_id, "instrumental_extracted", response_payload={"outputs": outputs}, output_files=list(outputs.values()))

            self._emit(payload.task_id, payload.media_id, "running", "package-hls", 80, detail="building hls package", outputs=outputs)
            hls_result = ffmpeg_service.build_multi_audio_hls(
                video_file=str(video_file),
                original_audio_file=str(original_audio),
                instrumental_audio_file=str(Path(outputs["instrumentalAudio"])),
                output_dir=str(output_root / "hls"),
            )
            if "error" in hls_result:
                raise RuntimeError(str(hls_result["error"]))
            outputs.update(
                {
                    "masterPlaylist": hls_result["master_playlist"],
                    "videoPlaylist": hls_result["video_playlist"],
                    "originalAudioPlaylist": hls_result["original_audio_playlist"],
                    "instrumentalAudioPlaylist": hls_result["instrumental_audio_playlist"],
                }
            )
            callback_result = self._register_arrangement_resources(payload.task_id, payload.media_id, outputs)
            final_payload = {"taskId": payload.task_id, "mediaId": payload.media_id, "outputs": outputs, "arrangementResourcesCallback": callback_result}
            task_store.record_finish(payload.task_id, "completed", final_payload, output_files=list(outputs.values()))
            self._emit(payload.task_id, payload.media_id, "completed", "done", 100, detail="task completed", outputs=outputs)
        except Exception as exc:
            error_message = str(exc)
            task_store.record_finish(payload.task_id, "failed", {"taskId": payload.task_id, "mediaId": payload.media_id, "outputs": outputs, "arrangementResourcesCallback": callback_result}, output_files=list(outputs.values()), error_message=error_message)
            self._emit(payload.task_id, payload.media_id, "failed", "error", 100, detail=error_message, outputs=outputs)

    def _emit(self, task_id: str, media_id: str, status: str, stage: str, progress: int, detail: str | None = None, outputs: dict[str, str] | None = None) -> None:
        task_progress_store.set_event(
            task_id,
            {
                "taskId": task_id,
                "mediaId": media_id,
                "status": status,
                "stage": stage,
                "progress": progress,
                "detail": detail,
                "outputs": outputs or {},
            },
        )

    @staticmethod
    def _resolve_url(payload: AsyncPackageRequest) -> str:
        if payload.url:
            return payload.url
        fields = payload.source_fields
        source_id = payload.source_id or fields.get("videoId") or fields.get("bvid") or fields.get("awemeId") or fields.get("tweetId")
        if payload.platform == "bilibili":
            bvid = fields.get("bvid") or source_id
            if bvid:
                return f"https://www.bilibili.com/video/{bvid}"
            avid = fields.get("avid")
            if avid:
                return f"https://www.bilibili.com/video/av{avid}"
        if payload.platform == "youtube" and source_id:
            return f"https://www.youtube.com/watch?v={source_id}"
        if payload.platform in {"douyin", "tiktok"} and source_id:
            return f"https://www.douyin.com/video/{source_id}"
        if payload.platform in {"twitter", "x"} and source_id:
            user = fields.get("user") or "i"
            if user == "i":
                return f"https://x.com/i/status/{source_id}"
            return f"https://x.com/{user}/status/{source_id}"
        if payload.platform == "instagram" and source_id:
            return f"https://www.instagram.com/reel/{source_id}/"
        raise ValueError("url or platform-specific sourceId/sourceFields is required")

    @staticmethod
    def _rename_output(source: Path, target: Path) -> Path:
        if source.resolve() == target.resolve():
            return source
        if target.exists():
            target.unlink()
        source.replace(target)
        return target

    def _run_instrumental_step(
        self,
        payload: AsyncPackageRequest,
        original_audio: Path,
        output_root: Path,
        outputs: dict[str, str],
    ) -> dict[str, str]:
        acquired = _instrumental_semaphore.acquire(blocking=False)
        if not acquired:
            self._emit(
                payload.task_id,
                payload.media_id,
                "running",
                "waiting-instrumental-slot",
                55,
                detail=f"waiting for accompaniment slot (max {_instrumental_limit})",
                outputs=outputs,
            )
            task_store.update_status(payload.task_id, "waiting_instrumental_slot", response_payload={"outputs": outputs}, output_files=list(outputs.values()))
            _instrumental_semaphore.acquire()

        try:
            self._emit(payload.task_id, payload.media_id, "running", "extract-instrumental", 60, detail="building accompaniment", outputs=outputs)
            return onnx_service.infer(
                str(original_audio),
                task_type="extract_instrumental",
                stem_mode="vocals_and_instrumental",
                output_format="wav",
                output_dir=str(output_root),
            )
        finally:
            _instrumental_semaphore.release()

    @staticmethod
    def _build_skip_instrumental_hls(
        video_file: str,
        source_audio_file: str | None,
        original_audio: Path,
        output_root: Path,
    ) -> dict[str, str]:
        source_audio_suffix = Path(source_audio_file).suffix.lower() if source_audio_file else ""
        if source_audio_suffix == ".m4a":
            return ffmpeg_service.build_muxed_hls(
                video_file=str(video_file),
                audio_file=str(original_audio),
                output_dir=str(output_root / "hls"),
            )
        return ffmpeg_service.build_single_mp4_hls(
            input_file=str(video_file),
            output_dir=str(output_root / "hls"),
        )

    @staticmethod
    def _build_resource_items(outputs: dict[str, str]) -> list[dict[str, str]]:
        variant_mapping = [
            ("masterPlaylist", "hls-master"),
            ("videoPlaylist", "hls-video"),
            ("originalAudioPlaylist", "hls-audio-original"),
            ("instrumentalAudioPlaylist", "hls-audio-instrumental"),
            ("downloadedVideo", "source-video"),
            ("downloadedAudio", "source-audio"),
            ("originalAudio", "original-audio"),
            ("instrumentalAudio", "instrumental-audio"),
            ("vocalAudio", "vocal-audio"),
        ]
        resources: list[dict[str, str]] = []
        for key, variant_name in variant_mapping:
            source_file = outputs.get(key)
            if not source_file:
                continue
            resources.append({"sourceFile": source_file, "variantName": variant_name})
        return resources

    def _register_arrangement_resources(self, task_id: str, media_id: str, outputs: dict[str, str]) -> dict[str, object] | None:
        resources = self._build_resource_items(outputs)
        if not resources:
            return None
        result = arrangement_client.register_task_resources(task_id, media_id, resources)
        status_code = result.get("status_code")
        if result.get("error"):
            raise RuntimeError(f"arrangement resource callback failed: {result['error']}")
        if not isinstance(status_code, int) or status_code < 200 or status_code >= 300:
            raise RuntimeError(f"arrangement resource callback returned {status_code}: {result.get('response_text', '')}")
        return result


async_package_service = AsyncPackageService()
