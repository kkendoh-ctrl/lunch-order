"""Phase 1+2+3 CLI: info / test / batch / watch / structure / aggregate。

watch / batch では Phase 1 (WhisperX) → Phase 2 (Claude 構造化 → Vault ノート)
→ Phase 3 (エンティティ skeleton + 日次ノート + 一覧再生成) を自動連鎖する。
ANTHROPIC_API_KEY 未設定なら Phase 2/3 はスキップし Phase 1 だけで止まる。
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

import click

# PowerShell の Tee-Object でログを取ると、Python のデフォルトのブロック
# バッファリングのせいで進捗が長時間止まって見える。改行ごとに flush する
# ことで `python main.py ... | Tee-Object out.log` でもリアルタイムに出る。
# 環境変数 PYTHONUNBUFFERED=1 や `python -u` を要求するより、ここで明示する
# 方が運用上事故が少ない(WhisperX/tqdm 等は stderr 側を使う)。
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    pass  # 古い Python(< 3.7)向けセーフガード。実運用上は通らない

import aggregator
import entity_normalizer
import failure_tracker
import filter as audio_filter
import importer
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
    transcript: dict, audio_path: Path, cfg: Config, force_note: bool = False
) -> str:
    """transcript dict → Claude → Vault にノート生成。ステータス文字列を返す。

    force_note=True で既存ノートがあっても上書き再生成する(--force-all 経由)。"""
    if not cfg.structuring_enabled:
        return "structure_skipped(ANTHROPIC_API_KEY未設定)"
    if not force_note and is_structured(cfg, audio_path):
        return "structure_already_done"

    try:
        result = structure.structure_transcript(transcript, audio_path, cfg)
    except Exception as e:
        traceback.print_exc()
        return f"structure_error: {e}"

    # エンティティ名寄せ: 既存 skeleton 名と一致するように counterpart/topics/
    # locations を canonical 化。note_writer の wiki link と aggregator の
    # skeleton 生成が同じ正規化名を見るようにする。
    if cfg.entity_normalize_enabled:
        try:
            result["structured"] = entity_normalizer.normalize_structured(
                result.get("structured", {}) or {}, cfg
            )
        except Exception as e:
            # 名寄せ失敗は致命的でない(原本のまま続行)
            print(f"  [warn] entity normalize failed: {e}")

    try:
        body = note_writer.render_note(transcript, result, audio_path, cfg)
        out = note_path_for(cfg, audio_path)
        note_writer.save_note(body, out)
        n_ctx = len(result.get("structured", {}).get("contexts", []) or [])
        usage = result.get("usage", {})
        fmt_tag = (
            "/markdown_fallback"
            if result.get("structuring_format") == "markdown_fallback"
            else ""
        )
        structure_msg = (
            f"structured(ctx={n_ctx}{fmt_tag}, in={usage.get('input_tokens', 0)}, "
            f"out={usage.get('output_tokens', 0)}, "
            f"cache_read={usage.get('cache_read_input_tokens', 0)}, "
            f"masked={result.get('pii_masked', 0)})"
        )
    except Exception as e:
        traceback.print_exc()
        return f"note_write_error: {e}"

    try:
        summary = aggregator.aggregate_after_note(
            result.get("structured", {}) or {}, audio_path, cfg
        )
        skels = summary["skeletons"]
        new_count = sum(len(v) for v in skels.values())
        agg_msg = (
            f"aggregated(skeleton={new_count}, daily={'OK' if summary['daily'] else 'skip'})"
        )
    except Exception as e:
        traceback.print_exc()
        agg_msg = f"aggregate_error: {e}"

    return f"{structure_msg} / {agg_msg}"


def _process_one(
    audio_path: Path, cfg: Config, force: bool = False, force_note: bool = False
) -> str:
    """1ファイルを処理して、status string を返す。失敗マーカーの管理も。"""
    status = _process_one_inner(
        audio_path, cfg, force=force, force_note=force_note
    )
    if failure_tracker.status_indicates_failure(status):
        phase = failure_tracker.classify_phase(status)
        failure_tracker.record_failure(cfg, audio_path, phase, status)
    elif not status.startswith("skipped"):
        # skipped は失敗ではないので消さない(skipped マーカーは別系統)
        failure_tracker.clear_failure(cfg, audio_path)
    return status


def _process_one_inner(
    audio_path: Path, cfg: Config, force: bool = False, force_note: bool = False
) -> str:
    """1ファイルを処理(filter → WhisperX → Claude → ノート → 集約)。
    返り値はステータス文字列(ログ用)。

    force: Phase 1 (WhisperX 文字起こし) を再実行
    force_note: 既存ノートを上書き再生成 (Phase 2 を強制再実行)。
                通常は --force-all 経由で True/True 同時セット。"""
    if not force and is_already_processed(cfg, audio_path):
        # Phase 1 は終わっているが Phase 2 がまだ(or force_note)なら走らせる
        if (
            cfg.structuring_enabled
            and transcript_path_for(cfg, audio_path).exists()
            and (force_note or not is_structured(cfg, audio_path))
        ):
            try:
                transcript = json.loads(
                    transcript_path_for(cfg, audio_path).read_text(encoding="utf-8")
                )
            except Exception as e:
                return f"transcript_read_error: {e}"
            return _run_structuring(
                transcript, audio_path, cfg, force_note=force_note
            )
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
        drops = result.get("hallucination_drops", 0)
        drop_tag = f", drop={drops}" if drops else ""
        transcribe_status = (
            f"transcribed({fr.duration_s:.1f}s, {len(result['segments'])} segs{drop_tag})"
        )
    except Exception as e:
        traceback.print_exc()
        return f"transcribe_error: {e}"

    structure_status = _run_structuring(
        result, audio_path, cfg, force_note=force_note
    )
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
    click.echo(f"PII_MASK_ENABLED: {cfg.pii_mask_enabled}")
    click.echo(f"PII_DICT_PATH: {cfg.pii_dict_path}")
    if cfg.pii_dict_path:
        click.echo(f"  exists: {cfg.pii_dict_path.exists()}")

    # 失敗マーカー
    failed_count = len(failure_tracker.list_failures(cfg))
    if failed_count:
        click.echo("")
        click.echo(
            f"⚠ 失敗マーカー: {failed_count} 件 "
            f"(`python main.py failed` で詳細, `retry` で再実行)"
        )

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
@click.option("--force", is_flag=True, help="Phase 1 (文字起こし) を再実行")
@click.option(
    "--force-all",
    is_flag=True,
    help="--force に加えて既存ノート (Phase 2 結果) も上書き再生成",
)
def test(audio_path: Path, force: bool, force_all: bool) -> None:
    """単一ファイルを処理(動作確認用)。"""
    cfg = Config.load()
    if force_all:
        force = True
    click.echo(f"処理中: {audio_path}")
    status = _process_one(audio_path, cfg, force=force, force_note=force_all)
    click.echo(f"結果: {status}")


@cli.command()
@click.option("--force", is_flag=True, help="Phase 1 (文字起こし) を再実行")
@click.option(
    "--force-all",
    is_flag=True,
    help="--force に加えて既存ノート (Phase 2 結果) も上書き再生成",
)
def batch(force: bool, force_all: bool) -> None:
    """未処理ファイルを全部処理して終了。"""
    cfg = Config.load()
    if force_all:
        force = True
    files = watcher.iter_audio_files(cfg.jpr_inbox)
    if force or force_all:
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
        status = _process_one(f, cfg, force=force, force_note=force_all)
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
@click.option(
    "--clean-stale",
    is_flag=True,
    help="参照先の音声ファイルが消えてるマーカーを削除",
)
def failed(clean_stale: bool) -> None:
    """失敗マーカー (_failed/) を phase 別に表示。エラー内容に
    既知パターンがあれば対処ヒントも添える。"""
    cfg = Config.load()

    if clean_stale:
        removed = failure_tracker.cleanup_stale(cfg)
        if not removed:
            click.echo("消失マーカーなし。")
        else:
            click.echo(f"消失マーカーを {len(removed)} 件削除:")
            for p in removed:
                click.echo(f"  - {p}")
        return

    fails = failure_tracker.list_failures(cfg)
    if not fails:
        click.echo("失敗マーカーなし。")
        return

    from collections import defaultdict

    by_phase: dict[str, list] = defaultdict(list)
    for f in fails:
        by_phase[f.phase].append(f)

    click.echo(f"{len(fails)} 件の失敗マーカー (phase 別):")
    for phase in sorted(by_phase.keys()):
        items = by_phase[phase]
        click.echo("")
        click.echo(f"[{phase}] {len(items)} 件:")
        for f in items:
            stale_mark = "" if f.audio_path.exists() else "  ⚠ 元ファイル消失"
            click.echo(
                f"  {f.audio_path.name}  試行 {f.attempt_count} 回  "
                f"最終 {f.last_attempted_at}{stale_mark}"
            )
            click.echo(f"    error: {f.error[:200]}")
            hint = failure_tracker.suggest_hint(f.error)
            if hint:
                click.echo(f"    hint:  {hint}")


@cli.command()
@click.argument("audio_path", type=click.Path(path_type=Path), required=False)
@click.option(
    "--force-all",
    is_flag=True,
    help="既存ノートも上書き再生成(--force 込み)",
)
def retry(audio_path: Path | None, force_all: bool) -> None:
    """失敗マーカーのあるファイルを再実行。引数なしで全件、引数で個別。"""
    cfg = Config.load()
    if audio_path:
        targets = [audio_path]
    else:
        targets = [f.audio_path for f in failure_tracker.list_failures(cfg)]
    if not targets:
        click.echo("再実行対象なし。")
        return
    click.echo(f"再実行対象: {len(targets)} 件")
    for i, p in enumerate(targets, 1):
        if not p.exists():
            click.echo(f"[{i}/{len(targets)}] {p} (元ファイルが消えています、skip)")
            continue
        click.echo(f"[{i}/{len(targets)}] {p}")
        # 通常は force=False/force_note=False で動く。Phase 1 未完なら最初から、
        # Phase 2 未完なら Phase 2 から自動で続きを処理する既存ロジックに任せる。
        # --force-all なら全段強制再実行。
        status = _process_one(
            p, cfg, force=force_all, force_note=force_all
        )
        click.echo(f"  → {status}")


_TEMPLATE_DIR = Path(__file__).parent / "templates"

_VAULT_DIRS = [
    "録音",
    "日次",
    "人物",
    "トピック",
    "場所",
    "一覧",
    "_プロンプト",
    "_テンプレート",
    "_transcripts",
    "_failed",
    "_reminders",
]

_TEMPLATES_TO_COPY = [
    ("claude-structuring.md", "_プロンプト/claude-structuring.md"),
    ("whisper-initial-prompt.txt", "_プロンプト/whisper-initial-prompt.txt"),
    ("録音ノート.md", "_テンプレート/録音ノート.md"),
]


@cli.command("import")
@click.argument(
    "source_dir",
    type=click.Path(exists=True, path_type=Path, file_okay=False),
)
def import_cmd(source_dir: Path) -> None:
    """任意フォルダの音声を inbox の YYYY-MM-DD/HH-MM-SS.m4a 形式にコピー。

    iOS 純正ボイスメモ等から書き出した過去録音を一括取込みする用。
    元ファイルは触らない。日時推定は (1) 音声メタの ©day → (2) mtime の
    順。両方失敗したら <inbox>/_undated/ に元のファイル名で隔離。
    取込み後は `python main.py batch` で全件処理。"""
    cfg = Config.load()
    if not cfg.jpr_inbox.exists():
        cfg.jpr_inbox.mkdir(parents=True)
    click.echo(f"取込み元: {source_dir}")
    click.echo(f"取込み先: {cfg.jpr_inbox}")
    click.echo("")
    results = importer.import_directory(source_dir, cfg)
    if not results:
        click.echo("対象ファイル無し(.m4a/.mp3/.wav/.mp4)")
        return

    by_source: dict[str, int] = {}
    for r in results:
        by_source[r.date_source] = by_source.get(r.date_source, 0) + 1
        if r.date_source == "error":
            click.echo(f"  [error] {r.src.name}: {r.error}")

    click.echo(f"\n{len(results)} 件処理:")
    for k in ("metadata", "mtime", "undated", "error"):
        v = by_source.get(k, 0)
        if v:
            click.echo(f"  {k}: {v} 件")
    if by_source.get("undated"):
        click.echo(
            f"\n  [warn] _undated/ のファイルは batch で処理されるが、"
            f"日付フォルダが '_undated' になる。"
        )
        click.echo(
            f"  正しい日付が分かるならば mv で <inbox>/YYYY-MM-DD/ に動かしてから batch。"
        )
    click.echo("")
    click.echo("次は: python main.py batch")


@cli.command()
@click.option("--force", is_flag=True, help="既存ファイルを上書き")
def init(force: bool) -> None:
    """Vault のフォルダ構造とプロンプトテンプレートを bootstrap する。

    既存ファイルは触らない(--force で上書き)。
    新規セットアップ時に1回だけ実行する想定。"""
    cfg = Config.load()
    if not cfg.vault.exists():
        cfg.vault.mkdir(parents=True)
        click.echo(f"Vault 作成: {cfg.vault}")

    for d in _VAULT_DIRS:
        target = cfg.vault / d
        if target.exists():
            click.echo(f"  既存: {d}/")
        else:
            target.mkdir(parents=True)
            click.echo(f"  作成: {d}/")

    click.echo("")
    click.echo(f"プロンプトテンプレートをコピー (from {_TEMPLATE_DIR})")
    for src_name, dest_rel in _TEMPLATES_TO_COPY:
        src = _TEMPLATE_DIR / src_name
        dest = cfg.vault / dest_rel
        if not src.exists():
            click.echo(f"  [warn] テンプレ無し: {src}")
            continue
        if dest.exists() and not force:
            click.echo(f"  既存(skip): {dest_rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        click.echo(f"  {'上書き' if force and dest.exists() else 'コピー'}: {dest_rel}")

    click.echo("")
    click.echo("次のステップ:")
    click.echo(f"  1. {cfg.vault / '_プロンプト' / 'whisper-initial-prompt.txt'} に固有名詞を追記")
    click.echo(f"  2. {cfg.vault / '_プロンプト' / 'claude-structuring.md'} を必要に応じて編集")
    click.echo(f"  3. python main.py info で設定値を確認")
    click.echo(f"  4. python main.py watch で常駐開始")


@cli.command()
def aggregate() -> None:
    """既存ノートから skeleton / 日次 / 一覧 を全部再生成(Phase 3 単体実行)。

    Phase 2 完了後の集約処理は通常 watch/batch/test が自動連鎖するが、
    手動で frontmatter を直したあとなど、明示的に再生成したい場合はこれ。"""
    cfg = Config.load()
    if not cfg.vault.exists():
        raise click.ClickException(f"VAULT_PATH が存在しない: {cfg.vault}")
    click.echo(f"Vault スキャン: {cfg.vault}")
    summary = aggregator.aggregate_full(cfg)
    click.echo(f"  録音ノート: {summary['scanned']} 件")
    skels = summary["skeletons"]
    click.echo(
        f"  skeleton 新規: 人物 {len(skels['人物'])} / "
        f"トピック {len(skels['トピック'])} / 場所 {len(skels['場所'])}"
    )
    click.echo(f"  日次ノート: {len(summary['dailies'])} 本")
    click.echo(f"  一覧: {summary['indexes']['todo']}")
    click.echo(f"  一覧: {summary['indexes']['important']}")


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
