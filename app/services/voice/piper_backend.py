# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import httpx


@dataclass(frozen=True)
class PiperModelSpec:
    name: str
    model_url: str
    config_url: str
    model_sha256: str


DEFAULT_RU_MODEL = PiperModelSpec(
    name="ru_RU-denis-medium",
    model_url=(
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx?download=true"
    ),
    config_url=(
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
        "ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx.json?download=true"
    ),
    model_sha256="15fab56e11a097858ee115545d0f697fc2a316c41a291a5362349fb870411b0a",
)


class PiperModelManager:
    def __init__(
        self,
        *,
        model_dir: str | Path,
        model_name: str = DEFAULT_RU_MODEL.name,
        timeout_s: float = 120.0,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.model_name = str(model_name or DEFAULT_RU_MODEL.name).strip()
        self.timeout_s = max(15.0, float(timeout_s or 120.0))
        self._lock = threading.Lock()

    @property
    def model_path(self) -> Path:
        return self.model_dir / f"{self.model_name}.onnx"

    @property
    def config_path(self) -> Path:
        return self.model_dir / f"{self.model_name}.onnx.json"

    def _spec(self) -> PiperModelSpec:
        if self.model_name != DEFAULT_RU_MODEL.name:
            raise ValueError(
                f"Unsupported bundled voice model: {self.model_name}. "
                f"Use {DEFAULT_RU_MODEL.name} or provide a local model path in a future provider."
            )
        return DEFAULT_RU_MODEL

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _download(self, url: str, target: Path, *, max_bytes: int) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(target.suffix + ".part")
        part.unlink(missing_ok=True)
        total = 0
        timeout = httpx.Timeout(connect=20.0, read=self.timeout_s, write=30.0, pool=self.timeout_s)
        try:
            with httpx.stream(
                "GET",
                url,
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": "BLACK-CROWN-OPS/voice-v5"},
            ) as response:
                response.raise_for_status()
                declared = int(response.headers.get("content-length") or 0)
                if declared and declared > max_bytes:
                    raise RuntimeError(f"voice asset too large: {declared} > {max_bytes}")
                with part.open("wb") as fh:
                    for chunk in response.iter_bytes(1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            raise RuntimeError(f"voice asset exceeded {max_bytes} bytes")
                        fh.write(chunk)
            if total <= 0:
                raise RuntimeError("downloaded empty voice asset")
            part.replace(target)
        except Exception:
            part.unlink(missing_ok=True)
            raise

    def ensure(self) -> tuple[Path, Path]:
        spec = self._spec()
        with self._lock:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            model_ok = self.model_path.exists() and self.model_path.stat().st_size > 10_000_000
            if model_ok:
                model_ok = self._sha256(self.model_path) == spec.model_sha256
            if not model_ok:
                self.model_path.unlink(missing_ok=True)
                self._download(spec.model_url, self.model_path, max_bytes=70 * 1024 * 1024)
                actual = self._sha256(self.model_path)
                if actual != spec.model_sha256:
                    self.model_path.unlink(missing_ok=True)
                    raise RuntimeError("Piper model SHA256 mismatch")

            config_ok = self.config_path.exists() and self.config_path.stat().st_size > 500
            if not config_ok:
                self.config_path.unlink(missing_ok=True)
                self._download(spec.config_url, self.config_path, max_bytes=128 * 1024)

            try:
                payload = json.loads(self.config_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict) or not payload.get("audio"):
                    raise ValueError("invalid Piper config")
            except Exception:
                self.config_path.unlink(missing_ok=True)
                raise RuntimeError("Piper config validation failed")

            return self.model_path, self.config_path


class PiperBackend:
    def __init__(self, manager: PiperModelManager) -> None:
        self.manager = manager
        self._voice: Any = None
        self._voice_key: tuple[str, str] | None = None
        self._lock = threading.Lock()

    def ensure_model(self) -> tuple[Path, Path]:
        return self.manager.ensure()

    def _load_voice(self):
        model_path, config_path = self.manager.ensure()
        key = (str(model_path), str(config_path))
        if self._voice is not None and self._voice_key == key:
            return self._voice
        from piper import PiperVoice

        self._voice = PiperVoice.load(str(model_path), config_path=str(config_path), use_cuda=False)
        self._voice_key = key
        return self._voice

    def synthesize_wav(self, text: str, output_path: str | Path, profile: Mapping[str, Any] | None = None) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        profile = profile or {}
        conversational_voice = str(profile.get("voice") or "TEAMMATE").upper()
        brain = str(profile.get("difficulty") or "Normal").upper()

        length_scale = 0.94 if conversational_voice == "TEAMMATE" else 1.03
        if brain == "DEMON":
            length_scale = max(0.90, length_scale - 0.03)

        from piper import SynthesisConfig

        syn_config = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=0.55,
            noise_w_scale=0.70,
        )

        with self._lock:
            voice = self._load_voice()
            with wave.open(str(output), "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=syn_config)

        if not output.exists() or output.stat().st_size <= 44:
            raise RuntimeError("Piper produced an empty WAV")
        return output
