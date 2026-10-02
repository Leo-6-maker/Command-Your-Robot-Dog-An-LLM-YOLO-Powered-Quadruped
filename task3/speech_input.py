"""Optional local English speech input for the existing Task 3 command loop."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np


@dataclass(frozen=True)
class SpeechResult:
    text: str
    model: str
    latency_s: float


class SpeechInputError(RuntimeError):
    """Microphone, audio file, or transcription could not produce a command."""


class LocalSpeechInput:
    """Record a short utterance and transcribe locally with faster-whisper.

    The model is loaded on first use, so typed commands never pay the STT
    startup cost. Audio is kept in memory and is never written to the repo.
    """

    def __init__(self, model: str = "base.en", duration_s: float = 7.0):
        if not 1 <= duration_s <= 30:
            raise ValueError("voice duration must be between 1 and 30 seconds")
        self.model_name = model
        self.duration_s = float(duration_s)
        self._model = None

    def record_and_transcribe(self) -> SpeechResult:
        if shutil.which("arecord"):
            try:
                capture = subprocess.run(
                    ["arecord", "-q", "-f", "S16_LE", "-r", "16000",
                     "-c", "1", "-d", str(round(self.duration_s)),
                     "-t", "raw", "-"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=self.duration_s + 5, check=True,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise SpeechInputError(f"microphone recording failed: {exc}") from exc
            audio = np.frombuffer(capture.stdout, dtype="<i2").astype(np.float32)
            return self.transcribe_audio(audio / 32768.0)
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:
            raise SpeechInputError(
                "microphone support is missing; install task3/requirements-bonus.txt"
            ) from exc
        try:
            audio = sd.rec(
                int(self.duration_s * 16_000), samplerate=16_000,
                channels=1, dtype="float32",
            )
            sd.wait()
        except Exception as exc:
            raise SpeechInputError(f"microphone recording failed: {exc}") from exc
        return self.transcribe_audio(audio[:, 0])

    def transcribe_file(self, path: str | Path) -> SpeechResult:
        source = Path(path).expanduser()
        if not source.is_file():
            raise SpeechInputError(f"audio file not found: {source}")
        return self._transcribe(str(source))

    def transcribe_audio(self, audio: np.ndarray) -> SpeechResult:
        if audio.ndim != 1 or audio.size == 0 or not np.isfinite(audio).all():
            raise SpeechInputError("audio must be a nonempty mono recording")
        if float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))) < 0.003:
            raise SpeechInputError("no audible speech detected")
        return self._transcribe(audio)

    def _transcribe(self, source: str | np.ndarray) -> SpeechResult:
        started = time.monotonic()
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise SpeechInputError(
                    "local STT is missing; install task3/requirements-bonus.txt"
                ) from exc
            try:
                self._model = WhisperModel(
                    self.model_name, device="cpu", compute_type="int8"
                )
            except Exception as exc:
                raise SpeechInputError(f"STT model could not load: {exc}") from exc
        try:
            segments, _ = self._model.transcribe(
                source, language="en", beam_size=5,
                condition_on_previous_text=False, vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except Exception as exc:
            raise SpeechInputError(f"transcription failed: {exc}") from exc
        if not text:
            raise SpeechInputError("no English speech was transcribed")
        return SpeechResult(text, self.model_name, time.monotonic() - started)
