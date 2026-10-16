"""環境変数を読み出して型安全に提供する。"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# override=True で `.env` を Windows ユーザー環境変数より優先する。
# 過去にユーザー環境変数に古い ANTHROPIC_API_KEY が残っていて `.env` の
# 新キーが効かない事故が起きたため、`.env` を single source of truth に
# 固定する。
load_dotenv(override=True)


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


def _get_float_tuple(key: str, default: tuple[float, ...]) -> tuple[float, ...]:
    """カンマ区切り文字列 → tuple[float, ...]。未設定なら default を返す。"""
    raw = os.environ.get(key, "")
    if not raw.strip():
        return default
    return tuple(float(x.strip()) for x in raw.split(",") if x.strip())


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

    # WhisperX VAD エンジン。pyannote (default) は Windows + CPU で長尺音声に
    # ハングする既知問題があるので、bronzeman 運用では silero を推奨。
    # デフォルトはあえて pyannote のまま(明示的に切り替える運用)。
    whisper_vad_method: str = "pyannote"

    # faster-whisper の `condition_on_previous_text`。True (FW デフォルト) だと
    # 前セグメントの結果を次の generation に渡すので、小音量・断続的な音声で
    # 「ディアリング ディアリング ...」のような繰り返しハルシネーションが
    # 発生する。False にすると各セグメント独立で生成され、ハルシネーション
    # 連鎖を断ち切れる。文脈一貫性は若干下がるが voice memo 用途では損が小さい。
    whisper_condition_on_previous_text: bool = False

    # 温度フォールバック (faster-whisper の `temperature`)。リストを渡すと
    # 各温度で順次試し、compression_ratio_threshold / log_prob_threshold を
    # 満たすまでフォールバック。`(0.0,)` だけにすると無効化、低温固定で生成。
    whisper_temperatures: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

    # 圧縮率しきい値。生成テキストを gzip した時の比率がこの値を超えると
    # 「同一フレーズ連発(ハルシネーション)」とみなして温度を上げて再試行。
    # FW デフォルト 2.4。低くするほど厳しい。
    whisper_compression_ratio_threshold: float = 2.4

    # 平均 log probability しきい値。これより低い (= 自信が無い) なら
    # 温度を上げて再試行。FW デフォルト -1.0。
    whisper_log_prob_threshold: float = -1.0

    # 無音判定しきい値 (0〜1)。no_speech_prob がこの値を超えるセグメントは
    # 文字起こしを破棄。FW デフォルト 0.6。下げるほど無音判定が緩い。
    whisper_no_speech_threshold: float = 0.6

    # 繰り返しペナルティ。1.0 = 無効、1.1 = 軽めの抑制 (同一トークンを
    # 繰り返した時の確率を割引)。faster-whisper 1.2+ サポート。
    # 業務会話で 1.1 程度なら正常文に悪影響なし。
    whisper_repetition_penalty: float = 1.1

    # faster-whisper 1.0+ の機能。0.0 = 無効、X.X = X.X 秒以上の無音区間が
    # 検知されたら文字起こしをスキップ。小音量録音で VAD が誤って通した
    # near-silent 区間からのハルシネーション抑止に効く。
    whisper_hallucination_silence_threshold: float = 0.0

    # 文字起こし後のハルシネーション後処理。faster-whisper の抑止スタックを
    # 通り抜けた「ご視聴ありがとうございました」や「うん うん うん..."」を
    # セグメント単位で drop マークに置換する。
    hallucination_drop_enabled: bool = True
    hallucination_drop_blacklist_path: Path | None = None
    hallucination_drop_token_streak: int = 5  # 同一トークン連続のしきい
    hallucination_drop_ngram_streak: int = 4  # N-gram 連続のしきい
    hallucination_drop_substr_streak: int = 6  # 空白なし部分文字列連続のしきい

    # Phase 3 前段: エンティティ名寄せ。Claude 抽出結果 (counterpart/topics/
    # locations) を既存 skeleton (vault/人物・トピック・場所/) に対して
    # 正規化する。敬称 strip + NFKC で重複 skeleton を防ぐ。
    entity_normalize_enabled: bool = True

    # Phase 4: PII マスキング。既存のテスト fixture を壊さないようデフォルト付き。
    pii_mask_enabled: bool = True
    pii_dict_path: Path | None = None
    pii_allowlist_path: Path | None = None

    # Phase 5: diarization と失敗追跡・Reminders 出力先
    diarize_enabled: bool = False
    hf_token: str = ""
    failed_dir_name: str = "_failed"
    reminders_enabled: bool = True

    @property
    def failed_dir(self) -> Path:
        return self.vault / self.failed_dir_name

    @property
    def reminders_dir(self) -> Path:
        return self.vault / "_reminders"

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
            whisper_vad_method=_get("WHISPER_VAD_METHOD", "pyannote"),
            whisper_condition_on_previous_text=_get_bool(
                "WHISPER_CONDITION_ON_PREVIOUS_TEXT", False
            ),
            whisper_temperatures=_get_float_tuple(
                "WHISPER_TEMPERATURES", (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
            ),
            whisper_compression_ratio_threshold=_get_float(
                "WHISPER_COMPRESSION_RATIO_THRESHOLD", 2.4
            ),
            whisper_log_prob_threshold=_get_float(
                "WHISPER_LOG_PROB_THRESHOLD", -1.0
            ),
            whisper_no_speech_threshold=_get_float(
                "WHISPER_NO_SPEECH_THRESHOLD", 0.6
            ),
            whisper_repetition_penalty=_get_float(
                "WHISPER_REPETITION_PENALTY", 1.1
            ),
            whisper_hallucination_silence_threshold=_get_float(
                "WHISPER_HALLUCINATION_SILENCE_THRESHOLD", 0.0
            ),
            hallucination_drop_enabled=_get_bool(
                "HALLUCINATION_DROP_ENABLED", True
            ),
            hallucination_drop_blacklist_path=(
                Path(_get("HALLUCINATION_DROP_BLACKLIST_PATH"))
                if _get("HALLUCINATION_DROP_BLACKLIST_PATH")
                else None
            ),
            hallucination_drop_token_streak=_get_int(
                "HALLUCINATION_DROP_TOKEN_STREAK", 5
            ),
            hallucination_drop_ngram_streak=_get_int(
                "HALLUCINATION_DROP_NGRAM_STREAK", 4
            ),
            hallucination_drop_substr_streak=_get_int(
                "HALLUCINATION_DROP_SUBSTR_STREAK", 6
            ),
            entity_normalize_enabled=_get_bool(
                "ENTITY_NORMALIZE_ENABLED", True
            ),
            file_stable_wait_s=_get_float("FILE_STABLE_WAIT_S", 5),
            file_stable_poll_s=_get_float("FILE_STABLE_POLL_S", 2),
            anthropic_api_key=_get("ANTHROPIC_API_KEY"),
            anthropic_model=_get("ANTHROPIC_MODEL", "claude-opus-4-7"),
            # default 16384 (応答 #16): 8192 だと 99 分音声で構造化失敗の実害あり。
            # ストリーミング API 経由なので上限を上げても 10 分タイムアウトは出ない。
            anthropic_max_tokens=_get_int("ANTHROPIC_MAX_TOKENS", 16384),
            anthropic_effort=_get("ANTHROPIC_EFFORT", "medium"),
            structuring_prompt_path=structuring_prompt_path,
            pii_mask_enabled=_get_bool("PII_MASK_ENABLED", True),
            pii_dict_path=pii_dict_path,
            pii_allowlist_path=pii_allowlist_path,
            diarize_enabled=_get_bool("DIARIZE_ENABLED", False),
            hf_token=_get("HF_TOKEN"),
            reminders_enabled=_get_bool("REMINDERS_ENABLED", True),
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


_DATE_FOLDER_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _try_audio_metadata_date(audio_path: Path) -> str | None:
    """MP4 ©day atom → "YYYY-MM-DD"。mutagen 無し or 取れなければ None。"""
    raw = _read_mp4_day(audio_path)
    if raw is None:
        return None
    dt = _parse_mp4_day(raw)
    return dt.strftime("%Y-%m-%d") if dt else None


def _try_audio_metadata_time(audio_path: Path) -> str | None:
    """MP4 ©day atom → "HH:MM:SS"。日付だけのフォーマットなら None。"""
    raw = _read_mp4_day(audio_path)
    if raw is None:
        return None
    dt = _parse_mp4_day(raw)
    if dt is None:
        return None
    # 日付だけ (HH:MM:SS = 00:00:00) は意味のある時刻ではないので None 扱い
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        # ただし元文字列に T が含まれていれば 00:00:00 を信用する
        if "T" in raw or " " in raw:
            return dt.strftime("%H:%M:%S")
        return None
    return dt.strftime("%H:%M:%S")


def _read_mp4_day(audio_path: Path) -> str | None:
    """MP4 ©day atom の生文字列を返す。mutagen 無し or 取れなければ None。"""
    try:
        from mutagen.mp4 import MP4
    except ImportError:
        return None
    try:
        f = MP4(str(audio_path))
        if not f.tags:
            return None
        raw = f.tags.get("\xa9day") or f.tags.get("\xa9DAY")
        if not raw:
            return None
        return str(raw[0]).strip()
    except Exception:
        return None


def _parse_mp4_day(raw: str) -> datetime | None:
    """ISO8601 風の MP4 ©day 文字列 → datetime。"""
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _try_mtime_date(audio_path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(
            audio_path.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d")
    except OSError:
        return None


def _try_mtime_time(audio_path: Path) -> str | None:
    """ファイル mtime → "HH:MM:SS" (UTC)。"""
    try:
        return datetime.fromtimestamp(
            audio_path.stat().st_mtime, tz=timezone.utc
        ).strftime("%H:%M:%S")
    except OSError:
        return None


_HHMMSS_RE = re.compile(r"\d{2}-\d{2}-\d{2}")


def canonical_date_folder(audio_path: Path) -> str:
    """audio_path から日付フォルダ名 (YYYY-MM-DD or "_undated") を決める。

    1. parent.name が YYYY-MM-DD パターンならそのまま使う(canonical layout)
    2. 違う(例: `inbox/` 直下に手動で置かれた `録音 138.m4a`)なら
       MP4 メタ → mtime → "_undated" の順でフォールバック

    これで `vault/録音/inbox/録音 138.md` のような変なフォルダを防ぎ、
    かつ既存の canonical な配置(YYYY-MM-DD/HH-MM-SS.m4a)は不変。"""
    parent = audio_path.parent.name
    if _DATE_FOLDER_RE.fullmatch(parent):
        return parent
    return (
        _try_audio_metadata_date(audio_path)
        or _try_mtime_date(audio_path)
        or "_undated"
    )


def canonical_time(audio_path: Path) -> str:
    """audio_path から HH:MM:SS 形式の時刻を決める(常に何か返す)。

    1. stem が `HH-MM-SS` パターンならそれを使う(JPR の canonical layout)
    2. MP4 メタ (©day の時刻部分) から取れればそれを使う
    3. ファイル mtime から取る
    4. 全部失敗したら "00:00:00"

    `test_5min` のような非 canonical stem でも、frontmatter の time フィールドが
    "" や "test_5min" にならず実用的な値が入る。Claude が時刻を空で返した
    ケースの最終フォールバックとしても使える。"""
    stem = audio_path.stem
    if _HHMMSS_RE.fullmatch(stem):
        return stem.replace("-", ":")
    return (
        _try_audio_metadata_time(audio_path)
        or _try_mtime_time(audio_path)
        or "00:00:00"
    )


def transcript_path_for(cfg: Config, audio_path: Path) -> Path:
    """audio: .../Just Press Record/2026-05-23/13-39-19.m4a
       → .../音声記憶/_transcripts/2026-05-23/13-39-19.json

    parent が非 canonical ならば canonical_date_folder() で推定する。"""
    date_folder = canonical_date_folder(audio_path)
    stem = audio_path.stem
    return cfg.transcripts_dir / date_folder / f"{stem}.json"


def skipped_marker_path_for(cfg: Config, audio_path: Path) -> Path:
    """同上、ただし .skipped 拡張子"""
    date_folder = canonical_date_folder(audio_path)
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
    date_folder = canonical_date_folder(audio_path)
    stem = audio_path.stem
    return cfg.notes_dir / date_folder / f"{stem}.md"


def is_structured(cfg: Config, audio_path: Path) -> bool:
    return note_path_for(cfg, audio_path).exists()
