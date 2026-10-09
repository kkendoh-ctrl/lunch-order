"""Phase 1 CLI: info / test / batch / watch."""
from __future__ import annotations

import time
import traceback
from pathlib import Path

import click

import filter as audio_filter
import transcribe as tx
import watcher
from config import (
    Config,
    is_already_processed,
    skipped_marker_path_for,
    transcript_path_for,
)


def _process_one(audio_path: Path, cfg: Config, force: bool = False) -> str:
    """1ファイルを処理。返り値はステータス文字列(ログ用)。"""
    if not force and is_already_processed(cfg, audio_path):
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
        return f"ok({fr.duration_s:.1f}s, {len(result['segments'])} segs)"
    except Exception as e:
        traceback.print_exc()
        return f"transcribe_error: {e}"


@click.group()
def cli() -> None:
    """音声記憶パイプライン Phase 1: WhisperX 文字起こし。"""


@cli.command()
def info() -> None:
    """設定値と環境を表示。動作前のヘルスチェック。"""
    cfg = Config.load()
    click.echo(f"JPR_INBOX_PATH: {cfg.jpr_inbox}")
    click.echo(f"  exists: {cfg.jpr_inbox.exists()}")
    click.echo(f"VAULT_PATH: {cfg.vault}")
    click.echo(f"  exists: {cfg.vault.exists()}")
    click.echo(f"TRANSCRIPTS_DIR: {cfg.transcripts_dir}")
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

    files = watcher.iter_audio_files(cfg.jpr_inbox)
    click.echo(f"\n見つかった音声ファイル: {len(files)}")
    pending = [f for f in files if not is_already_processed(cfg, f)]
    click.echo(f"未処理: {len(pending)}")
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
    pending = files if force else [f for f in files if not is_already_processed(cfg, f)]
    click.echo(f"対象: {len(pending)} 件 / 全 {len(files)} 件")
    for i, f in enumerate(pending, 1):
        click.echo(f"[{i}/{len(pending)}] {f.relative_to(cfg.jpr_inbox)}")
        status = _process_one(f, cfg, force=force)
        click.echo(f"  → {status}")


@cli.command()
def watch() -> None:
    """watchdog で常駐、新規ファイルを順次処理。Ctrl+C で停止。"""
    cfg = Config.load()
    click.echo(f"監視開始: {cfg.jpr_inbox}")
    if not cfg.jpr_inbox.exists():
        raise click.ClickException(f"JPR_INBOX_PATH が存在しない: {cfg.jpr_inbox}")

    # 起動時に未処理を一気に処理
    files = watcher.iter_audio_files(cfg.jpr_inbox)
    pending = [f for f in files if not is_already_processed(cfg, f)]
    click.echo(f"起動時バックログ: {len(pending)} 件")
    for f in pending:
        click.echo(f"  処理: {f.relative_to(cfg.jpr_inbox)}")
        status = _process_one(f, cfg)
        click.echo(f"    → {status}")

    def on_file(path: Path) -> None:
        if is_already_processed(cfg, path):
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
