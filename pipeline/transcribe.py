"""WhisperX で文字起こし → JSON 出力。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Config


_model_cache: dict[str, Any] = {}


def _load_model(cfg: Config):
    """WhisperX モデルをロード。プロセス内で1回だけ。

    WhisperX 3.x で `initial_prompt` の渡し方が変わった:
      旧: `model.transcribe(audio, initial_prompt=...)`
      新: `whisperx.load_model(..., asr_options={"initial_prompt": ...})`
    cfg は process-static なので prompt もプロセス内では変わらない前提。
    キャッシュキーには含めない(変えたければプロセス再起動)。"""
    import whisperx  # 重いので関数内 import

    key = f"{cfg.whisper_model}:{cfg.whisper_device}:{cfg.whisper_compute_type}"
    if key not in _model_cache:
        kwargs: dict = {
            "device": cfg.whisper_device,
            "compute_type": cfg.whisper_compute_type,
            "language": cfg.whisper_language,
            "vad_method": cfg.whisper_vad_method,
        }
        # asr_options: ハルシネーション抑止スタック + initial_prompt を組み立て。
        # WhisperX 3.x はこれを faster-whisper の TranscriptionOptions へ
        # 引き渡す。デフォルトを faster-whisper のデフォルト値で明示的に
        # 上書きしているのは、WhisperX 経由だと一部の defaults が伝播しない
        # ケースが観測されているため(`temperature` の単一値固定など)。
        asr_options: dict = {
            "temperatures": list(cfg.whisper_temperatures),
            "compression_ratio_threshold": cfg.whisper_compression_ratio_threshold,
            "log_prob_threshold": cfg.whisper_log_prob_threshold,
            "no_speech_threshold": cfg.whisper_no_speech_threshold,
            "repetition_penalty": cfg.whisper_repetition_penalty,
        }
        if cfg.whisper_hallucination_silence_threshold > 0:
            asr_options["hallucination_silence_threshold"] = (
                cfg.whisper_hallucination_silence_threshold
            )
        if not cfg.whisper_condition_on_previous_text:
            asr_options["condition_on_previous_text"] = False
        prompt = cfg.load_initial_prompt()
        if prompt:
            asr_options["initial_prompt"] = prompt
        kwargs["asr_options"] = asr_options
        _model_cache[key] = whisperx.load_model(cfg.whisper_model, **kwargs)
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


def _load_diarize_pipeline(cfg: Config):
    """WhisperX の diarization pipeline。HF_TOKEN が必要(pyannote モデル)。"""
    import whisperx

    key = f"diarize:{cfg.whisper_device}"
    if key not in _model_cache:
        _model_cache[key] = whisperx.diarize.DiarizationPipeline(
            use_auth_token=cfg.hf_token, device=cfg.whisper_device
        )
    return _model_cache[key]


def _maybe_diarize(result: dict, audio, cfg: Config) -> dict:
    """`cfg.diarize_enabled and cfg.hf_token` の時だけ話者分離を試みる。

    失敗(モデル無し/権限無し/メモリ不足)は致命的ではないので警告して原本を返す。"""
    if not cfg.diarize_enabled:
        return result
    if not cfg.hf_token:
        print("  [warn] DIARIZE_ENABLED=true だが HF_TOKEN が無いので skip")
        return result
    try:
        import whisperx

        pipeline = _load_diarize_pipeline(cfg)
        diarize_segments = pipeline(audio)
        result = whisperx.assign_word_speakers(diarize_segments, result)
    except Exception as e:
        print(f"  [warn] diarization failed: {e}")
    return result


def transcribe(audio_path: Path, cfg: Config) -> dict:
    """音声ファイル → セグメント+全文の dict。
    呼び出し側で JSON 保存する。"""
    import whisperx

    model = _load_model(cfg)
    audio = whisperx.load_audio(str(audio_path))

    # initial_prompt は _load_model 内で asr_options 経由で注入済(WhisperX 3.x)
    result = model.transcribe(audio)

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

    # 話者分離(任意、Phase 5c)
    result = _maybe_diarize(result, audio, cfg)

    segments = [
        {
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": str(s.get("text", "")).strip(),
            **(
                {"speaker": str(s["speaker"])}
                if s.get("speaker") is not None
                else {}
            ),
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
        "diarize_enabled": cfg.diarize_enabled,
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
