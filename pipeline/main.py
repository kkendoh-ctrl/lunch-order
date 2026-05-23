"""Phase 1+2 CLI: info / test / batch / watch / structure。

watch / batch では Phase 1 (WhisperX) → Phase 2 (Claude 構造化 → Vault ノート)
を自動連鎖する。ANTHROPIC_API_KEY 未設定なら Phase 2 はスキップし
Phase 1 だけで止まる(_transcripts/ に JSON が残る)。
"""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import click

import filter as audio_filter
import note_writer
import structure
import transcribe as tx
import watcher
from config import (
    Config,
    is_already_processed,
    is_structured,
    note_path_for,
    skipped_marker_path_for,
    transcript_path_for,
)


def _run_structuring(
    transcript: dict, audio_path: Path, cfg: Config
) -> str:
    """transcript dict → Claude → Vault にノート生成。ステータス文字列を返す。"""
    if not cfg.structuring_enabled:
        return "structure_skipped(ANTHROPIC_API_KEY未設定)"
    if is_structured(cfg, audio_path):
        return "structure_already_done"

    try:
        result = structure.structure_transcript(transcript, audio_path, cfg)
    except Exception as e:
        traceback.print_exc()
        return f"structure_error: {e}"

    try:
        body = note_writer.render_note(transcript, result, audio_path, cfg)
        out = note_path_for(cfg, audio_path)
        note_writer.save_note(body, out)
        n_ctx = len(result.get("structured", {}).get("contexts", []) or [])
        usage = result.get("usage", {})
        return (
            f"structured(ctx={n_ctx}, in={usage.get('input_tokens', 0)}, "
            f"out={usage.get('output_tokens', 0)}, "
            f"cache_read={usage.get('cache_read_input_tokens', 0)})"
        )
    except Exception as e:
        traceback.print_exc()
        return f"note_write_error: {e}"


def _process_one(audio_path: Path, cfg: Config, force: bool = False) -> str:
    """1ファイルを処理(filter → WhisperX → Claude → ノート)。
    返り値はステータス文字列(ログ用)。"""
    if not force and is_already_processed(cfg, audio_path):
        # Phase 1 は終わっているが Phase 2 がまだなら走らせる
        if (
            cfg.structuring_enabled
            and transcript_path_for(cfg, audio_path).exists()
            and not is_structured(cfg, audio_path)
        ):
            try:
                transcript = json.loads(
                    transcript_path_for(cfg, audio_path).read_text(encoding="utf-8")
                )
            except Exception as e:
                return f"transcript_read_error: {e}"
            return _run_structuring(transcript, audio_path, cfg)
        return "already_processed"

    try:
        fr = audio_filter.evaluate(audio_path, cfg)
    except Exception as e:
        return f"filter_error: {e}"

    if fr.skip:
        marker = skipped_marker_path_for(cfg, audio_path)
        tx.save_skipped_marker(marker, fr.reason, fr.duration_s)
        return f"skipped({fr.reason}, {fr.duration_s:.1f}s)"

    try:
        result = tx.transcribe(audio_path, cfg)
        out = transcript_path_for(cfg, audio_path)
        tx.save_transcript(result, out)
        transcribe_status = f"transcribed({fr.duration_s:.1f}s, {len(result['segments'])} segs)"
    except Exception as e:
        traceback.print_exc()
        return f"transcribe_error: {e}"

    structure_status = _run_structuring(result, audio_path, cfg)
    return f"{transcribe_status} / {structure_status}"


@click.group()
def cli() -> None:
    """音声記憶パイプライン Phase 1+2: WhisperX + Claude 構造化。"""


@cli.command()
def info() -> None:
    """設定値と環境を表示。動作前のヘルスチェック。"""
    cfg = Config.load()
    click.echo(f"JPR_INBOX_PATH: {cfg.jpr_inbox}")
    click.echo(f"  exists: {cfg.jpr_inbox.exists()}")
    click.echo(f"VAULT_PATH: {cfg.vault}")
    click.echo(f"  exists: {cfg.vault.exists()}")
    click.echo(f"TRANSCRIPTS_DIR: {cfg.transcripts_dir}")
    click.echo(f"NOTES_DIR: {cfg.notes_dir}")
    click.echo(f"WHISPER_MODEL: {cfg.whisper_model}")
    click.echo(f"WHISPER_DEVICE: {cfg.whisper_device}")
    click.echo(f"WHISPER_COMPUTE_TYPE: {cfg.whisper_compute_type}")
    click.echo(f"WHISPER_LANGUAGE: {cfg.whisper_language}")
    click.echo(f"INITIAL_PROMPT_PATH: {cfg.whisper_initial_prompt_path}")
    if cfg.whisper_initial_prompt_path:
        click.echo(f"  exists: {cfg.whisper_initial_prompt_path.exists()}")
    click.echo(f"ALIGN_ENABLED: {cfg.whisper_align_enabled}")
    click.echo(f"SKIP_DURATION_S: {cfg.skip_duration_s}")
    click.echo(f"SKIP_SILENCE_RATIO: {cfg.skip_silence_ratio}")
    click.echo("")
    click.echo(f"ANTHROPIC_MODEL: {cfg.anthropic_model}")
    click.echo(f"ANTHROPIC_EFFORT: {cfg.anthropic_effort}")
    click.echo(f"ANTHROPIC_MAX_TOKENS: {cfg.anthropic_max_tokens}")
    click.echo(f"STRUCTURING_ENABLED: {cfg.structuring_enabled}")
    click.echo(f"STRUCTURING_PROMPT_PATH: {cfg.structuring_prompt_path}")
    if cfg.structuring_prompt_path:
        click.echo(f"  exists: {cfg.structuring_prompt_path.exists()}")

    files = watcher.iter_audio_files(cfg.jpr_inbox)
    click.echo(f"\n見つかった音声ファイル: {len(files)}")
    pending = [f for f in files if not is_already_processed(cfg, f)]
    click.echo(f"Phase 1 未処理: {len(pending)}")
    if cfg.structuring_enabled:
        pending_p2 = [
            f
            for f in files
            if transcript_path_for(cfg, f).exists() and not is_structured(cfg, f)
        ]
        click.echo(f"Phase 2 未処理: {len(pending_p2)}")
    for f in pending[:10]:
        click.echo(f"  - {f.relative_to(cfg.jpr_inbox)}")
    if len(pending) > 10:
        click.echo(f"  ... and {len(pending) - 10} more")


@cli.command()
@click.argument("audio_path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="既に処理済みでも再実行")
def test(audio_path: Path, force: bool) -> None:
    """単一ファイルを処理(動作確認用)。"""
    cfg = Config.load()
    click.echo(f"処理中: {audio_path}")
    status = _process_one(audio_path, cfg, force=force)
    click.echo(f"結果: {status}")


@cli.command()
@click.option("--force", is_flag=True, help="既に処理済みでも再実行")
def batch(force: bool) -> None:
    """未処理ファイルを全部処理して終了。"""
    cfg = Config.load()
    files = watcher.iter_audio_files(cfg.jpr_inbox)
    if force:
        pending = files
    else:
        pending = []
        for f in files:
            # Phase 1 未処理、または Phase 2 未処理
            if not is_already_processed(cfg, f):
                pending.append(f)
            elif (
                cfg.structuring_enabled
                and transcript_path_for(cfg, f).exists()
                and not is_structured(cfg, f)
            ):
                pending.append(f)
    click.echo(f"対象: {len(pending)} 件 / 全 {len(files)} 件")
    for i, f in enumerate(pending, 1):
        click.echo(f"[{i}/{len(pending)}] {f.relative_to(cfg.jpr_inbox)}")
        status = _process_one(f, cfg, force=force)
        click.echo(f"  → {status}")


@cli.command()
@click.argument("transcript_path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True, help="既存のノートを上書き")
def structure_cmd(transcript_path: Path, force: bool) -> None:
    """transcript JSON を単体で構造化 → ノート生成(デバッグ用)。"""
    cfg = Config.load()
    if not cfg.structuring_enabled:
        raise click.ClickException("ANTHROPIC_API_KEY 未設定")

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    # transcript の audio_path から元の m4a パスを復元
    audio_str = transcript.get("audio_path")
    if not audio_str:
        raise click.ClickException(
            "transcript JSON に audio_path フィールドが無い"
        )
    audio_path = Path(audio_str)

    if not force and is_structured(cfg, audio_path):
        click.echo(f"既存ノートあり: {note_path_for(cfg, audio_path)}")
        click.echo("--force で上書き")
        return

    status = _run_structuring(transcript, audio_path, cfg)
    click.echo(f"結果: {status}")
    click.echo(f"出力先: {note_path_for(cfg, audio_path)}")


# Click のサブコマンド名は kebab-case 推奨
cli.add_command(structure_cmd, name="structure")


@cli.command()
def watch() -> None:
    """watchdog で常駐、新規ファイルを順次処理。Ctrl+C で停止。"""
    cfg = Config.load()
    click.echo(f"監視開始: {cfg.jpr_inbox}")
    if not cfg.jpr_inbox.exists():
        raise click.ClickException(f"JPR_INBOX_PATH が存在しない: {cfg.jpr_inbox}")
    if cfg.structuring_enabled:
        click.echo(f"Phase 2 構造化: 有効 ({cfg.anthropic_model})")
    else:
        click.echo("Phase 2 構造化: 無効 (ANTHROPIC_API_KEY 未設定)")

    # 起動時に未処理を一気に処理
    files = watcher.iter_audio_files(cfg.jpr_inbox)
    pending = []
    for f in files:
        if not is_already_processed(cfg, f):
            pending.append(f)
        elif (
            cfg.structuring_enabled
            and transcript_path_for(cfg, f).exists()
            and not is_structured(cfg, f)
        ):
            pending.append(f)
    click.echo(f"起動時バックログ: {len(pending)} 件")
    for f in pending:
        click.echo(f"  処理: {f.relative_to(cfg.jpr_inbox)}")
        status = _process_one(f, cfg)
        click.echo(f"    → {status}")

    def on_file(path: Path) -> None:
        if is_already_processed(cfg, path) and (
            not cfg.structuring_enabled or is_structured(cfg, path)
        ):
            return
        click.echo(f"\n新規検知: {path.relative_to(cfg.jpr_inbox) if path.is_relative_to(cfg.jpr_inbox) else path}")
        click.echo(f"  ファイル安定待ち...")
        if not watcher.wait_for_stable(path, cfg):
            click.echo(f"  → タイムアウトまたはファイル消失")
            return
        status = _process_one(path, cfg)
        click.echo(f"  → {status}")

    obs = watcher.watch(cfg.jpr_inbox, on_file)
    click.echo("待機中(Ctrl+C で終了)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\n停止中...")
        obs.stop()
        obs.join()
        click.echo("停止しました")


if __name__ == "__main__":
    cli()
