from typing import Any, Literal

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: dict | list[dict] | None = None


class ExtractAudioRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    input_file: str = Field(..., alias="inputFile")
    output_dir: str = Field(..., alias="outputDir")
    output_audio_format: Literal["mp3", "wav", "aac", "flac", "m4a"] = Field(alias="outputAudioFormat")
    audio_codec: str | None = Field(default=None, alias="audioCodec")
    sample_rate: int | None = Field(default=None, alias="sampleRate")
    bitrate: str | None = None


class ExtractAudioResult(BaseModel):
    task_id: str = Field(alias="taskId")
    output_file: str = Field(alias="outputFile")
    duration: float | None = None


class TranscodeRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    input_file: str = Field(..., alias="inputFile")
    output_dir: str = Field(..., alias="outputDir")
    output_format: str = Field(..., alias="outputFormat")
    video_codec: str | None = Field(default=None, alias="videoCodec")
    audio_codec: str | None = Field(default=None, alias="audioCodec")
    resolution: str | None = None
    bitrate: str | None = None


class TranscodeResult(BaseModel):
    task_id: str = Field(alias="taskId")
    output_file: str = Field(alias="outputFile")


class ExtractInstrumentalRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    input_file: str = Field(..., alias="inputFile")
    output_dir: str = Field(..., alias="outputDir")
    output_format: Literal["wav", "mp3", "flac"] = Field(alias="outputFormat")
    stem_mode: Literal["instrumental_only", "vocals_only", "vocals_and_instrumental"] = Field(alias="stemMode")


class ExtractInstrumentalResult(BaseModel):
    task_id: str = Field(alias="taskId")
    instrumental_file: str = Field(alias="instrumentalFile")
    vocal_file: str | None = Field(default=None, alias="vocalFile")


class DownloadVideoRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    media_id: str = Field(..., alias="mediaId")
    platform: str
    url: str
    output_dir: str = Field(default="../Data/downloads", alias="outputDir")
    format_selector: str | None = Field(default=None, alias="formatSelector")
    extract_audio: bool = Field(default=False, alias="extractAudio")
    audio_format: str | None = Field(default=None, alias="audioFormat")
    cookies_file: str | None = Field(default=None, alias="cookiesFile")
    user_agent: str | None = Field(default=None, alias="userAgent")
    referer: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    subtitles: bool = False
    subtitle_languages: list[str] = Field(default_factory=list, alias="subtitleLanguages")
    playlist_items: str | None = Field(default=None, alias="playlistItems")
    extra_args: list[str] = Field(default_factory=list, alias="extraArgs")


class DownloadVideoResult(BaseModel):
    task_id: str = Field(alias="taskId")
    media_id: str = Field(alias="mediaId")
    platform: str
    source_url: str = Field(alias="sourceUrl")
    output_dir: str = Field(alias="outputDir")
    downloaded_files: list[str] = Field(default_factory=list, alias="downloadedFiles")
    stdout: str | None = None


class AsyncPackageRequest(BaseModel):
    task_id: str = Field(..., alias="taskId")
    media_id: str = Field(..., alias="mediaId")
    platform: Literal["youtube", "bilibili", "douyin", "tiktok", "twitter", "x", "instagram", "generic"]
    source_id: str | None = Field(default=None, alias="sourceId")
    source_fields: dict[str, str] = Field(default_factory=dict, alias="sourceFields")
    url: str | None = None
    output_dir: str = Field(default="../Data/tasks", alias="outputDir")
    format_selector: str | None = Field(default="bv*+ba/b", alias="formatSelector")
    cookies_file: str | None = Field(default=None, alias="cookiesFile")
    user_agent: str | None = Field(default=None, alias="userAgent")
    referer: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    extra_args: list[str] = Field(default_factory=list, alias="extraArgs")
    skip_instrumental_extraction: bool = Field(default=False, alias="skipInstrumentalExtraction")


class AsyncAcceptedResult(BaseModel):
    task_id: str = Field(alias="taskId")
    media_id: str = Field(alias="mediaId")
    status: str
    ws_path: str = Field(alias="wsPath")


class AsyncStatusEvent(BaseModel):
    task_id: str = Field(alias="taskId")
    media_id: str = Field(alias="mediaId")
    status: str
    stage: str
    progress: int
    detail: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)


class TaskRunRecord(BaseModel):
    id: int
    task_id: str = Field(alias="taskId")
    task_type: str = Field(alias="taskType")
    status: str
    input_file: str = Field(alias="inputFile")
    output_files: list[str] = Field(default_factory=list, alias="outputFiles")
    request_json: dict[str, Any] | None = Field(default=None, alias="requestJson")
    response_json: dict[str, Any] | None = Field(default=None, alias="responseJson")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
