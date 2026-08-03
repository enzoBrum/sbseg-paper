import os
import signal
import socket
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import DEVNULL

import requests

_LIBRARY_DIR = Path(__file__).parent


class LibraryVerifier(ABC):
    name: str
    version: str | None = None
    port: int = 8080
    startup_timeout: int = 60

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    @property
    @abstractmethod
    def command(self) -> list[str]: ...

    @property
    @abstractmethod
    def cwd(self) -> Path: ...

    def start(self) -> None:
        self._check_port_free()
        self._process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            start_new_session=True,
            stdout=DEVNULL,
            stderr=DEVNULL,
        )
        self._wait_ready()

    def stop(self) -> None:
        if self._process is None:
            return
        try:
            pgid = os.getpgid(self._process.pid)
            os.killpg(pgid, signal.SIGTERM)
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
                self._process.wait()
        except ProcessLookupError:
            pass
        finally:
            self._process = None

    def _check_port_free(self) -> None:
        try:
            with socket.create_connection(("localhost", self.port), timeout=1):
                raise RuntimeError(
                    f"Port {self.port} is already in use — kill the stale process first."
                )
        except OSError:
            pass

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            try:
                requests.get(f"http://localhost:{self.port}/", timeout=1)
                return
            except requests.exceptions.ConnectionError:
                time.sleep(0.5)
            except requests.exceptions.Timeout:
                time.sleep(0.5)
        raise TimeoutError(
            f"{self.name} did not start on port {self.port} "
            f"within {self.startup_timeout}s"
        )


class PyHankoVerifier(LibraryVerifier):
    name = "pyhanko"
    startup_timeout = 30

    @property
    def version(self) -> str | None:
        try:
            from importlib.metadata import version
            return version("pyhanko")
        except Exception:
            return None

    @property
    def command(self) -> list[str]:
        return [
            "uv", "run", "gunicorn", "main:application",
            "--bind", f"localhost:{self.port}",
        ]

    @property
    def cwd(self) -> Path:
        return _LIBRARY_DIR / "pyhanko"


class DSSVerifier(LibraryVerifier):
    name = "dss"
    version = "6.4"
    startup_timeout = 60

    @property
    def command(self) -> list[str]:
        return ["java", "-jar", "target/demo-0.0.1-SNAPSHOT.jar"]

    @property
    def cwd(self) -> Path:
        return _LIBRARY_DIR / "dss"


REGISTRY: dict[str, type[LibraryVerifier]] = {
    PyHankoVerifier.name: PyHankoVerifier,
    DSSVerifier.name: DSSVerifier,
}


def _pyhanko_version() -> str | None:
    try:
        from importlib.metadata import version
        return version("pyhanko")
    except Exception:
        return None


# (slug, display_name, version)
SEED_DATA: list[tuple[str, str, str | None]] = [
    ("pyhanko", "PyHanko", _pyhanko_version()),
    ("dss", "DSS", DSSVerifier.version),
]
