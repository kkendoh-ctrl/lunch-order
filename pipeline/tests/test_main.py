"""main.py CLI のテスト。特に --force / --force-all のフラグ挙動を検証。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

import main
from config import Config, note_path_for


def _mk_cfg(tmp_path: Path) -> Config:
    vault = tmp_path / "vault"
    return Config(
        jpr_inbox=tmp_path / "inbox",
        vault=vault,
        transcripts_dir=vault / "_transcripts",
        notes_dir=vault / "録音",
        skip_duration_s=10,
        skip_silence_ratio=0.95,
        skip_silence_db=-40,
        whisper_model="large-v3-turbo",
        whisper_device="cpu",
        whisper_compute_type="int8",
        whisper_language="ja",
        whisper_initial_prompt_path=None,
        whisper_align_enabled=False,
        file_stable_wait_s=5,
        file_stable_poll_s=2,
        anthropic_api_key="dummy",  # structuring_enabled=True にする
        anthropic_model="claude-opus-4-7",
        anthropic_max_tokens=8192,
        anthropic_effort="medium",
        structuring_prompt_path=None,
    )


def _stub_result() -> dict:
    return {
        "structured": {"contexts": []},
        "structuring_format": "tool_use",
        "model": "claude-opus-4-7",
        "structured_at": "2026-05-23T00:00:00Z",
        "pii_masked": 0,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


# -------------------- _run_structuring: force_note 挙動 --------------------


def test_run_structuring_skips_when_note_exists_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """既存ノートあり + force_note=False (デフォルト) → structure_already_done。"""
    cfg = _mk_cfg(tmp_path)
    audio = tmp_path / "inbox" / "2026-05-23" / "13-39-19.m4a"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"x")
    # 既存ノートを置く
    note = note_path_for(cfg, audio)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# existing\n", encoding="utf-8")

    called: dict = {"count": 0}

    def fake_structure_transcript(*args, **kwargs):
        called["count"] += 1
        return _stub_result()

    monkeypatch.setattr(
        main.structure, "structure_transcript", fake_structure_transcript
    )

    status = main._run_structuring({}, audio, cfg)
    assert status == "structure_already_done"
    assert called["count"] == 0  # structure_transcript は呼ばれない


def test_run_structuring_overwrites_when_force_note_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """既存ノートあり + force_note=True → 上書き再生成。"""
    cfg = _mk_cfg(tmp_path)
    audio = tmp_path / "inbox" / "2026-05-23" / "13-39-19.m4a"
    audio.parent.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(b"x")
    note = note_path_for(cfg, audio)
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("# old\n", encoding="utf-8")

    monkeypatch.setattr(
        main.structure, "structure_transcript", lambda *a, **kw: _stub_result()
    )
    monkeypatch.setattr(
        main.note_writer, "render_note", lambda *a, **kw: "# new note\n"
    )
    monkeypatch.setattr(
        main.aggregator,
        "aggregate_after_note",
        lambda *a, **kw: {
            "skeletons": {"人物": [], "トピック": [], "場所": []},
            "daily": True,
        },
    )
    monkeypatch.setattr(
        main.entity_normalizer,
        "normalize_structured",
        lambda s, c: s,
    )

    status = main._run_structuring({}, audio, cfg, force_note=True)
    assert "structure_already_done" not in status
    assert "structured(" in status
    # ノートが新内容で上書きされている
    assert note.read_text(encoding="utf-8") == "# new note\n"


# -------------------- CLI --force-all フラグ --------------------


def test_test_command_has_force_all_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main.cli, ["test", "--help"])
    assert result.exit_code == 0
    assert "--force-all" in result.output
    assert "ノート" in result.output  # 日本語ヘルプテキスト確認


def test_batch_command_has_force_all_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main.cli, ["batch", "--help"])
    assert result.exit_code == 0
    assert "--force-all" in result.output


def test_retry_command_has_force_all_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main.cli, ["retry", "--help"])
    assert result.exit_code == 0
    assert "--force-all" in result.output


def test_test_command_force_all_implies_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force-all で _process_one が force=True force_note=True で呼ばれる。"""
    cfg = _mk_cfg(tmp_path)
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"x")

    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: cfg))

    captured: dict = {}

    def fake_process_one(p, c, force=False, force_note=False):
        captured["force"] = force
        captured["force_note"] = force_note
        return "ok"

    monkeypatch.setattr(main, "_process_one", fake_process_one)

    runner = CliRunner()
    result = runner.invoke(main.cli, ["test", str(audio), "--force-all"])
    assert result.exit_code == 0, result.output
    assert captured == {"force": True, "force_note": True}


def test_test_command_force_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--force だけなら force=True force_note=False(既存ノート保護)。"""
    cfg = _mk_cfg(tmp_path)
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"x")

    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: cfg))

    captured: dict = {}

    def fake_process_one(p, c, force=False, force_note=False):
        captured["force"] = force
        captured["force_note"] = force_note
        return "ok"

    monkeypatch.setattr(main, "_process_one", fake_process_one)

    runner = CliRunner()
    result = runner.invoke(main.cli, ["test", str(audio), "--force"])
    assert result.exit_code == 0, result.output
    assert captured == {"force": True, "force_note": False}
