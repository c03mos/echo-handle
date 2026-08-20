import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None

from app.core.config import settings
from app.services.ffmpeg_service import ffmpeg_service


class OnnxService:
    _kim_n_fft = 6144
    _kim_hop_length = 1024
    _kim_dim_f = 3072
    _kim_dim_t = 256

    def load_model(self) -> dict[str, str]:
        model_path = Path(settings.onnx_model_path)
        if ort is None:
            return {"error": "onnxruntime is not installed"}
        if not model_path.exists():
            return {"error": f"model not found: {model_path}"}
        session = ort.InferenceSession(str(model_path))
        return {"model": model_path.name, "inputs": str(len(session.get_inputs()))}

    def infer(self, media_path: str, task_type: str, **kwargs: str) -> dict[str, str]:
        if task_type == "extract_instrumental":
            output_dir = kwargs.get("output_dir")
            output_format = kwargs.get("output_format", "wav")
            stem_mode = kwargs.get("stem_mode", "vocals_and_instrumental")
            if output_dir is None:
                return {"error": "output_dir is required for extract_instrumental"}
            return self.extract_instrumental(media_path, output_dir, output_format, stem_mode)

        if task_type == "audio_to_srt":
            output_dir = kwargs.get("output_dir")
            language = kwargs.get("language", "auto")
            if output_dir is None:
                return {"error": "output_dir is required for audio_to_srt"}
            return self.audio_to_srt(media_path, output_dir, language)

        return {"status": "placeholder", "media_path": media_path, "task_type": task_type, **kwargs}

    def extract_instrumental(
        self,
        media_path: str,
        output_dir: str,
        output_format: str,
        stem_mode: str,
    ) -> dict[str, str]:
        if ort is None:
            return {"error": "onnxruntime is not installed"}

        model_path = Path(settings.kim_model_path).resolve()
        if not model_path.exists():
            return {"error": f"Kim model not found: {model_path}"}

        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        input_path = Path(media_path)

        with TemporaryDirectory(prefix="kim_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            normalized_wav = temp_dir_path / "input_44k.wav"
            converted = ffmpeg_service.pcm_44k_stereo(str(input_path), str(normalized_wav))
            if "error" in converted:
                return converted

            waveform, sample_rate = self._read_wave(normalized_wav)
            if sample_rate != 44100:
                return {"error": f"unexpected sample rate after ffmpeg conversion: {sample_rate}"}

            session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
            vocals, instrumental = self._run_kim(session, waveform)

            instrumental_wav = output_root / f"{input_path.stem}_instrumental.wav"
            vocals_wav = output_root / f"{input_path.stem}_vocals.wav"
            self._write_wave(instrumental_wav, instrumental, sample_rate)
            self._write_wave(vocals_wav, vocals, sample_rate)

            instrumental_output = self._maybe_convert_output(instrumental_wav, output_format)
            if "error" in instrumental_output:
                return instrumental_output

            result: dict[str, str] = {
                "instrumental_file": instrumental_output["output_file"],
                "status": "completed",
            }

            if stem_mode in {"vocals_only", "vocals_and_instrumental"}:
                vocals_output = self._maybe_convert_output(vocals_wav, output_format)
                if "error" in vocals_output:
                    return vocals_output
                result["vocal_file"] = vocals_output["output_file"]

            return result

    def audio_to_srt(self, media_path: str, output_dir: str, language: str) -> dict[str, str]:
        model_path = self._resolve_whisper_cpp_model()
        if model_path is None:
            return {
                "error": (
                    "whisper.cpp model not found; place a ggml model such as ggml-base.bin under "
                    "../modelZoo/whisper.cpp or set WHISPER_CPP_MODEL_PATH"
                )
            }

        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        input_path = Path(media_path)
        output_file = output_root / f"{input_path.stem}.srt"
        result = ffmpeg_service.transcribe_to_srt(str(input_path), str(output_file), str(model_path), language=language)
        if "error" in result:
            return result
        return {"output_file": str(output_file), "status": "completed", "model_file": str(model_path)}

    def _run_kim(self, session: "ort.InferenceSession", waveform: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        chunk_size = self._kim_hop_length * (self._kim_dim_t - 1)
        padded_length = int(np.ceil(waveform.shape[1] / chunk_size) * chunk_size)
        padded = np.pad(waveform, ((0, 0), (0, padded_length - waveform.shape[1])))
        vocals = np.zeros_like(padded, dtype=np.float32)
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name

        for start in range(0, padded.shape[1], chunk_size):
            stop = start + chunk_size
            chunk = padded[:, start:stop]
            tensor = self._wave_to_tensor(chunk)[None, ...]
            prediction = session.run([output_name], {input_name: tensor})[0][0]
            vocals[:, start:stop] = self._tensor_to_wave(prediction, chunk.shape[1])

        vocals = vocals[:, : waveform.shape[1]]
        instrumental = waveform - vocals
        return vocals, instrumental

    def _wave_to_tensor(self, waveform: np.ndarray) -> np.ndarray:
        spec = self._stft(waveform)
        spec = spec[:, : self._kim_dim_f, : self._kim_dim_t]
        return np.concatenate([spec.real, spec.imag], axis=0).astype(np.float32)

    def _tensor_to_wave(self, tensor: np.ndarray, target_length: int) -> np.ndarray:
        real = tensor[:2]
        imag = tensor[2:]
        spec = real + (1j * imag)
        full_spec = np.zeros((2, self._kim_n_fft // 2 + 1, self._kim_dim_t), dtype=np.complex64)
        full_spec[:, : self._kim_dim_f, :] = spec
        waveform = self._istft(full_spec, target_length)
        return waveform.astype(np.float32)

    def _stft(self, waveform: np.ndarray) -> np.ndarray:
        pad = self._kim_n_fft // 2
        padded = np.pad(waveform, ((0, 0), (pad, pad)))
        frames = []
        window = np.hanning(self._kim_n_fft + 1)[:-1].astype(np.float32)
        for frame_index in range(self._kim_dim_t):
            start = frame_index * self._kim_hop_length
            frame = padded[:, start : start + self._kim_n_fft] * window[None, :]
            frames.append(np.fft.rfft(frame, axis=1))
        return np.stack(frames, axis=-1)

    def _istft(self, spec: np.ndarray, target_length: int) -> np.ndarray:
        pad = self._kim_n_fft // 2
        total_length = target_length + (pad * 2)
        waveform = np.zeros((2, total_length), dtype=np.float32)
        window = np.hanning(self._kim_n_fft + 1)[:-1].astype(np.float32)
        window_sum = np.zeros(total_length, dtype=np.float32)

        for frame_index in range(spec.shape[-1]):
            start = frame_index * self._kim_hop_length
            frame = np.fft.irfft(spec[:, :, frame_index], n=self._kim_n_fft, axis=1).astype(np.float32)
            waveform[:, start : start + self._kim_n_fft] += frame * window[None, :]
            window_sum[start : start + self._kim_n_fft] += window**2

        safe = np.where(window_sum > 1e-8, window_sum, 1.0)
        waveform /= safe[None, :]
        return waveform[:, pad : pad + target_length]

    @staticmethod
    def _read_wave(path: Path) -> tuple[np.ndarray, int]:
        with wave.open(str(path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channels = wav_file.getnchannels()
            frames = wav_file.readframes(wav_file.getnframes())

        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        audio = audio.reshape(-1, channels).T
        if channels == 1:
            audio = np.vstack([audio, audio])
        return audio[:2], sample_rate

    @staticmethod
    def _write_wave(path: Path, waveform: np.ndarray, sample_rate: int) -> None:
        clipped = np.clip(waveform.T, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())

    @staticmethod
    def _maybe_convert_output(path: Path, output_format: str) -> dict[str, str]:
        if output_format == "wav":
            return {"output_file": str(path)}
        converted_path = path.with_suffix(f".{output_format}")
        return ffmpeg_service.transcode(str(path), str(converted_path), audio_codec=None)

    @staticmethod
    def _resolve_whisper_cpp_model() -> Path | None:
        configured = Path(settings.whisper_cpp_model_path).resolve()
        if configured.exists():
            return configured

        candidate_dir = Path(settings.model_zoo_dir).resolve() / "whisper.cpp"
        if candidate_dir.exists():
            for pattern in ("ggml-*.bin", "*.gguf", "*.bin"):
                matches = sorted(candidate_dir.glob(pattern))
                if matches:
                    return matches[0]
        return None


onnx_service = OnnxService()
