"""Docker and HTTP operations for the Windows VM."""

import subprocess
import sqlite3
import tempfile
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests
from tester_scripts.gui.verifiers import REGISTRY as GUI_VERIFIERS

from .config import API_URL, INSTALLER_CACHE, REPO_ROOT, STATE_ROOT, VERIFIERS


def _merge_database(database: Path, returned_database: Path) -> None:
    """Add missing verifier results without replacing the local test corpus."""
    with (
        sqlite3.connect(database, timeout=60) as target,
        sqlite3.connect(returned_database) as source,
    ):
        target.execute("BEGIN IMMEDIATE")
        verifier_ids = dict(target.execute("SELECT name, id FROM verifier"))
        test_ids = {
            row[0] for row in target.execute("SELECT id FROM modification_test")
        }
        existing = set(
            target.execute(
                """
                SELECT association.idA, result.name
                FROM modification_verifier_association AS association
                JOIN verifier_test AS result ON result.id = association.idB
                """
            )
        )

        rows = source.execute(
            """
            SELECT association.idA, result.name,
                   result.result_layer_1, result.warn_modified_layer_1,
                   result.screenshot_layer_1,
                   result.result_layer_2, result.warn_modified_layer_2,
                   result.screenshot_layer_2
            FROM modification_verifier_association AS association
            JOIN verifier_test AS result ON result.id = association.idB
            """
        )
        for row in rows:
            test_id, verifier = row[:2]
            if (
                (test_id, verifier) in existing
                or test_id not in test_ids
                or verifier not in verifier_ids
            ):
                continue
            cursor = target.execute(
                """
                INSERT INTO verifier_test (
                    name, verifier_id,
                    result_layer_1, warn_modified_layer_1, screenshot_layer_1,
                    result_layer_2, warn_modified_layer_2, screenshot_layer_2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (verifier, verifier_ids[verifier], *row[2:]),
            )
            target.execute(
                """
                INSERT INTO modification_verifier_association (idA, idB)
                VALUES (?, ?)
                """,
                (test_id, cursor.lastrowid),
            )
            existing.add((test_id, verifier))


def _targets(values: list[str]) -> list[str]:
    if values == ["all"]:
        values = sorted(GUI_VERIFIERS)
    if not values or "all" in values or set(values) - set(GUI_VERIFIERS):
        raise ValueError(
            f"Choose one or more of {', '.join(sorted(GUI_VERIFIERS))}, "
            "or use 'all' by itself."
        )
    missing = set(values) - set(VERIFIERS)
    if missing:
        raise ValueError(
            f"Missing Windows VM configuration for: {', '.join(sorted(missing))}"
        )
    return list(dict.fromkeys(values))


def create_vm() -> None:
    """Create the local directories and start the persistent VM."""
    (STATE_ROOT / "storage").mkdir(parents=True, exist_ok=True)
    INSTALLER_CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(REPO_ROOT / "vm" / "compose.yaml"),
            "up",
            "-d",
        ],
        check=True,
        cwd=REPO_ROOT,
    )


def init_vm(timeout: float) -> dict[str, Any]:
    """Wait for the HTTP worker and check its desktop dimensions."""
    deadline = time.monotonic() + timeout
    health: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        try:
            with requests.get(f"{API_URL}/health", timeout=5) as response:
                response.raise_for_status()
                health = response.json()
            break
        except requests.RequestException:
            time.sleep(2)
    if health is None:
        raise RuntimeError(
            f"Windows did not become ready within {timeout:.0f}s; "
            "open http://127.0.0.1:8006 to inspect it."
        )
    if (health.get("screen_width"), health.get("screen_height")) != (1920, 1080):
        raise RuntimeError("Windows must use a 1920x1080 desktop.")
    if health.get("dpi") != 96:
        raise RuntimeError("Windows must use 96 DPI (100% scaling).")
    return health


def ensure_vm(timeout: float) -> dict[str, Any]:
    """Start the Windows container when needed, then wait for its worker."""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(REPO_ROOT / "vm" / "compose.yaml"),
            "ps",
            "--status",
            "running",
            "--services",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if "windows-verifiers" in result.stdout.splitlines():
        print("Windows VM is running; checking guest health...")
    else:
        print("Windows VM is not running; starting it...")
        create_vm()
    return init_vm(timeout)


def prepare_vm(values: list[str], timeout: float) -> list[str]:
    """Upload selected installers and prepare the guest."""
    installers: list[dict[str, Any]] = []
    for slug in _targets(values):
        spec = VERIFIERS[slug]
        source = INSTALLER_CACHE / f"{slug}{spec.installer_extension}"
        available = source.is_file()
        if not available and spec.installer_required:
            raise RuntimeError(f"Missing installer: {source}")
        if available:
            with source.open("rb") as data, requests.put(
                f"{API_URL}/installers/{source.name}", data=data, timeout=300
            ) as response:
                response.raise_for_status()
        installers.append(asdict(spec) | {"slug": slug, "available": available})

    with requests.post(
        f"{API_URL}/prepare",
        json={"installers": installers},
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        return list(response.json().get("warnings", []))


def run_vm(
    values: list[str],
    database: Path,
    mode: str,
    action_delay: float,
    timeout: float,
) -> None:
    """Run verifiers and directly replace the database with the result."""
    database = database.expanduser().resolve()
    if not database.is_file():
        raise RuntimeError(f"Database does not exist: {database}")

    with database.open("rb") as data, requests.put(
        f"{API_URL}/database", data=data, timeout=300
    ) as response:
        response.raise_for_status()

    run_error = None
    with requests.post(
        f"{API_URL}/run",
        json={
            "verifiers": [
                {"slug": slug, "exe": VERIFIERS[slug].exe}
                for slug in _targets(values)
            ],
            "mode": mode,
            "action_delay": action_delay,
        },
        timeout=timeout,
    ) as response:
        if not response.ok:
            run_error = response.json().get("error", "VM verifier run failed")

    with requests.get(f"{API_URL}/database", timeout=300) as response:
        response.raise_for_status()
        with tempfile.TemporaryDirectory() as directory:
            returned_database = Path(directory) / "results.db"
            returned_database.write_bytes(response.content)
            _merge_database(database, returned_database)

    archive = STATE_ROOT / "screenshots.zip"
    with requests.get(f"{API_URL}/screenshots", timeout=300) as response:
        if response.status_code != 404:
            response.raise_for_status()
            archive.write_bytes(response.content)
            with zipfile.ZipFile(archive) as screenshots:
                screenshots.extractall(REPO_ROOT / "src" / "screenshots")
            archive.unlink()

    if run_error:
        raise RuntimeError(
            f"{run_error}\nPartial database was recovered; available screenshots "
            "were also downloaded."
        )


def stop_vm() -> None:
    """Stop the VM while keeping its disk."""
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(REPO_ROOT / "vm" / "compose.yaml"),
            "stop",
        ],
        check=True,
        cwd=REPO_ROOT,
    )
