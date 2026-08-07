"""Docker and HTTP operations for the Windows VM."""

import subprocess
import sqlite3
import tempfile
import threading
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests
from tester_scripts.gui.verifiers import REGISTRY as GUI_VERIFIERS

from .config import API_URL, INSTALLER_CACHE, REPO_ROOT, STATE_ROOT, VERIFIERS

# The guest writes a consistent DB snapshot here (shared folder) after every
# committed test; see worker.ps1 SBSEG_DB_SYNC_PATH.
SHARED_OUTPUT_DB = STATE_ROOT / "vm_output.db"
# How often the host folds the guest's shared snapshot into the local DB.
_MERGE_POLL_INTERVAL = 5.0


def _merge_database(database: Path, returned_database: Path) -> int:
    """Add missing verifier results without replacing the local test corpus.

    Returns the number of newly inserted verifier results.
    """
    inserted = 0
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
            inserted += 1
    return inserted


def _merge_shared_snapshot(database: Path, snapshot: Path) -> int:
    """Fold the guest's shared snapshot into the local DB; return #inserted.

    Tolerant of a missing or momentarily-unreadable snapshot (the guest writes
    it atomically, but SMB propagation can lag) so it is safe to call on a
    timer while the run is still in flight.
    """
    if not snapshot.is_file():
        return 0
    try:
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "snapshot.db"
            local.write_bytes(snapshot.read_bytes())
            return _merge_database(database, local)
    except (OSError, sqlite3.Error):
        return 0


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
    """Run verifiers, merging results into the local DB as they arrive.

    The guest commits each test to a snapshot in the shared folder; a
    background thread folds those into the local DB while the run is still in
    flight, and a final merge runs no matter how the /run request ends. A
    dropped, crashed, or timed-out request therefore never discards results the
    verifier already recorded.
    """
    database = database.expanduser().resolve()
    if not database.is_file():
        raise RuntimeError(f"Database does not exist: {database}")

    # Clear any snapshot left over from a previous run so we never merge stale
    # results before the guest has produced a fresh one.
    SHARED_OUTPUT_DB.unlink(missing_ok=True)

    with database.open("rb") as data, requests.put(
        f"{API_URL}/database", data=data, timeout=300
    ) as response:
        response.raise_for_status()

    stop_polling = threading.Event()

    def _poll_snapshot() -> None:
        while not stop_polling.wait(_MERGE_POLL_INTERVAL):
            added = _merge_shared_snapshot(database, SHARED_OUTPUT_DB)
            if added:
                print(f"Merged {added} new result(s) from the VM so far.")

    poller = threading.Thread(target=_poll_snapshot, daemon=True)
    poller.start()

    run_error = None
    try:
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
    except requests.RequestException as error:
        # The request itself failed (timeout, reset, VM restart). The guest may
        # still have committed results to the shared snapshot; the finally below
        # collects whatever is there.
        run_error = f"VM run request failed: {error}"
    finally:
        stop_polling.set()
        poller.join(timeout=30)

        # Authoritative final merge from the shared snapshot — independent of
        # whether the request survived.
        _merge_shared_snapshot(database, SHARED_OUTPUT_DB)

        # Best-effort HTTP fallback in case the shared snapshot never appeared
        # (e.g. an old guest worker without snapshot support).
        try:
            with requests.get(f"{API_URL}/database", timeout=300) as response:
                if response.ok:
                    with tempfile.TemporaryDirectory() as directory:
                        returned = Path(directory) / "results.db"
                        returned.write_bytes(response.content)
                        _merge_database(database, returned)
        except requests.RequestException:
            pass

        # Screenshots are best-effort and must not mask a run error.
        archive = STATE_ROOT / "screenshots.zip"
        try:
            with requests.get(f"{API_URL}/screenshots", timeout=300) as response:
                if response.status_code != 404:
                    response.raise_for_status()
                    archive.write_bytes(response.content)
                    with zipfile.ZipFile(archive) as screenshots:
                        screenshots.extractall(REPO_ROOT / "src" / "screenshots")
                    archive.unlink()
        except (requests.RequestException, zipfile.BadZipFile, OSError):
            pass

    if run_error:
        raise RuntimeError(
            f"{run_error}\nResults committed before the failure were merged into "
            f"{database}; available screenshots were also downloaded."
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
