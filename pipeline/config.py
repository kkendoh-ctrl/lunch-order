"""環境変数を読み出して型安全に提供する。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(key, default)
    if required and not val:
        raise RuntimeError(f"環境変数 {key} が未設定。.env を確認してください")
    return val or ""


def _get_path(key: str, required: bool = True) -> Path:
    return Path(_get(key, required=required))


def _get_float(key: str, default: float) -> float:
    return float(_get(key, str(default)))


def _get_int(key: str, default: int) -> int:
    return int(_get(key, str(default)))


def _get_bool(key: str, default: bool) -> bool:
    return _get(key, str(default)).lower() in ("true", "1", "yes", "on")


@dataclass(frozen=True)
class Config:
    jpr_inbox: Path
    vault: Path
    transcripts_dir: Path
    notes_dir: Path

    skip_duration_s: float
    skip_silence_ratio: float
    skip_silence_db: float

    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_language: str
    whisper_initial_prompt_path: Path | None
    whisper_align_enabled: bool

    file_stable_wait_s: float
    file_stable_poll_s: float

    anthropic_api_key: str
    anthropic_model: str
    anthropic_max_tokens: int
    anthropic_effort: str
    structuring_prompt_path: Path | None

    # Phase 4: PII マスキング。既存のテスト fixture を壊さないようデフォルト付き。
    pii_mask_enabled: bool = True
    pii_dict_path: Path | None = None
    pii_allowlist_path: Path | None = None

    @classmethod
    def load(cls) -> "Config":
        vault = _get_path("VAULT_PATH")
        initial_prompt_rel = _get("WHISPER_INITIAL_PROMPT_PATH")
        initial_prompt_path = vault / initial_prompt_rel if initial_prompt_rel else None
        structuring_prompt_rel = _get("STRUCTURING_PROMPT_PATH")
        structuring_prompt_path = (
            vault / structuring_prompt_rel if structuring_prompt_rel else None
        )
        pii_dict_raw = _get("PII_DICT_PATH")
        pii_dict_path = Path(pii_dict_raw) if pii_dict_raw else None
        pii_allowlist_raw = _get("PII_ALLOWLIST_PATH")
        pii_allowlist_path = (
            Path(pii_allowlist_raw) if pii_allowlist_raw else None
        )
        return cls(
            jpr_inbox=_get_path("JPR_INBOX_PATH"),
            vault=vault,
            transcripts_dir=vault / "_transcripts",
            notes_dir=vault / "録音",
            skip_duration_s=_get_float("SKIP_DURATION_THRESHOLD_S", 10),
            skip_silence_ratio=_get_float("SKIP_SILENCE_RATIO", 0.95),
            skip_silence_db=_get_float("SKIP_SILENCE_DB", -40),
            whisper_model=_get("WHISPER_MODEL", "large-v3"),
            whisper_device=_get("WHISPER_DEVICE", "cpu"),
            whisper_compute_type=_get("WHISPER_COMPUTE_TYPE", "int8"),
            whisper_language=_get("WHISPER_LANGUAGE", "ja"),
            whisper_initial_prompt_path=initial_prompt_path,
            whisper_align_enabled=_get_bool("WHISPER_ALIGN_ENABLED", True),
            file_stable_wait_s=_get_float("FILE_STABLE_WAIT_S", 5),
            file_stable_poll_s=_get_float("FILE_STABLE_POLL_S", 2),
            anthropic_api_key=_get("ANTHROPIC_API_KEY"),
            anthropic_model=_get("ANTHROPIC_MODEL", "claude-opus-4-7"),
            anthropic_max_tokens=_get_int("ANTHROPIC_MAX_TOKENS", 8192),
            anthropic_effort=_get("ANTHROPIC_EFFORT", "medium"),
            structuring_prompt_path=structuring_prompt_path,
            pii_mask_enabled=_get_bool("PII_MASK_ENABLED", True),
            pii_dict_path=pii_dict_path,
            pii_allowlist_path=pii_allowlist_path,
        )

    def load_initial_prompt(self) -> str | None:
        if not self.whisper_initial_prompt_path:
            return None
        if not self.whisper_initial_prompt_path.exists():
            return None
        return self.whisper_initial_prompt_path.read_text(encoding="utf-8").strip()

    def load_structuring_prompt(self) -> str | None:
        if not self.structuring_prompt_path:
            return None
        if not self.structuring_prompt_path.exists():
            return None
        return self.structuring_prompt_path.read_text(encoding="utf-8")

    @property
    def structuring_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def transcript_path_for(cfg: Config, audio_path: Path) -> Path:
    """audio: .../Just Press Record/2026-05-23/13-39-19.m4a
       → .../音声記憶/_transcripts/2026-05-23/13-39-19.json"""
    date_folder = audio_path.parent.name
    stem = audio_path.stem
    return cfg.transcripts_dir / date_folder / f"{stem}.json"


def skipped_marker_path_for(cfg: Config, audio_path: Path) -> Path:
    """同上、ただし .skipped 拡張子"""
    date_folder = audio_path.parent.name
    stem = audio_path.stem
    return cfg.transcripts_dir / date_folder / f"{stem}.skipped"


def is_already_processed(cfg: Config, audio_path: Path) -> bool:
    return (
        transcript_path_for(cfg, audio_path).exists()
        or skipped_marker_path_for(cfg, audio_path).exists()
    )


def note_path_for(cfg: Config, audio_path: Path) -> Path:
    """audio: .../Just Press Record/2026-05-23/13-39-19.m4a
       → .../音声記憶/録音/2026-05-23/13-39-19.md"""
    date_folder = audio_path.parent.name
    stem = audio_path.stem
    return cfg.notes_dir / date_folder / f"{stem}.md"


def is_structured(cfg: Config, audio_path: Path) -> bool:
    return note_path_for(cfg, audio_path).exists()
