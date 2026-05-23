"""ファイル監視: iCloud Drive のダウンロード完了を待ってから処理に回す。"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config import Config

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac"}


def wait_for_stable(path: Path, cfg: Config, timeout_s: float = 300) -> bool:
    """ファイルサイズが file_stable_wait_s 秒変化しなければ確定。
    True: 安定した / False: タイムアウト or ファイル消失"""
    last_size = -1
    stable_since = None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if not path.exists():
            return False
        size = path.stat().st_size
        now = time.time()
        if size == last_size and size > 0:
            if stable_since is None:
                stable_since = now
            if now - stable_since >= cfg.file_stable_wait_s:
                return True
        else:
            stable_since = None
            last_size = size
        time.sleep(cfg.file_stable_poll_s)
    return False


def iter_audio_files(root: Path) -> list[Path]:
    """JPR フォルダ配下の .m4a を全部列挙(日付フォルダの中)"""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in AUDIO_EXTS)


class _Handler(FileSystemEventHandler):
    def __init__(self, on_file: Callable[[Path], None]):
        self.on_file = on_file

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix.lower() in AUDIO_EXTS:
            self.on_file(p)

    def on_modified(self, event: FileSystemEvent) -> None:
        # iCloud のダウンロード完了は modified イベントとして来る場合がある
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.suffix.lower() in AUDIO_EXTS:
            self.on_file(p)


def watch(root: Path, on_file: Callable[[Path], None]) -> Observer:
    """非ブロッキングで監視開始。Observer を返す。呼び出し側で .join() してください。"""
    observer = Observer()
    observer.schedule(_Handler(on_file), str(root), recursive=True)
    observer.start()
    return observer
