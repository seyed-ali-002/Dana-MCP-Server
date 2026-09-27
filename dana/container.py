from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.yml"
PROJECT_NAME = os.getenv("DANA_COMPOSE_PROJECT", "dana")


class DockerUnavailable(RuntimeError):
    pass


def docker_command() -> list[str]:
    if not shutil.which("docker"):
        raise DockerUnavailable(
            "Docker is not installed. Install Docker Desktop or Docker Engine, "
            "then run 'dana install'."
        )
    result = subprocess.run(
        ["docker", "compose", "version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise DockerUnavailable(
            "Docker Compose v2 is unavailable"
            + (f": {detail}" if detail else ".")
        )
    return ["docker", "compose"]


def compose_args(*args: str) -> list[str]:
    return [
        *docker_command(),
        "-p",
        PROJECT_NAME,
        "-f",
        str(COMPOSE_FILE),
        *args,
    ]


def compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        compose_args(*args),
        cwd=ROOT,
        text=True,
        check=check,
    )


def is_available() -> bool:
    try:
        docker_command()
    except (DockerUnavailable, OSError):
        return False
    return True


def install() -> None:
    # Pull/build is deliberately separated from start so failures are explicit.
    compose("build", "--pull")


def start() -> None:
    compose("up", "-d", "--remove-orphans")


def stop() -> None:
    compose("down")


def restart() -> None:
    compose("up", "-d", "--force-recreate", "--remove-orphans")


def update() -> None:
    compose("build", "--pull")
    compose("up", "-d", "--remove-orphans")


def logs(follow: bool = False, tail: int = 200) -> None:
    args = ["logs", "--tail", str(max(1, min(tail, 5000)))]
    if follow:
        args.append("-f")
    compose(*args)


def status() -> None:
    compose("ps")


def uninstall(remove_data: bool = False) -> None:
    args = ["down", "--remove-orphans"]
    if remove_data:
        args.append("--volumes")
    compose(*args)


def health_url() -> str:
    return "http://127.0.0.1:8765/health"
