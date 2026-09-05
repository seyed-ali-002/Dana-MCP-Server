from __future__ import annotations

import logging
import os
import socket
from pathlib import Path
import uvicorn
from uvicorn.supervisors.multiprocess import Multiprocess, Process

from .config import settings
from .terminal_ui import server_dashboard


def _mode() -> str:
    return settings.normalized_mode()


def _public_url() -> str | None:
    if not settings.public_host:
        return None
    if _mode() == "server":
        return f"https://{settings.public_host}{settings.mcp_path}"
    authority = settings.public_host
    if settings.public_port and settings.public_port not in (80, 443):
        authority = f"{authority}:{settings.public_port}"
    return f"https://{authority}/{settings.require_auth_token()}{settings.mcp_path}"


PID_FILE = Path(__file__).resolve().parents[1] / ".dana.pid"


def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


class DanaWorkerProcess(Process):
    def __init__(self, config, sockets, worker_number: int):
        self.worker_number = worker_number
        super().__init__(config, sockets)

    def target(self, sockets=None):
        os.environ["DANA_WORKER_NUMBER"] = str(self.worker_number)
        return super().target(sockets)


class DanaMultiprocess(Multiprocess):
    def _new_process(self, worker_number: int) -> DanaWorkerProcess:
        process = DanaWorkerProcess(self.config, self.sockets, worker_number)
        process.start()
        return process

    def init_processes(self) -> None:
        # Start workers strictly in numeric order. A worker is considered
        # online only after Uvicorn reports that its server is ready.
        # If one worker fails, continue with the next worker.
        for worker_number in range(1, self.processes_num + 1):
            if self.should_exit.is_set():
                return

            process = self._new_process(worker_number)
            if process.wait_until_ready(
                self.config.timeout_worker_healthcheck, self.should_exit
            ):
                self.processes.append(process)
                continue

            exit_code = process.exitcode
            if exit_code is None:
                process.terminate()
            process.join()
            logging.getLogger("dana").error(
                "Worker #%s failed to start%s; continuing with the next worker.",
                worker_number,
                f" (exit code {exit_code})" if exit_code is not None else "",
            )

    def restart_all(self) -> None:
        for index, old_process in enumerate(self.processes):
            if self.should_exit.is_set():
                return
            worker_number = index + 1
            new_process = self._new_process(worker_number)
            if not new_process.wait_until_ready(
                self.config.timeout_worker_healthcheck, self.should_exit
            ):
                new_process.kill()
                new_process.join()
                return
            old_process.terminate()
            old_process.join()
            self.processes[index] = new_process

    def handle_ttin(self) -> None:
        self.processes_num += 1
        self.processes.append(self._new_process(self.processes_num))


def run() -> None:
    mode = _mode()
    public_url = _public_url()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((settings.host, settings.port))
        probe.close()
    except OSError as exc:
        from .terminal_ui import startup_error

        startup_error(
            f"Port {settings.port} is already in use. Dana may already be running. Use ./stop to stop it."
        )
        return
    server_dashboard(settings, mode, public_url)

    # Uvicorn runs the configured number of application processes. Each process
    # gets its own stable Worker number/name and handles concurrent MCP clients.

    # Keep routine HTTP/session/access logging out of the terminal. Real server
    # errors remain available at ERROR level.
    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "mcp",
        "mcp.server",
        "mcp.server.streamable_http",
        "mcp.server.streamable_http_manager",
        "mcp.server.fastmcp.tools.tool_manager",
    ):
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers.clear()
        logger.propagate = False
    config = uvicorn.Config(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level="error",
        access_log=False,
        reload=False,
        # Uvicorn provides the actual process pool used by Dana Workers.
        workers=settings.normalized_workers(),
    )
    _write_pid()
    try:
        if config.workers > 1:
            sock = config.bind_socket()
            DanaMultiprocess(config, sockets=[sock]).run()
        else:
            uvicorn.Server(config).run()
    finally:
        _remove_pid()


if __name__ == "__main__":
    run()
