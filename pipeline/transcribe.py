"""WhisperX で文字起こし → JSON 出力。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Config


_model_cache: dict[str, Any] = {}


def _load_model(cfg: Config):
    """WhisperX モデルをロード。プロセス内で1回だけ。"""
    import whisperx  # 重いので関数内 import

    key = f"{cfg.whisper_model}:{cfg.whisper_device}:{cfg.whisper_compute_type}"
    if key not in _model_cache:
        _model_cache[key] = whisperx.load_model(
            cfg.whisper_model,
            device=cfg.whisper_device,
            compute_type=cfg.whisper_compute_type,
            language=cfg.whisper_language,
        )
    return _model_cache[key]


def _load_align_model(cfg: Config):
    import whisperx

    key = f"align:{cfg.whisper_language}:{cfg.whisper_device}"
    if key not in _model_cache:
        model, metadata = whisperx.load_align_model(
            language_code=cfg.whisper_language, device=cfg.whisper_device
        )
        _model_cache[key] = (model, metadata)
    return _model_cache[key]


def transcribe(audio_path: Path, cfg: Config) -> dict:
    """音声ファイル → セグメント+全文の dict。
    呼び出し側で JSON 保存する。"""
    import whisperx

    model = _load_model(cfg)
    audio = whisperx.load_audio(str(audio_path))

    initial_prompt = cfg.load_initial_prompt()
    transcribe_kwargs = {}
    if initial_prompt:
        transcribe_kwargs["initial_prompt"] = initial_prompt

    result = model.transcribe(audio, **transcribe_kwargs)

    # 単語レベルアライメント(任意)
    if cfg.whisper_align_enabled:
        try:
            align_model, metadata = _load_align_model(cfg)
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                device=cfg.whisper_device,
            )
        except Exception as e:
            # アライメント失敗は致命的ではない。警告だけ出して続行
            print(f"  [warn] alignment failed: {e}")

    segments = [
        {
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": str(s.get("text", "")).strip(),
        }
        for s in result.get("segments", [])
    ]
    full_text = " ".join(s["text"] for s in segments if s["text"])
    duration = segments[-1]["end"] if segments else 0.0

    return {
        "audio_path": str(audio_path),
        "duration_s": duration,
        "model": cfg.whisper_model,
        "language": cfg.whisper_language,
        "align_enabled": cfg.whisper_align_enabled,
        "transcribed_at": datetime.now(timezone.utc).isoformat(),
        "segments": segments,
        "text": full_text,
    }


def save_transcript(result: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_skipped_marker(out_path: Path, reason: str, duration_s: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "reason": reason,
                "duration_s": duration_s,
                "skipped_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
