from __future__ import annotations

import atexit
import logging
import os
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = PROJECT_ROOT / ".dana" / "logs"
LOG_FILE_NAME = "dana.log"


def _log_dir() -> Path:
    configured = os.getenv("DANA_LOG_DIR", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_LOG_DIR


def configure_file_logging() -> Path:
    """Mirror all Python logging records into Dana's persistent runtime log."""
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME

    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file:
            return log_file

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(process)d | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    logging.getLogger("dana").info("Dana file logging started: %s", log_file)
    return log_file


def append_stream_line(line: str, source: str = "stdout") -> None:
    """Persist terminal stdout/stderr lines that bypass Python logging."""
    text = line.rstrip("\n")
    if not text:
        return
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME
    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} | TERMINAL | {os.getpid()} | {source} | {text}\n")


class TeeStream:
    def __init__(self, stream, source: str) -> None:
        self._stream = stream
        self._source = source
        self._buffer = ""

    def write(self, data):
        result = self._stream.write(data)
        self._stream.flush()
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            append_stream_line(line, self._source)
        return result

    def flush(self):
        self._stream.flush()
        if self._buffer:
            append_stream_line(self._buffer, self._source)
            self._buffer = ""

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install_terminal_mirror() -> None:
    import sys

    if not isinstance(sys.stdout, TeeStream):
        sys.stdout = TeeStream(sys.stdout, "stdout")
    if not isinstance(sys.stderr, TeeStream):
        sys.stderr = TeeStream(sys.stderr, "stderr")
    atexit.register(sys.stdout.flush)
    atexit.register(sys.stderr.flush)
